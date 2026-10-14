-- Operational Safety Reviews. Apply after 033_add_pending_safety_checks_status.sql
-- and 032_technical_support_reservations.sql.
--
-- An event moves from Planning to Pending Safety Checks once its approved venue
-- and technical equipment arrangements are complete. This migration deliberately
-- makes the review read-only: a later safety-decision story can introduce an
-- approved/rejected outcome without conflating this story's review access with
-- an unrequested lifecycle decision.
begin;

-- Make the role available for assignment without duplicating it in databases
-- where an administrator has already created it.
insert into public.roles (role_name)
select 'Safety Officer'
where not exists (
    select 1 from public.roles
    where lower(replace(btrim(role_name), ' ', '_')) = 'safety_officer'
);

alter table public.venues
    add column if not exists emergency_access text,
    add column if not exists safety_restrictions text;

alter table public.events
    add column if not exists crowd_movement_plan text,
    add column if not exists equipment_placement_plan text;

-- Existing confirmation checks also require coordinator assignment and
-- registration readiness. They are intentionally excluded here: Safety may
-- review as soon as venue and technical arrangements are done.
create or replace function public.event_safety_check_blockers(p_event public.events)
returns text[] language sql volatile security definer set search_path = public as $$
    select coalesce(array_agg(item), array[]::text[])
    from unnest(public.event_confirmation_blockers(p_event)) as item
    where item not in (
        'An Event Coordinator must be assigned.',
        'The Event Coordinator must confirm registration readiness.'
    );
$$;

create or replace function public.has_safety_officer_role()
returns boolean language sql stable security definer set search_path = public as $$
    select auth.uid() is not null and exists (
        select 1
        from public.user_roles ur join public.roles r using (role_id)
        where ur.user_id = auth.uid()
          and lower(replace(btrim(r.role_name), ' ', '_')) = 'safety_officer'
    );
$$;

-- Preserve the existing lifecycle safeguards while inserting the explicit
-- hand-off to Safety. A direct API/database write cannot jump to the pending
-- status; it is derived only when the arrangement blockers disappear.
create or replace function public.guard_event_lifecycle()
returns trigger language plpgsql security definer set search_path = public as $$
declare blockers text[];
begin
    if TG_OP = 'INSERT' then
        new.registration_ready := false;
        if new.status <> 'planning' then
            raise check_violation using message = 'New operational events start in Planning.';
        end if;
    else
        if old.status = 'confirmed' and
            (to_jsonb(new) - array['status', 'registration_ready', 'updated_at']) is distinct from
            (to_jsonb(old) - array['status', 'registration_ready', 'updated_at']) then
            raise check_violation using message = 'Confirmed event arrangements cannot be edited.';
        end if;
        if new.registration_ready is distinct from old.registration_ready
            and auth.uid() is distinct from old.event_coordinator_id then
            raise insufficient_privilege using message = 'Only the assigned coordinator can confirm registration readiness.';
        end if;
        if new.registration_needs is distinct from old.registration_needs then
            new.registration_ready := false;
        end if;
        if old.status in ('completed', 'cancelled') and new is distinct from old then
            raise check_violation using message = 'Completed and cancelled events cannot be changed.';
        end if;
        if new.status is distinct from old.status and not (
            (old.status = 'planning' and new.status = 'cancelled')
            or (old.status = 'pending_safety_checks' and new.status in ('planning', 'cancelled'))
            or (old.status = 'confirmed' and new.status in ('planning', 'completed', 'cancelled'))
        ) then
            raise check_violation using message = 'Invalid event status transition.';
        end if;
        if new.status = 'cancelled' and old.status <> 'cancelled'
            and auth.uid() is distinct from old.event_coordinator_id
            and auth.uid() is distinct from old.event_organiser_id then
            raise insufficient_privilege using message = 'Only the organiser or coordinator can cancel an event.';
        end if;
        if new.status = 'completed' and old.status <> 'completed'
            and (new.end_datetime is null or new.end_datetime > now()) then
            raise check_violation using message = 'An event cannot complete before its end time.';
        end if;
    end if;

    if new.status in ('planning', 'pending_safety_checks') then
        blockers := public.event_safety_check_blockers(new);
        new.status := case when cardinality(blockers) = 0
                           then 'pending_safety_checks'::public.event_status
                           else 'planning'::public.event_status end;
    elsif new.status = 'confirmed' then
        blockers := public.event_confirmation_blockers(new);
        if cardinality(blockers) > 0 then
            new.status := 'planning'::public.event_status;
        end if;
    end if;
    if TG_OP = 'UPDATE' then new.updated_at := clock_timestamp(); end if;
    return new;
end;
$$;

-- Registration may be recorded before or while Safety reviews the event.
create or replace function public.set_event_registration_ready(p_event_id integer, p_ready boolean)
returns jsonb language plpgsql security definer set search_path = public as $$
declare saved public.events;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    select * into saved from public.events where event_id = p_event_id for update;
    if not found or saved.event_coordinator_id is distinct from auth.uid() then
        return jsonb_build_object('error', 'Only the assigned Event Coordinator can update registration readiness.', 'status', 403);
    end if;
    if saved.status not in ('planning', 'pending_safety_checks', 'confirmed') then
        return jsonb_build_object('error', 'Registration readiness cannot change at this stage.', 'status', 409);
    end if;
    if p_ready is null then return jsonb_build_object('error', 'Readiness must be true or false.', 'status', 400); end if;
    update public.events set registration_ready = p_ready where event_id = p_event_id returning * into saved;
    return jsonb_build_object('event', to_jsonb(saved), 'blockers', public.event_confirmation_blockers(saved));
end;
$$;

create or replace function public.cancel_planned_event(p_event_id integer)
returns jsonb language plpgsql security definer set search_path = public as $$
declare saved public.events;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    select * into saved from public.events where event_id = p_event_id for update;
    if not found or (auth.uid() is distinct from saved.event_organiser_id and auth.uid() is distinct from saved.event_coordinator_id) then
        return jsonb_build_object('error', 'Event not found or access unavailable.', 'status', 404);
    end if;
    if saved.status not in ('planning', 'pending_safety_checks', 'confirmed') then
        return jsonb_build_object('error', 'Only Planning, Pending Safety Checks, or Confirmed events can be cancelled.', 'status', 409);
    end if;
    update public.events set status = 'cancelled' where event_id = p_event_id returning * into saved;
    return jsonb_build_object('event', to_jsonb(saved));
end;
$$;

-- The queue and event read use a security-definer RPC so the Safety Officer
-- role, rather than broad table access, controls visibility.
create or replace function public.safety_review_queue()
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare result jsonb;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_safety_officer_role() then
        return jsonb_build_object('error', 'Only Safety Officers can review operational safety arrangements.', 'status', 403);
    end if;
    select coalesce(jsonb_agg(jsonb_build_object(
        'event_id', e.event_id,
        'event_name', e.event_name,
        'start_datetime', e.start_datetime,
        'end_datetime', e.end_datetime,
        'capacity_needed', e.capacity_needed,
        'venue_name', venue.venue_name
    ) order by e.start_datetime), '[]'::jsonb) into result
    from public.events e
    left join lateral (
        select v.venue_name
        from public.venue_booking_requests b join public.venues v using (venue_id)
        where b.event_id = e.event_id and b.status = 'approved'
        order by b.reviewed_at desc nulls last
        limit 1
    ) venue on true
    where e.status = 'pending_safety_checks';
    return jsonb_build_object('events', result);
end;
$$;

create or replace function public.safety_review_event(p_event_id integer)
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare event_row public.events; result jsonb;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_safety_officer_role() then
        return jsonb_build_object('error', 'Only Safety Officers can review operational safety arrangements.', 'status', 403);
    end if;
    select * into event_row from public.events
    where event_id = p_event_id and status = 'pending_safety_checks';
    if not found then return jsonb_build_object('error', 'Event not found or no longer awaiting safety checks.', 'status', 404); end if;

    select jsonb_build_object(
        'event_id', event_row.event_id,
        'event_name', event_row.event_name,
        'start_datetime', event_row.start_datetime,
        'end_datetime', event_row.end_datetime,
        'expected_attendance', event_row.capacity_needed,
        'venue_name', v.venue_name,
        'venue_capacity', v.capacity,
        'room_layout', replace(coalesce(event_row.room_layout::text, ''), '_', ' '),
        'emergency_access', v.emergency_access,
        'accessibility_requirements', to_jsonb(array_remove(array[
            case when event_row.need_wheelchair_accessibility then 'Wheelchair accessibility required' end,
            case when event_row.need_blind_accessibility then 'Blind-accessibility support required' end,
            case when v.wheelchair_accessible then 'Venue has wheelchair access' end,
            case when v.blind_accessible then 'Venue has blind-accessibility support' end
        ], null)),
        'equipment_placement', coalesce((
            select jsonb_agg(item order by item)
            from (
                select event_row.equipment_placement_plan as item
                where nullif(btrim(event_row.equipment_placement_plan), '') is not null
                union all
                select q.equipment_type || ' – ' || q.equipment_model || ' (quantity ' || r.quantity || ')'
                from public.equipment_reservations r join public.equipment q using (equipment_id)
                where r.event_id = event_row.event_id::text
            ) arranged_equipment
        ), '[]'::jsonb),
        'crowd_movement', event_row.crowd_movement_plan,
        'venue_restrictions', v.safety_restrictions
    ) into result
    from public.venue_booking_requests b
    join public.venues v using (venue_id)
    where b.event_id = event_row.event_id and b.status = 'approved'
    order by b.reviewed_at desc nulls last
    limit 1;
    return jsonb_build_object('event', coalesce(result, to_jsonb(event_row)));
end;
$$;

revoke all on function public.event_safety_check_blockers(public.events), public.has_safety_officer_role(),
    public.safety_review_queue(), public.safety_review_event(integer) from public, anon, authenticated;
grant execute on function public.safety_review_queue(), public.safety_review_event(integer) to authenticated;

-- Re-evaluate existing planning events so already-complete arrangements enter
-- the same review queue as newly completed arrangements.
update public.events set updated_at = clock_timestamp() where status = 'planning';

notify pgrst, 'reload schema';
commit;
