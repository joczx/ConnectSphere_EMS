-- ConnectSphere EMS: remove the registration-readiness lifecycle gate.
-- Apply after 052_event_registration_roster.sql and 048_submit_for_safety_checks.sql.
-- Registration requirements, periods, attendee registration, waiting lists and
-- rosters remain; only the readiness acknowledgement and its lifecycle effect
-- are removed.

begin;

-- Venue and equipment arrangements remain the confirmation prerequisites.
-- Registration details deliberately do not participate in this function.
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
            where r.event_id = p_event.event_id
              and lower(btrim(q.equipment_type)) = lower(btrim(item->>'equipment_type'))
              and r.starts_at <= p_event.start_datetime and r.ends_at >= p_event.end_datetime;
            if reserved < (item->>'quantity')::numeric then
                blockers := array_append(blockers, 'Reserve all required ' || (item->>'equipment_type') || '.');
            end if;
        end loop;
    end if;
    if exists (
        select 1 from public.equipment_request q where q.event_id = p_event.event_id
        and not exists (select 1 from public.equipment_reservations r
            where r.equipment_request_id = q.equipment_request_id
              and r.quantity >= q.quantity
              and r.starts_at <= p_event.start_datetime and r.ends_at >= p_event.end_datetime)
    ) then
        blockers := array_append(blockers, 'Every equipment request must be fully reserved.');
    end if;
    return blockers;
end;
$$;

create or replace function public.event_safety_check_blockers(p_event public.events)
returns text[] language plpgsql volatile security definer set search_path = public as $$
declare blockers text[]; requirements text[] := coalesce(p_event.safety_rework_arrangements, array[]::text[]);
begin
    blockers := public.event_confirmation_blockers(p_event);
    blockers := array_remove(blockers, 'An Event Coordinator must be assigned.');
    if p_event.safety_rework_required then
        blockers := array_append(blockers, 'Address the requested safety changes before another safety check.');
    end if;
    if 'venue' = any(requirements) and not exists (
        select 1 from public.venue_booking_requests b
        join public.venues v using (venue_id)
        where b.event_id = p_event.event_id and b.status = 'approved'
          and b.reviewed_at >= p_event.safety_rework_requested_at
          and b.starts_at = p_event.start_datetime and b.ends_at = p_event.end_datetime
          and (p_event.capacity_needed is null or b.attendance = p_event.capacity_needed)
          and v.deleted_at is null
          and cardinality(public.venue_shortfalls_for_event(v, p_event)) = 0
    ) then
        blockers := array_append(blockers, 'The affected venue arrangement must be reviewed and confirmed again.');
    end if;
    if 'technical' = any(requirements) and not exists (
        select 1 from public.equipment_reservations r
        where r.event_id = p_event.event_id
          and r.created_at >= p_event.safety_rework_requested_at
    ) then
        blockers := array_append(blockers, 'The affected technical arrangement must be reviewed and confirmed again.');
    end if;
    return coalesce(blockers, array[]::text[]);
end;
$$;

-- Preserve the explicit coordinator submission and Safety Officer approval
-- workflow. Registration fields are excluded from both the confirmed-event
-- edit lock and safety-approval invalidation because they are managed by the
-- independent attendee-registration workflow.
create or replace function public.guard_event_lifecycle()
returns trigger language plpgsql security definer set search_path = public as $$
declare
    blockers text[];
    change_request_workflow boolean := coalesce(current_setting('connectsphere.change_request_workflow', true), '') = 'true';
    non_important_workflow boolean := coalesce(current_setting('connectsphere.change_request_importance', true), '') = 'non_important';
    safety_submission boolean := coalesce(current_setting('connectsphere.safety_submission', true), '') = 'true';
begin
    if TG_OP = 'INSERT' then
        if new.status <> 'planning' then
            raise check_violation using message = 'New operational events start in Planning.';
        end if;
    else
        if (new.safety_rework_required is distinct from old.safety_rework_required
            or new.safety_rework_requested_at is distinct from old.safety_rework_requested_at
            or new.safety_rework_arrangements is distinct from old.safety_rework_arrangements
            or new.safety_approved_at is distinct from old.safety_approved_at)
            and current_setting('connectsphere.safety_workflow', true) is distinct from 'true' then
            raise insufficient_privilege using message = 'Safety workflow fields can only be changed by the safety workflow.';
        end if;
        if old.status = 'confirmed' and not change_request_workflow and
            (to_jsonb(new) - array['registration_needs', 'registration_opens_at', 'registration_closes_at',
                                   'waiting_list_enabled', 'status', 'updated_at',
                                   'safety_rework_required', 'safety_rework_requested_at',
                                   'safety_rework_arrangements', 'safety_approved_at']) is distinct from
            (to_jsonb(old) - array['registration_needs', 'registration_opens_at', 'registration_closes_at',
                                   'waiting_list_enabled', 'status', 'updated_at',
                                   'safety_rework_required', 'safety_rework_requested_at',
                                   'safety_rework_arrangements', 'safety_approved_at']) then
            raise check_violation using message = 'Confirmed event arrangements cannot be edited.';
        end if;
        if (to_jsonb(new) - array['registration_needs', 'registration_opens_at', 'registration_closes_at',
                                  'waiting_list_enabled', 'status', 'updated_at',
                                  'safety_rework_required', 'safety_rework_requested_at',
                                  'safety_rework_arrangements', 'safety_approved_at']) is distinct from
           (to_jsonb(old) - array['registration_needs', 'registration_opens_at', 'registration_closes_at',
                                  'waiting_list_enabled', 'status', 'updated_at',
                                  'safety_rework_required', 'safety_rework_requested_at',
                                  'safety_rework_arrangements', 'safety_approved_at'])
            and not (change_request_workflow and non_important_workflow) then
            new.safety_rework_required := false;
            new.safety_approved_at := null;
        end if;
        if old.status in ('completed', 'cancelled') and new is distinct from old then
            raise check_violation using message = 'Completed and cancelled events cannot be changed.';
        end if;
        if new.status is distinct from old.status and not (
            (old.status = 'planning' and new.status = 'cancelled')
            or (old.status = 'planning' and new.status = 'pending_safety_checks' and safety_submission)
            or (old.status = 'pending_safety_checks' and new.status in ('planning', 'confirmed', 'cancelled'))
            or (old.status = 'confirmed' and new.status in ('planning', 'completed', 'cancelled'))
        ) then
            raise check_violation using message = 'Invalid event status transition.';
        end if;
        if old.status = 'pending_safety_checks' and new.status = 'confirmed' and not exists (
            select 1 from public.operational_safety_decision d
            where d.event_id = old.event_id and d.safety_officer_id = auth.uid()
              and d.outcome = 'approved' and d.created_at >= old.updated_at
        ) then
            raise insufficient_privilege using message = 'A Safety Officer approval is required before confirming this event.';
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
    if TG_OP = 'UPDATE' and change_request_workflow then
        new.status := old.status;
    elsif new.status in ('planning', 'pending_safety_checks') then
        blockers := public.event_safety_check_blockers(new);
        if cardinality(blockers) > 0 then
            new.status := 'planning'::public.event_status;
        elsif new.safety_approved_at is not null
            and cardinality(public.event_confirmation_blockers(new)) = 0 then
            new.status := 'confirmed'::public.event_status;
        end if;
    elsif new.status = 'confirmed' and cardinality(public.event_confirmation_blockers(new)) > 0 then
        new.status := case when new.safety_approved_at is not null
                                and cardinality(public.event_safety_check_blockers(new)) = 0
                           then 'pending_safety_checks'::public.event_status
                           else 'planning'::public.event_status end;
    end if;
    if TG_OP = 'UPDATE' then new.updated_at := clock_timestamp(); end if;
    return new;
end;
$$;

-- Replace 049's decision RPC as well as the trigger it calls. Approval is now
-- unambiguously terminal for this review: when the arrangement blockers above
-- are clear, the assigned Safety Officer's approval returns a Confirmed event.
create or replace function public.record_safety_decision(
    p_event_id integer, p_outcome text, p_remarks text, p_affected_arrangements text[]
) returns jsonb language plpgsql security definer set search_path = public as $$
declare
    planned public.events;
    saved public.operational_safety_decision;
    outcome text := lower(btrim(coalesce(p_outcome, '')));
    remarks text := nullif(btrim(coalesce(p_remarks, '')), '');
    affected text[] := coalesce(p_affected_arrangements, array[]::text[]);
    note text;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_safety_officer_role() then
        return jsonb_build_object('error', 'Only Safety Officers can record operational safety decisions.', 'status', 403);
    end if;
    if outcome not in ('approved', 'rejected', 'changes_requested') then
        return jsonb_build_object('error', 'Choose Approve, Reject, or Request changes.', 'status', 400);
    end if;
    if outcome <> 'approved' and remarks is null then
        return jsonb_build_object('error', 'Remarks are required when rejecting or requesting changes.', 'status', 400);
    end if;
    if remarks is not null and length(remarks) > 2000 then
        return jsonb_build_object('error', 'Remarks must be 2000 characters or fewer.', 'status', 400);
    end if;
    if not (affected <@ array['venue', 'technical']::text[]) then
        return jsonb_build_object('error', 'Affected arrangements must be venue or technical.', 'status', 400);
    end if;

    select * into planned from public.events where event_id = p_event_id for update;
    if not found or planned.status <> 'pending_safety_checks'
        or planned.safety_officer_id is distinct from auth.uid() then
        return jsonb_build_object('error', 'Event not found or no longer awaiting your safety check.', 'status', 404);
    end if;
    if outcome = 'approved' and cardinality(public.event_safety_check_blockers(planned)) > 0 then
        return jsonb_build_object('error', 'The event arrangements changed and must be completed before approval.', 'status', 409);
    end if;
    if planned.event_coordinator_id is null then
        return jsonb_build_object('error', 'Assign an Event Coordinator before recording a safety decision.', 'status', 409);
    end if;

    insert into public.operational_safety_decision
        (event_id, safety_officer_id, outcome, remarks, affected_arrangements)
    values (planned.event_id, auth.uid(), outcome, remarks, affected)
    returning * into saved;

    perform set_config('connectsphere.safety_workflow', 'true', true);
    if outcome = 'approved' then
        update public.events
        set status = 'confirmed', safety_rework_required = false,
            safety_rework_arrangements = array[]::text[], safety_approved_at = saved.created_at
        where event_id = planned.event_id
        returning * into planned;
        note := 'Safety arrangements approved. The event is confirmed.';
    else
        update public.events
        set status = 'planning', safety_rework_required = true,
            safety_rework_requested_at = saved.created_at,
            safety_rework_arrangements = affected, safety_approved_at = null
        where event_id = planned.event_id
        returning * into planned;
        note := case when outcome = 'rejected'
                     then 'Safety arrangements rejected. Address the remarks before proceeding.'
                     else 'Safety changes requested. Address the remarks before proceeding.' end;
    end if;
    perform set_config('connectsphere.safety_workflow', '', true);

    return jsonb_build_object(
        'event', to_jsonb(planned), 'decision', to_jsonb(saved), 'message', note
    );
end;
$$;

-- The API no longer exposes this function. Remove every execution grant with
-- the function itself, then remove the now-unreferenced stored flag.
drop function if exists public.set_event_registration_ready(integer, boolean);
alter table public.events drop column if exists registration_ready;

-- Events that already have a valid Safety approval but were waiting only on
-- registration readiness should become Confirmed immediately.
update public.events
set updated_at = clock_timestamp()
where status = 'pending_safety_checks'
  and safety_approved_at is not null
  and cardinality(public.event_safety_check_blockers(events)) = 0
  and cardinality(public.event_confirmation_blockers(events)) = 0;

notify pgrst, 'reload schema';
commit;
