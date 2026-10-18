-- Review and process Event Organiser change requests.
-- Apply after 037_event_change_requests.sql and the operational safety migrations.
begin;

alter table public.event_change_request
    add column if not exists importance text not null default 'important',
    add column if not exists decision_reason text;

alter table public.event_change_request
    drop constraint if exists event_change_request_importance_check;
alter table public.event_change_request
    add constraint event_change_request_importance_check
    check (importance in ('important', 'non_important'));

alter table public.event_change_request
    drop constraint if exists event_change_request_decision_reason_check;
update public.event_change_request
set decision_reason = 'Decision recorded before review reasons were introduced.'
where status = 'rejected' and nullif(btrim(decision_reason), '') is null;
alter table public.event_change_request
    add constraint event_change_request_decision_reason_check check (
        status <> 'rejected' or nullif(btrim(decision_reason), '') is not null
    );

-- Reassignment transfers review visibility to the coordinator currently in
-- charge of the event; the stored assigned_coordinator_id remains an audit
-- snapshot of who held it when the request was submitted.
drop policy if exists event_change_request_read_participants on public.event_change_request;
create policy event_change_request_read_participants on public.event_change_request
    for select to authenticated using (
        requested_by = (select auth.uid())
        or exists (
            select 1 from public.events e
            where e.event_id = event_change_request.event_id
              and e.event_coordinator_id = (select auth.uid())
        )
    );

-- Derived in the database so the queue, detail page, and approval modal cannot
-- disagree about which preparations are affected.
create or replace function public.event_change_request_impacts(p_changes jsonb)
returns jsonb language plpgsql immutable set search_path = public as $$
declare impacts text[] := array[]::text[];
begin
    if p_changes ?| array['start_datetime', 'end_datetime'] then
        impacts := impacts || array['venue_availability', 'equipment_reservations', 'event_schedule'];
    end if;
    if p_changes ? 'capacity_needed' then
        impacts := impacts || array['venue_capacity', 'venue_suitability'];
    end if;
    if p_changes ?| array['room_layout', 'required_facilities'] then
        if not ('venue_suitability' = any(impacts)) then impacts := array_append(impacts, 'venue_suitability'); end if;
    end if;
    if p_changes ?| array['need_wheelchair_accessibility', 'need_blind_accessibility'] then
        impacts := array_append(impacts, 'accessibility_arrangements');
        if not ('venue_suitability' = any(impacts)) then impacts := array_append(impacts, 'venue_suitability'); end if;
    end if;
    if p_changes ? 'equipment_requirements' then
        impacts := array_append(impacts, 'equipment_availability');
        if not ('equipment_reservations' = any(impacts)) then impacts := array_append(impacts, 'equipment_reservations'); end if;
    end if;
    return to_jsonb(impacts);
end;
$$;

-- Confirmed events normally reject edits. A reviewed request is the sole
-- exception. Non-important workflow edits do not invalidate safety approval;
-- important edits invalidate the prior approval data but keep the event's
-- lifecycle status separate from the request's decision status.
create or replace function public.guard_event_lifecycle()
returns trigger language plpgsql security definer set search_path = public as $$
declare
    blockers text[];
    change_request_workflow boolean := coalesce(current_setting('connectsphere.change_request_workflow', true), '') = 'true';
    non_important_workflow boolean := coalesce(current_setting('connectsphere.change_request_importance', true), '') = 'non_important';
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
    -- The request owns its Pending Review/Approved/Rejected lifecycle. Applying
    -- it must not copy that lifecycle onto the event or silently move the event
    -- to another stage. Preparation impacts remain visible in the request and
    -- its Critical Edit history entry for the coordinator to follow up.
    if TG_OP = 'UPDATE' and change_request_workflow then
        new.status := old.status;
    elsif new.status in ('planning', 'pending_safety_checks') then
        blockers := public.event_safety_check_blockers(new);
        if cardinality(blockers) > 0 then
            new.status := 'planning'::public.event_status;
        elsif new.safety_approved_at is not null
            and cardinality(public.event_confirmation_blockers(new)) = 0 then
            new.status := 'confirmed'::public.event_status;
        else
            new.status := 'pending_safety_checks'::public.event_status;
        end if;
    elsif new.status = 'confirmed' and cardinality(public.event_confirmation_blockers(new)) > 0 then
        new.status := case when cardinality(public.event_safety_check_blockers(new)) = 0
                           then 'pending_safety_checks'::public.event_status
                           else 'planning'::public.event_status end;
    end if;
    if TG_OP = 'UPDATE' then new.updated_at := clock_timestamp(); end if;
    return new;
end;
$$;

-- Submission now also accepts event name and description. Only requests whose
-- actual diff contains an important field wait for coordinator review.
create or replace function public.submit_event_change_request(
    p_event_id integer, p_reason text, p_proposed_values jsonb,
    p_expected_event_updated_at timestamptz, p_confirm_critical boolean default false
) returns jsonb language plpgsql security definer set search_path = public as $$
declare
    planned public.events;
    candidate public.events;
    saved public.event_change_request;
    calculated_changes jsonb := '{}'::jsonb;
    changed_key text;
    readable_fields jsonb;
    is_important boolean;
    allowed_fields constant text[] := array[
        'event_name', 'description', 'start_datetime', 'end_datetime',
        'capacity_needed', 'room_layout', 'required_facilities',
        'need_wheelchair_accessibility', 'need_blind_accessibility',
        'equipment_requirements'
    ];
    important_fields constant text[] := array[
        'start_datetime', 'end_datetime', 'capacity_needed', 'room_layout',
        'required_facilities', 'need_wheelchair_accessibility',
        'need_blind_accessibility', 'equipment_requirements'
    ];
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('event_organiser') then
        return jsonb_build_object('error', 'Only Event Organisers can submit event change requests.', 'status', 403);
    end if;
    if nullif(btrim(coalesce(p_reason, '')), '') is null then
        return jsonb_build_object('error', 'The change request could not be submitted because some details are invalid.',
            'errors', jsonb_build_object('reason', 'Please provide a reason for this change request'), 'status', 400);
    end if;
    if length(btrim(p_reason)) > 2000 then return jsonb_build_object('error', 'The reason must be 2000 characters or fewer.', 'status', 400); end if;
    if jsonb_typeof(p_proposed_values) is distinct from 'object' then return jsonb_build_object('error', 'Proposed changes must be a JSON object.', 'status', 400); end if;
    if exists (select 1 from jsonb_object_keys(p_proposed_values) key where not (key = any(allowed_fields))) then
        return jsonb_build_object('error', 'One or more proposed fields cannot be changed.', 'status', 400);
    end if;

    select * into planned from public.events where event_id = p_event_id for update;
    if not found or planned.event_organiser_id is distinct from auth.uid() then return jsonb_build_object('error', 'Event not found or access unavailable.', 'status', 404); end if;
    if planned.status not in ('planning', 'pending_safety_checks', 'confirmed') then return jsonb_build_object('error', 'This event can no longer accept change requests.', 'status', 409); end if;
    if planned.updated_at is distinct from p_expected_event_updated_at then return jsonb_build_object('error', 'This event changed while you were editing. Reload it and try again.', 'stale', true, 'status', 409); end if;
    if exists (select 1 from public.event_change_request where event_id = p_event_id and status = 'pending_review') then return jsonb_build_object('error', 'This event already has a change request pending review.', 'status', 409); end if;

    begin select * into candidate from jsonb_populate_record(planned, p_proposed_values);
    exception when others then return jsonb_build_object('error', 'One or more proposed values are invalid.', 'status', 400); end;
    for changed_key in select jsonb_object_keys(p_proposed_values) loop
        if (to_jsonb(candidate) -> changed_key) = 'null'::jsonb then return jsonb_build_object('error', 'Proposed values cannot be empty.', 'status', 400); end if;
        if (to_jsonb(candidate) -> changed_key) is distinct from (to_jsonb(planned) -> changed_key) then
            calculated_changes := calculated_changes || jsonb_build_object(changed_key,
                jsonb_build_object('from', to_jsonb(planned) -> changed_key, 'to', to_jsonb(candidate) -> changed_key));
        end if;
    end loop;
    if calculated_changes = '{}'::jsonb then return jsonb_build_object('error', 'Make at least one change before submitting.', 'status', 400); end if;
    if candidate.end_datetime <= candidate.start_datetime then return jsonb_build_object('error', 'The event must end after it starts.', 'status', 400); end if;
    if p_proposed_values ? 'start_datetime' and candidate.start_datetime <= now() then return jsonb_build_object('error', 'The event must start in the future.', 'status', 400); end if;
    if candidate.capacity_needed < 1 then return jsonb_build_object('error', 'Expected attendance must be at least 1.', 'status', 400); end if;

    is_important := calculated_changes ?| important_fields;
    if planned.status = 'confirmed' and is_important and not coalesce(p_confirm_critical, false) then
        select coalesce(jsonb_agg(case key
            when 'start_datetime' then 'Proposed start date and time' when 'end_datetime' then 'Proposed end date and time'
            when 'capacity_needed' then 'Expected attendance' when 'room_layout' then 'Room layout'
            when 'required_facilities' then 'Venue requirements' when 'need_wheelchair_accessibility' then 'Wheelchair accessibility'
            when 'need_blind_accessibility' then 'Accessibility for blind attendees' when 'equipment_requirements' then 'Equipment requirements'
            end order by key), '[]'::jsonb) into readable_fields
        from jsonb_object_keys(calculated_changes) key where key = any(important_fields);
        return jsonb_build_object('error', 'Review and confirm changes that may affect existing arrangements.', 'critical_fields', readable_fields, 'status', 409);
    end if;

    insert into public.event_change_request (
        event_id, requested_by, assigned_coordinator_id, reason, proposed_values,
        changes, expected_event_updated_at, importance, status, reviewed_at, reviewed_by
    ) values (
        planned.event_id, auth.uid(), planned.event_coordinator_id, btrim(p_reason),
        p_proposed_values, calculated_changes, planned.updated_at,
        case when is_important then 'important' else 'non_important' end,
        case when is_important
            then 'pending_review'::public.event_change_request_status
            else 'approved'::public.event_change_request_status
        end,
        case when is_important then null else clock_timestamp() end,
        case when is_important then null else auth.uid() end
    ) returning * into saved;

    if is_important then
        insert into public.notification (recipient_id, event_change_request_id, notification_type, message)
        values (planned.event_coordinator_id, saved.event_change_request_id, 'event_change_request_submitted',
                'A change request for ' || planned.event_name || ' is awaiting your review.');
    else
        perform set_config('connectsphere.change_request_workflow', 'true', true);
        perform set_config('connectsphere.change_request_importance', 'non_important', true);
        update public.events set event_name = candidate.event_name, description = candidate.description
        where event_id = planned.event_id returning * into planned;
        insert into public.event_activity (event_id, changed_by, change_type, changes, event_change_request_id)
        values (planned.event_id, auth.uid(), 'edit', calculated_changes, saved.event_change_request_id);
    end if;

    return jsonb_build_object(
        'message', case when is_important then 'Event change request submitted successfully.' else 'Non-critical changes were recorded and applied successfully.' end,
        'change_request', to_jsonb(saved)
    );
end;
$$;

create or replace function public.event_change_requests_for_coordinator(p_status text default null)
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare result jsonb;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('event_coordinator') then return jsonb_build_object('error', 'Only Event Coordinators can review event change requests.', 'status', 403); end if;
    if p_status is not null and p_status not in ('pending_review', 'approved', 'rejected') then return jsonb_build_object('error', 'Choose a valid change request status.', 'status', 400); end if;
    select coalesce(jsonb_agg(
        to_jsonb(c) || jsonb_build_object(
            'event_name', e.event_name,
            'changed_fields', (select coalesce(jsonb_agg(key order by key), '[]'::jsonb) from jsonb_object_keys(c.changes) key),
            'preparation_impacts', public.event_change_request_impacts(c.changes)
        ) order by (c.status = 'pending_review') desc, c.submitted_at desc
    ), '[]'::jsonb) into result
    from public.event_change_request c join public.events e on e.event_id = c.event_id
    where e.event_coordinator_id = auth.uid() and (p_status is null or c.status::text = p_status);
    return jsonb_build_object('change_requests', result);
end;
$$;

-- Organisers keep a complete history after a coordinator decides a request.
-- This is separate from the eligible-event picker: a decided request must
-- remain visible even when its event later reaches a terminal lifecycle state.
create or replace function public.event_change_requests_for_organiser()
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare result jsonb;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('event_organiser') then return jsonb_build_object('error', 'Only Event Organisers can view their event change requests.', 'status', 403); end if;
    select coalesce(jsonb_agg(
        to_jsonb(c) || jsonb_build_object(
            'event_name', e.event_name,
            'changed_fields', (select coalesce(jsonb_agg(key order by key), '[]'::jsonb) from jsonb_object_keys(c.changes) key)
        ) order by c.submitted_at desc
    ), '[]'::jsonb) into result
    from public.event_change_request c
    join public.events e on e.event_id = c.event_id
    where c.requested_by = auth.uid();
    return jsonb_build_object('change_requests', result);
end;
$$;

create or replace function public.event_change_request_for_review(p_request_id bigint)
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare result jsonb;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('event_coordinator') then return jsonb_build_object('error', 'Only Event Coordinators can review event change requests.', 'status', 403); end if;
    select to_jsonb(c) || jsonb_build_object('event_name', e.event_name) into result
    from public.event_change_request c join public.events e on e.event_id = c.event_id
    where c.event_change_request_id = p_request_id and e.event_coordinator_id = auth.uid();
    if result is null then return jsonb_build_object('error', 'Change request not found or access unavailable.', 'status', 404); end if;
    return jsonb_build_object('change_request', result, 'preparation_impacts', public.event_change_request_impacts(result->'changes'));
end;
$$;

create or replace function public.review_event_change_request(
    p_request_id bigint, p_decision text, p_reason text default null
) returns jsonb language plpgsql security definer set search_path = public as $$
declare
    change_request public.event_change_request;
    planned public.events;
    candidate public.events;
    decision text := lower(btrim(coalesce(p_decision, '')));
    decision_reason_value text := nullif(btrim(coalesce(p_reason, '')), '');
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('event_coordinator') then return jsonb_build_object('error', 'Only Event Coordinators can review event change requests.', 'status', 403); end if;
    if decision not in ('approve', 'reject') then return jsonb_build_object('error', 'Choose Approve or Reject.', 'status', 400); end if;
    if decision = 'reject' and decision_reason_value is null then return jsonb_build_object('error', 'Check the review decision.', 'errors', jsonb_build_object('reason', 'Please provide a reason for rejecting this change request.'), 'status', 400); end if;
    if decision_reason_value is not null and length(decision_reason_value) > 2000 then return jsonb_build_object('error', 'The decision reason must be 2000 characters or fewer.', 'status', 400); end if;

    select * into change_request from public.event_change_request where event_change_request_id = p_request_id for update;
    if not found then return jsonb_build_object('error', 'Change request not found or access unavailable.', 'status', 404); end if;
    select * into planned from public.events where event_id = change_request.event_id for update;
    if not found or planned.event_coordinator_id is distinct from auth.uid() then return jsonb_build_object('error', 'Change request not found or access unavailable.', 'status', 404); end if;
    if change_request.status <> 'pending_review' or change_request.importance <> 'important' then return jsonb_build_object('error', 'This change request no longer requires a decision.', 'status', 409); end if;
    if planned.status not in ('planning', 'pending_safety_checks', 'confirmed') then return jsonb_build_object('error', 'This event can no longer be changed.', 'status', 409); end if;

    if decision = 'approve' then
        if planned.updated_at is distinct from change_request.expected_event_updated_at then
            return jsonb_build_object('error', 'The event changed after this request was submitted. Reject this request and ask the organiser to submit an updated request.', 'stale', true, 'status', 409);
        end if;
        begin select * into candidate from jsonb_populate_record(planned, change_request.proposed_values);
        exception when others then return jsonb_build_object('error', 'The proposed values can no longer be applied.', 'status', 409); end;
        -- Keep the event write, decision, and required Critical Edit entry in
        -- one subtransaction. If an existing arrangement guard refuses the
        -- event write, none of the three is left half-applied and the caller
        -- receives the useful conflict instead of a generic service outage.
        begin
            perform set_config('connectsphere.change_request_workflow', 'true', true);
            perform set_config('connectsphere.change_request_importance', 'important', true);
            perform set_config('connectsphere.safety_workflow', 'true', true);
            update public.events set
                event_name = candidate.event_name, description = candidate.description,
                start_datetime = candidate.start_datetime, end_datetime = candidate.end_datetime,
                capacity_needed = candidate.capacity_needed, room_layout = candidate.room_layout,
                required_facilities = candidate.required_facilities,
                need_wheelchair_accessibility = candidate.need_wheelchair_accessibility,
                need_blind_accessibility = candidate.need_blind_accessibility,
                equipment_requirements = candidate.equipment_requirements
            where event_id = planned.event_id returning * into planned;
            update public.event_change_request set status = 'approved', reviewed_at = clock_timestamp(),
                reviewed_by = auth.uid(), decision_reason = decision_reason_value
            where event_change_request_id = p_request_id returning * into change_request;
            insert into public.event_activity (event_id, changed_by, change_type, changes, event_change_request_id)
            values (planned.event_id, auth.uid(), 'critical_edit', change_request.changes, change_request.event_change_request_id);
        exception
            when check_violation or foreign_key_violation or not_null_violation or insufficient_privilege then
                return jsonb_build_object('error', sqlerrm, 'status', 409);
            when others then
                return jsonb_build_object(
                    'error', 'The approved changes could not be applied. Refresh the request and try again.',
                    'status', 409
                );
        end;
    else
        update public.event_change_request set status = 'rejected', reviewed_at = clock_timestamp(),
            reviewed_by = auth.uid(), decision_reason = decision_reason_value
        where event_change_request_id = p_request_id returning * into change_request;
    end if;

    -- A missing or incompatible notification row must not undo a decision that
    -- has already been recorded. The request itself remains the source of truth
    -- and is visible to the organiser.
    begin
        insert into public.notification (recipient_id, event_change_request_id, notification_type, message)
        values (change_request.requested_by, change_request.event_change_request_id,
            'event_change_request_' || change_request.status::text,
            'Your change request for ' || planned.event_name || ' was ' || change_request.status::text ||
            case when decision_reason_value is null then '.' else '. Reason: ' || decision_reason_value end);
    exception when foreign_key_violation or check_violation or not_null_violation then
        null;
    end;
    return jsonb_build_object(
        'message', case when decision = 'approve' then 'Change request approved and event information updated.' else 'Change request rejected. The event was not changed.' end,
        'change_request', to_jsonb(change_request), 'event', to_jsonb(planned)
    );
end;
$$;

revoke all on function public.event_change_request_impacts(jsonb),
    public.event_change_requests_for_coordinator(text),
    public.event_change_requests_for_organiser(),
    public.event_change_request_for_review(bigint),
    public.review_event_change_request(bigint, text, text) from public, anon;
grant execute on function public.event_change_requests_for_coordinator(text),
    public.event_change_requests_for_organiser(),
    public.event_change_request_for_review(bigint),
    public.review_event_change_request(bigint, text, text) to authenticated;

notify pgrst, 'reload schema';
commit;
