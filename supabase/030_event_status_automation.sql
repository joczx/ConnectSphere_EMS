-- Apply after 028. Approval is a review outcome, not a separate lifecycle
-- status. An approved request and its operational event both enter Planning.
begin;

drop trigger if exists create_event_after_request_approval on public.event_request;
create trigger create_event_after_request_approval
    after update of status on public.event_request for each row
    when (new.status = 'planning' and old.status is distinct from 'planning')
    execute function public.create_event_from_approved_request();

alter table public.events add column if not exists registration_ready boolean not null default false;

alter table public.event_request drop constraint if exists complete_before_submit;
alter table public.event_request add constraint complete_before_submit check (
    status in ('draft', 'cancelled') or (
        event_name is not null and purpose is not null and start_datetime is not null
        and end_datetime is not null and capacity_needed is not null
    )
);

-- Private evaluator: all reservations must cover the event's entire period.
-- Match types case-insensitively, summing models of the same type. Never count
-- accepted requests a second time: their linked reservations are the stock held.
create or replace function public.event_confirmation_blockers(p_event public.events)
returns text[] language plpgsql volatile security definer set search_path = public as $$
declare blockers text[] := '{}'; item jsonb; reserved bigint;
begin
    if p_event.event_coordinator_id is null then
        blockers := array_append(blockers, 'An Event Coordinator must be assigned.');
    end if;
    if p_event.start_datetime is null or p_event.end_datetime is null
        or p_event.end_datetime <= p_event.start_datetime then
        blockers := array_append(blockers, 'Valid event dates are required.');
    end if;
    if not exists (
        select 1 from public.venue_booking_requests b join public.venues v using (venue_id)
        where b.event_id = p_event.event_id and b.status = 'approved'
          and b.starts_at = p_event.start_datetime and b.ends_at = p_event.end_datetime
          and (p_event.capacity_needed is null or b.attendance = p_event.capacity_needed)
          and v.deleted_at is null
          and cardinality(public.venue_shortfalls_for_event(v, p_event)) = 0
    ) then
        blockers := array_append(blockers, 'An approved venue booking matching the event is required.');
    end if;
    if p_event.equipment_requirements is null then
        blockers := array_append(blockers, 'Record equipment requirements, or an empty list if none are needed.');
    elsif jsonb_typeof(p_event.equipment_requirements) <> 'array' then
        blockers := array_append(blockers, 'Equipment requirements must be a list of types and quantities.');
    else
        for item in select value from jsonb_array_elements(p_event.equipment_requirements) loop
            if jsonb_typeof(item) <> 'object'
                or jsonb_typeof(item->'equipment_type') is distinct from 'string'
                or jsonb_typeof(item->'quantity') is distinct from 'number'
                or nullif(btrim(item->>'equipment_type'), '') is null
                or coalesce(item->>'quantity', '') !~ '^[1-9][0-9]*$' then
                blockers := array_append(blockers, 'Each equipment requirement needs a type and positive quantity.');
                continue;
            end if;
            select coalesce(sum(r.quantity), 0) into reserved
            from public.equipment_reservations r join public.equipment q using (equipment_id)
            where r.event_id = p_event.event_id::text
              and lower(btrim(q.equipment_type)) = lower(btrim(item->>'equipment_type'))
              and r.starts_at <= p_event.start_datetime and r.ends_at >= p_event.end_datetime;
            if reserved < (item->>'quantity')::numeric then
                blockers := array_append(blockers, 'Reserve all required ' || (item->>'equipment_type') || '.');
            end if;
        end loop;
    end if;
    -- Additional requests must also be fully fulfilled, including requests
    -- added after the original requirements. Rejected/partial requests do not
    -- silently become fulfilled requests.
    if exists (
        select 1 from public.equipment_request q where q.event_id = p_event.event_id
        and not exists (select 1 from public.equipment_reservations r
            where r.equipment_request_id = q.equipment_request_id
              and r.quantity >= q.quantity
              and r.starts_at <= p_event.start_datetime and r.ends_at >= p_event.end_datetime)
    ) then
        blockers := array_append(blockers, 'Every equipment request must be fully reserved.');
    end if;
    if nullif(btrim(p_event.registration_needs), '') is not null and not p_event.registration_ready then
        blockers := array_append(blockers, 'The Event Coordinator must confirm registration readiness.');
    end if;
    return blockers;
end;
$$;

-- Before-write guard also covers direct PostgREST writes, not just Flask.
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
            (old.status = 'planning' and new.status in ('confirmed', 'cancelled'))
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
    if new.status in ('planning', 'confirmed') then
        blockers := public.event_confirmation_blockers(new);
        if TG_OP = 'UPDATE' and old.status = 'planning' and new.status = 'confirmed'
            and cardinality(blockers) > 0 then
            raise check_violation using message = array_to_string(blockers, ' ');
        end if;
        if TG_OP = 'UPDATE' and old.status = 'confirmed' and new.status = 'planning'
            and cardinality(blockers) = 0 then
            raise check_violation using message = 'A confirmed event can return to Planning only if arrangements are incomplete.';
        end if;
        -- Losing a reservation reopens Planning rather than showing a false
        -- Confirmed status. A cancellation/completion is never reopened.
        new.status := case when cardinality(blockers) = 0 then 'confirmed'::public.event_status
                           else 'planning'::public.event_status end;
    end if;
    if TG_OP = 'UPDATE' then new.updated_at := clock_timestamp(); end if;
    return new;
end;
$$;
create trigger guard_event_lifecycle before insert or update on public.events
    for each row execute function public.guard_event_lifecycle();

create or replace function public.guard_request_lifecycle()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    if TG_OP = 'INSERT' then
        if new.status not in ('draft', 'submitted') then
            raise check_violation using message = 'New requests must be Draft or Submitted.';
        end if;
    elsif new.status is distinct from old.status then
        if not ((old.status = 'draft' and new.status in ('submitted', 'cancelled'))
            or (old.status = 'submitted' and new.status in ('planning', 'rejected', 'cancelled'))
            or (old.status = 'rejected' and new.status in ('submitted', 'cancelled'))) then
            raise check_violation using message = 'Invalid request status transition.';
        end if;
        if new.status in ('planning', 'rejected') then
            if auth.uid() is distinct from old.event_coordinator_id then
                raise insufficient_privilege using message = 'Only the assigned coordinator can decide a request.';
            end if;
            if not exists (select 1 from public.event_request_review r
                where r.event_request_id = new.event_request_id
                  and r.reviewer_id = old.event_coordinator_id
                  and r.outcome::text = case when new.status = 'planning' then 'approved' else 'rejected' end
                  and r.created_at >= old.updated_at) then
                raise check_violation using message = 'A matching coordinator review is required.';
            end if;
        end if;
    end if;
    if new.status = 'submitted' and (TG_OP = 'INSERT' or old.status is distinct from new.status)
        and (new.start_datetime <= now() or new.end_datetime <= new.start_datetime) then
        raise check_violation using message = 'Submission requires a future start and an end after the start.';
    end if;
    return new;
end;
$$;
create trigger guard_request_lifecycle before insert or update of status on public.event_request
    for each row execute function public.guard_request_lifecycle();

-- Re-evaluate after each arrangement write in the same transaction. Updating
-- the parent serializes concurrent arrangement changes. The evaluator is
-- VOLATILE so its reads see commits that arrived while that row lock waited.
create or replace function public.refresh_arranged_event()
returns trigger language plpgsql security definer set search_path = public as $$
declare previous_id text; next_id text;
begin
    if TG_OP <> 'INSERT' then previous_id := old.event_id::text; end if;
    if TG_OP <> 'DELETE' then next_id := new.event_id::text; end if;
    update public.events set updated_at = clock_timestamp()
    where event_id::text in (previous_id, next_id) and status in ('planning', 'confirmed');
    return null;
end;
$$;
create trigger venue_updates_event_status after insert or update or delete on public.venue_booking_requests
    for each row execute function public.refresh_arranged_event();
create trigger reservations_update_event_status after insert or update or delete on public.equipment_reservations
    for each row execute function public.refresh_arranged_event();
create trigger requests_update_event_status after insert or update or delete on public.equipment_request
    for each row execute function public.refresh_arranged_event();

create or replace function public.refresh_venue_event_statuses()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    update public.events e set updated_at = clock_timestamp()
    where e.status in ('planning', 'confirmed') and exists (
        select 1 from public.venue_booking_requests b
        where b.event_id = e.event_id and b.venue_id = new.venue_id and b.status = 'approved'
    );
    return null;
end;
$$;
create trigger venue_changes_update_event_status after update on public.venues
    for each row execute function public.refresh_venue_event_statuses();

alter table public.event_activity drop constraint if exists event_activity_change_type_check;
alter table public.event_activity add constraint event_activity_change_type_check
    check (change_type in ('edit', 'critical_edit', 'status_change'));
create or replace function public.record_event_status_change()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    insert into public.event_activity (event_id, changed_by, change_type, changes)
    values (new.event_id, auth.uid(), 'status_change',
        jsonb_build_object('status', jsonb_build_object('from', old.status, 'to', new.status)));
    return null;
end;
$$;
create trigger record_event_status_change after update on public.events
    for each row when (old.status is distinct from new.status)
    execute function public.record_event_status_change();

-- Narrow RPC: only the assigned coordinator can acknowledge registration.
create or replace function public.set_event_registration_ready(p_event_id integer, p_ready boolean)
returns jsonb language plpgsql security definer set search_path = public as $$
declare saved public.events;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    select * into saved from public.events where event_id = p_event_id for update;
    if not found or saved.event_coordinator_id is distinct from auth.uid() then
        return jsonb_build_object('error', 'Only the assigned Event Coordinator can update registration readiness.', 'status', 403);
    end if;
    if saved.status not in ('planning', 'confirmed') then
        return jsonb_build_object('error', 'Registration readiness cannot change at this stage.', 'status', 409);
    end if;
    if p_ready is null then return jsonb_build_object('error', 'Readiness must be true or false.', 'status', 400); end if;
    update public.events set registration_ready = p_ready where event_id = p_event_id returning * into saved;
    return jsonb_build_object('event', to_jsonb(saved), 'blockers', public.event_confirmation_blockers(saved));
end;
$$;

create or replace function public.refresh_visible_event_statuses()
returns jsonb language plpgsql security definer set search_path = public as $$
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    update public.events set status = 'completed'
    where status = 'confirmed' and end_datetime <= now()
      and auth.uid() in (event_organiser_id, event_coordinator_id, technical_support_id, venue_staff_id);
    return '{}'::jsonb;
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
    if saved.status not in ('planning', 'confirmed') then
        return jsonb_build_object('error', 'Only Planning or Confirmed events can be cancelled.', 'status', 409);
    end if;
    update public.events set status = 'cancelled' where event_id = p_event_id returning * into saved;
    return jsonb_build_object('event', to_jsonb(saved));
end;
$$;

create or replace function public.cancel_event_request(p_request_id integer)
returns jsonb language plpgsql security definer set search_path = public as $$
declare saved public.event_request;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    select * into saved from public.event_request where event_request_id = p_request_id for update;
    if not found or (auth.uid() is distinct from saved.event_organiser_id and auth.uid() is distinct from saved.event_coordinator_id) then
        return jsonb_build_object('error', 'Event request not found or access unavailable.', 'status', 404);
    end if;
    if saved.status not in ('draft', 'submitted', 'rejected') then
        return jsonb_build_object('error', 'Cancel the operational event after approval.', 'status', 409);
    end if;
    update public.event_request set status = 'cancelled', updated_at = clock_timestamp()
    where event_request_id = p_request_id returning * into saved;
    return jsonb_build_object('event_request', to_jsonb(saved));
end;
$$;

revoke all on function public.event_confirmation_blockers(public.events), public.guard_event_lifecycle(),
    public.guard_request_lifecycle(), public.refresh_arranged_event(), public.refresh_venue_event_statuses(), public.record_event_status_change(),
    public.set_event_registration_ready(integer, boolean), public.refresh_visible_event_statuses(),
    public.cancel_planned_event(integer), public.cancel_event_request(integer) from public, anon, authenticated;
grant execute on function public.set_event_registration_ready(integer, boolean), public.refresh_visible_event_statuses(),
    public.cancel_planned_event(integer), public.cancel_event_request(integer) to authenticated;

-- Apply readiness to existing planning events after all guards are installed.
update public.events set updated_at = clock_timestamp() where status = 'planning';
commit;
