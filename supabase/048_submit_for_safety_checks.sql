-- ConnectSphere EMS: Event Coordinators submit events for safety checks
-- Run in the Supabase SQL Editor after 047.
--
-- Until now an event moved from Planning to Pending Safety Checks on its own
-- the moment its venue and technical arrangements were complete (034). The
-- coordinator now decides when planning is finished: the event stays in
-- Planning until they submit it, and only then reaches its assigned Safety
-- Officer's queue.
--
-- What still happens automatically:
--   * an event under safety review whose arrangements stop being complete
--     returns to Planning (it must then be submitted again);
--   * a safety-approved event is confirmed once its readiness checks pass.
-- A confirmed event whose safety approval is withdrawn by an arrangement
-- change returns to Planning rather than straight back into the queue.

begin;

-- Copy of 038's definition. Changes are marked "048".
create or replace function public.guard_event_lifecycle()
returns trigger language plpgsql security definer set search_path = public as $$
declare
    blockers text[];
    change_request_workflow boolean := coalesce(current_setting('connectsphere.change_request_workflow', true), '') = 'true';
    non_important_workflow boolean := coalesce(current_setting('connectsphere.change_request_importance', true), '') = 'non_important';
    -- 048: set only by submit_event_for_safety_checks().
    safety_submission boolean := coalesce(current_setting('connectsphere.safety_submission', true), '') = 'true';
begin
    if TG_OP = 'INSERT' then
        new.registration_ready := false;
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
            (to_jsonb(new) - array['status', 'registration_ready', 'updated_at',
                                   'safety_rework_required', 'safety_rework_requested_at',
                                   'safety_rework_arrangements', 'safety_approved_at']) is distinct from
            (to_jsonb(old) - array['status', 'registration_ready', 'updated_at',
                                   'safety_rework_required', 'safety_rework_requested_at',
                                   'safety_rework_arrangements', 'safety_approved_at']) then
            raise check_violation using message = 'Confirmed event arrangements cannot be edited.';
        end if;
        if new.registration_ready is distinct from old.registration_ready
            and auth.uid() is distinct from old.event_coordinator_id then
            raise insufficient_privilege using message = 'Only the assigned coordinator can confirm registration readiness.';
        end if;
        if new.registration_needs is distinct from old.registration_needs then
            new.registration_ready := false;
        end if;
        if (to_jsonb(new) - array['status', 'updated_at', 'registration_ready',
                                  'safety_rework_required', 'safety_rework_requested_at',
                                  'safety_rework_arrangements', 'safety_approved_at'])
                is distinct from
                (to_jsonb(old) - array['status', 'updated_at', 'registration_ready',
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
            -- 048: the coordinator's submission is the only way into the queue.
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
        -- 048: otherwise the requested status stands. Planning is no longer
        -- promoted just because its arrangements are complete.
    elsif new.status = 'confirmed' and cardinality(public.event_confirmation_blockers(new)) > 0 then
        -- 048: only an event that still holds its safety approval waits in
        -- Pending Safety Checks; one whose approval was withdrawn goes back to
        -- Planning for the coordinator to submit again.
        new.status := case when new.safety_approved_at is not null
                                and cardinality(public.event_safety_check_blockers(new)) = 0
                           then 'pending_safety_checks'::public.event_status
                           else 'planning'::public.event_status end;
    end if;
    if TG_OP = 'UPDATE' then new.updated_at := clock_timestamp(); end if;
    return new;
end;
$$;

create or replace function public.submit_event_for_safety_checks(p_event_id integer)
returns jsonb language plpgsql security definer set search_path = public as $$
declare saved public.events; blockers text[]; coordinator text;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    select * into saved from public.events where event_id = p_event_id for update;
    if not found or saved.event_coordinator_id is distinct from auth.uid() then
        return jsonb_build_object('error', 'Only the assigned Event Coordinator can submit this event for safety checks.', 'status', 403);
    end if;
    if saved.status <> 'planning' then
        return jsonb_build_object('error', 'Only events in Planning can be submitted for safety checks.', 'status', 409);
    end if;
    blockers := public.event_safety_check_blockers(saved);
    if cardinality(blockers) > 0 then
        return jsonb_build_object('error', 'Complete the planning arrangements first: ' || array_to_string(blockers, ' '),
                                  'blockers', to_jsonb(blockers), 'status', 409);
    end if;
    if saved.safety_officer_id is null then
        return jsonb_build_object('error', 'No Safety Officer is assigned to this event yet.', 'status', 409);
    end if;

    perform set_config('connectsphere.safety_submission', 'true', true);
    update public.events set status = 'pending_safety_checks' where event_id = p_event_id returning * into saved;
    perform set_config('connectsphere.safety_submission', '', true);

    coordinator := coalesce((select name from public.users where user_id = auth.uid()), 'the Event Coordinator');
    perform public.notify_user(saved.safety_officer_id, 'safety_check_requested', 'Event awaiting safety check',
        format('%s has been submitted for safety checks by %s.', coalesce(saved.event_name, 'An unnamed event'), coordinator),
        '/operational-safety-reviews/' || saved.event_id);
    return jsonb_build_object('event', to_jsonb(saved),
        'message', 'Event submitted for safety checks. The assigned Safety Officer has been notified.');
end;
$$;

-- Copy of 034's queue, narrowed to events assigned to the signed-in officer.
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
    where e.status = 'pending_safety_checks' and e.safety_officer_id = auth.uid();
    return jsonb_build_object('events', result);
end;
$$;

revoke all on function public.submit_event_for_safety_checks(integer) from public, anon, authenticated;
grant execute on function public.submit_event_for_safety_checks(integer) to authenticated;

notify pgrst, 'reload schema';
commit;
