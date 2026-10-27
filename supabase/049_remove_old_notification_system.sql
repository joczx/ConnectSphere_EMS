-- ConnectSphere EMS: Remove the old notification system
-- Run in the Supabase SQL Editor after 048 (048_submit_for_safety_checks.sql). Already applied.
--
-- 046 replaced the old notification system with public.notifications and left
-- public.notification discarding whatever was still written to it. This removes
-- those leftover writes and then the old table itself.
--
-- Each function below is the latest version from the migration named beside it,
-- unchanged except that its write to public.notification is removed:
--   assign_event_request_coordinator (029), reassign_submitted_request_coordinator
--   and reassign_event_coordinator_for_lead (030), record_safety_decision (035),
--   submit_event_change_request and review_event_change_request (038),
--   review_venue_booking (028), block_venue (041).
-- The tentative-hold functions (042) no longer call notify_venue_booking, which
-- is dropped; the expiry job only expires holds.
--
-- These events notify no one until each is rebuilt on notify_user() /
-- notify_role() (046). Coordinator assignment already is (047), by trigger.

begin;

create or replace function public.assign_event_request_coordinator(
    p_event_request_id bigint,
    p_coordinator_id uuid
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    assigned_request public.event_request;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator_lead') then
        return jsonb_build_object(
            'error', 'Only Event Coordinator Leads can assign event coordinators.',
            'status', 403
        );
    end if;
    if p_coordinator_id is null or not exists (
        select 1
        from public.user_roles ur
        join public.roles ro on ro.role_id = ur.role_id
        where ur.user_id = p_coordinator_id
          and replace(lower(trim(ro.role_name)), ' ', '_') = 'event_coordinator'
    ) then
        return jsonb_build_object(
            'error', 'Choose a user with the Event Coordinator role.',
            'status', 400
        );
    end if;

    select * into assigned_request
    from public.event_request
    where event_request_id = p_event_request_id
    for update;

    if not found then
        return jsonb_build_object('error', 'Event request not found.', 'status', 404);
    end if;
    if assigned_request.status <> 'submitted'::public.event_status
       or assigned_request.event_coordinator_id is not null then
        return jsonb_build_object(
            'error', 'This request is no longer available for assignment. Refresh the queue.',
            'status', 409
        );
    end if;

    update public.event_request
    set event_coordinator_id = p_coordinator_id,
        updated_at = now()
    where event_request_id = p_event_request_id
    returning * into assigned_request;

    update public.events
    set event_coordinator_id = p_coordinator_id
    where event_request_id = p_event_request_id;


    return jsonb_build_object(
        'message', 'Event Coordinator assigned successfully.',
        'event_request', to_jsonb(assigned_request)
    );
end;
$$;

create or replace function public.reassign_submitted_request_coordinator(
    p_event_request_id bigint,
    p_coordinator_id uuid
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    assigned_request public.event_request;
    previous_coordinator_id uuid;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator_lead') then
        return jsonb_build_object(
            'error', 'Only Event Coordinator Leads can reassign event coordinators.',
            'status', 403
        );
    end if;
    if p_coordinator_id is null or not exists (
        select 1
        from public.user_roles ur
        join public.roles ro on ro.role_id = ur.role_id
        where ur.user_id = p_coordinator_id
          and replace(lower(trim(ro.role_name)), ' ', '_') = 'event_coordinator'
    ) then
        return jsonb_build_object(
            'error', 'Choose a user with the Event Coordinator role.',
            'status', 400
        );
    end if;

    select * into assigned_request
    from public.event_request
    where event_request_id = p_event_request_id
    for update;

    if not found then
        return jsonb_build_object('error', 'Event request not found.', 'status', 404);
    end if;
    if assigned_request.status <> 'submitted'::public.event_status then
        return jsonb_build_object(
            'error', 'Only submitted event requests can be reassigned.',
            'status', 409
        );
    end if;

    previous_coordinator_id := assigned_request.event_coordinator_id;
    if previous_coordinator_id is distinct from p_coordinator_id then
        update public.event_request
        set event_coordinator_id = p_coordinator_id,
            updated_at = now()
        where event_request_id = p_event_request_id
        returning * into assigned_request;

    end if;

    return jsonb_build_object(
        'message', 'Event Coordinator reassigned successfully.',
        'event_request', to_jsonb(assigned_request)
    );
end;
$$;

create or replace function public.reassign_event_coordinator_for_lead(
    p_event_id integer,
    p_coordinator_id uuid
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    assigned_event public.events;
    previous_coordinator_id uuid;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator_lead') then
        return jsonb_build_object(
            'error', 'Only Event Coordinator Leads can reassign events.',
            'status', 403
        );
    end if;
    if p_coordinator_id is null or not exists (
        select 1
        from public.user_roles ur
        join public.roles ro on ro.role_id = ur.role_id
        where ur.user_id = p_coordinator_id
          and replace(lower(trim(ro.role_name)), ' ', '_') = 'event_coordinator'
    ) then
        return jsonb_build_object(
            'error', 'Choose a user with the Event Coordinator role.',
            'status', 400
        );
    end if;

    select * into assigned_event
    from public.events
    where event_id = p_event_id
    for update;

    if not found then
        return jsonb_build_object('error', 'Event not found.', 'status', 404);
    end if;
    if assigned_event.status::text not in (
        'planning',
        'pending_safety_checks',
        'confirmed'
    ) then
        return jsonb_build_object(
            'error', 'This event is no longer available for reassignment.',
            'status', 409
        );
    end if;

    previous_coordinator_id := assigned_event.event_coordinator_id;
    if previous_coordinator_id is distinct from p_coordinator_id then
        update public.events
        set event_coordinator_id = p_coordinator_id
        where event_id = p_event_id
        returning * into assigned_event;

        if assigned_event.event_request_id is not null then
            update public.event_request
            set event_coordinator_id = p_coordinator_id,
                updated_at = now()
            where event_request_id = assigned_event.event_request_id;

        end if;
    end if;

    return jsonb_build_object(
        'message', 'Event Coordinator reassigned successfully.',
        'event', to_jsonb(assigned_event)
    );
end;
$$;

create or replace function public.record_safety_decision(
    p_event_id integer, p_outcome text, p_remarks text, p_affected_arrangements text[]
) returns jsonb language plpgsql security definer set search_path = public as $$
declare planned public.events; saved public.operational_safety_decision; outcome text := lower(btrim(coalesce(p_outcome, '')));
        remarks text := nullif(btrim(coalesce(p_remarks, '')), ''); affected text[] := coalesce(p_affected_arrangements, array[]::text[]); note text;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_safety_officer_role() then return jsonb_build_object('error', 'Only Safety Officers can record operational safety decisions.', 'status', 403); end if;
    if outcome not in ('approved', 'rejected', 'changes_requested') then return jsonb_build_object('error', 'Choose Approve, Reject, or Request changes.', 'status', 400); end if;
    if outcome <> 'approved' and remarks is null then return jsonb_build_object('error', 'Remarks are required when rejecting or requesting changes.', 'status', 400); end if;
    if remarks is not null and length(remarks) > 2000 then return jsonb_build_object('error', 'Remarks must be 2000 characters or fewer.', 'status', 400); end if;
    if not (affected <@ array['venue', 'technical']::text[]) then return jsonb_build_object('error', 'Affected arrangements must be venue or technical.', 'status', 400); end if;

    select * into planned from public.events where event_id = p_event_id for update;
    if not found or planned.status <> 'pending_safety_checks' then return jsonb_build_object('error', 'Event not found or no longer awaiting safety checks.', 'status', 404); end if;
    if outcome = 'approved' and cardinality(public.event_safety_check_blockers(planned)) > 0 then
        return jsonb_build_object('error', 'The event arrangements changed and must be completed before approval.', 'status', 409);
    end if;
    if planned.event_coordinator_id is null then return jsonb_build_object('error', 'Assign an Event Coordinator before recording a safety decision.', 'status', 409); end if;

    insert into public.operational_safety_decision (event_id, safety_officer_id, outcome, remarks, affected_arrangements)
    values (planned.event_id, auth.uid(), outcome, remarks, affected) returning * into saved;
    perform set_config('connectsphere.safety_workflow', 'true', true);
    if outcome = 'approved' then
        update public.events set status = 'confirmed', safety_rework_required = false,
            safety_rework_arrangements = array[]::text[], safety_approved_at = saved.created_at
        where event_id = planned.event_id returning * into planned;
        note := case when planned.status = 'confirmed' then 'Safety arrangements approved. The event is confirmed.'
                     else 'Safety arrangements approved. The event will be confirmed once its remaining readiness checks are complete.' end;
    else
        update public.events set status = 'planning', safety_rework_required = true,
            safety_rework_requested_at = saved.created_at, safety_rework_arrangements = affected,
            safety_approved_at = null
        where event_id = planned.event_id returning * into planned;
        note := case when outcome = 'rejected' then 'Safety arrangements rejected. Address the remarks before proceeding.'
                     else 'Safety changes requested. Address the remarks before proceeding.' end;
    end if;
    return jsonb_build_object('event', to_jsonb(planned), 'decision', to_jsonb(saved), 'message', note);
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

    return jsonb_build_object(
        'message', case when decision = 'approve' then 'Change request approved and event information updated.' else 'Change request rejected. The event was not changed.' end,
        'change_request', to_jsonb(change_request), 'event', to_jsonb(planned)
    );
end;
$$;

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

    if not is_important then
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

create or replace function public.review_venue_booking(
    p_booking_id uuid, p_outcome text, p_comments text
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    pending public.venue_booking_requests;
    decided public.venue_booking_requests;
    planned public.events;
    chosen public.venues;
    shortfalls text[];
    blocking jsonb;
    comments text := nullif(trim(coalesce(p_comments, '')), '');
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can approve or reject venue bookings.', 'status', 403);
    end if;
    if p_outcome is null or p_outcome not in ('approved', 'rejected') then
        return jsonb_build_object('error', 'Choose Approve or Reject.', 'status', 400);
    end if;
    if p_outcome = 'rejected' and comments is null then
        return jsonb_build_object(
            'error', 'Enter a reason for rejecting this request.',
            'errors', jsonb_build_object('comments', 'A reason is required when rejecting.'),
            'status', 400
        );
    end if;
    if comments is not null and length(comments) > 2000 then
        return jsonb_build_object('error', 'Comments must be 2000 characters or fewer.', 'status', 400);
    end if;

    select * into pending from public.venue_booking_requests where booking_id = p_booking_id;
    if not found then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    if pending.status <> 'submitted' then
        return jsonb_build_object(
            'error', 'This request has already been ' || pending.status || '.', 'status', 409
        );
    end if;

    if p_outcome = 'approved' then
        -- FOR SHARE: no edit to this venue can commit until this approval has,
        -- so the venue checked below is the venue booked.
        select * into chosen from public.venues where venue_id = pending.venue_id for share;
        if not found or chosen.deleted_at is not null then
            return jsonb_build_object(
                'error', 'This venue has been removed from the catalogue, so it can no longer be approved. Reject the request instead.',
                'status', 409
            );
        end if;

        if pending.event_id is not null then
            -- And the same for the event: a critical edit waits for this.
            select * into planned from public.events where event_id = pending.event_id for share;
            if found then
                if planned.status is distinct from 'planning'::public.event_status then
                    return jsonb_build_object(
                        'error', 'This event is ' || planned.status || ', so its venue can no longer be approved. Reject the request instead.',
                        'status', 409
                    );
                end if;
                if pending.starts_at is distinct from planned.start_datetime
                    or pending.ends_at is distinct from planned.end_datetime
                    or (planned.capacity_needed is not null
                        and pending.attendance is distinct from planned.capacity_needed) then
                    return jsonb_build_object(
                        'error', 'The event''s date, time or attendance has changed since this was requested, so approving it would book the wrong period. Reject it so the Event Coordinator can request again.',
                        'status', 409
                    );
                end if;
                shortfalls := public.venue_shortfalls_for_event(chosen, planned);
                if cardinality(shortfalls) > 0 then
                    return jsonb_build_object(
                        'error', 'The event has changed since this was requested, and the venue no longer meets its requirements. Reject the request instead.',
                        'unmet_requirements', to_jsonb(shortfalls),
                        'status', 409
                    );
                end if;
            end if;
        end if;

        blocking := public.venue_booking_conflicts(
            pending.venue_id, pending.starts_at, pending.ends_at, pending.booking_id, true
        );
        if jsonb_array_length(blocking) > 0 then
            return jsonb_build_object(
                'error', 'This venue is already booked for an overlapping period, so this request can only be rejected.',
                'conflicts', blocking,
                'status', 409
            );
        end if;
    end if;

    begin
        update public.venue_booking_requests
        set status = p_outcome,
            reviewed_by = auth.uid(),
            reviewed_at = now(),
            review_comments = comments
        where booking_id = p_booking_id and status = 'submitted'
        returning * into decided;
    exception when exclusion_violation then
        return jsonb_build_object(
            'error', 'Another booking for this venue at an overlapping time was approved just now, so this request can only be rejected.',
            'conflicts', public.venue_booking_conflicts(
                pending.venue_id, pending.starts_at, pending.ends_at, pending.booking_id, true
            ),
            'status', 409
        );
    end;

    if decided.booking_id is null then
        return jsonb_build_object('error', 'Another member of Venue Staff decided this request first.', 'status', 409);
    end if;



    return jsonb_build_object('booking', to_jsonb(decided));
end;
$$;

create or replace function public.block_venue(
    p_venue_id uuid, p_starts timestamptz, p_ends timestamptz, p_reason text
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    block public.venue_blocks;
    venue text;
    reason text := trim(coalesce(p_reason, ''));
    affected jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can mark a venue unavailable.', 'status', 403);
    end if;
    select venue_name into venue from public.venues where venue_id = p_venue_id and deleted_at is null;
    if not found then
        return jsonb_build_object('error', 'Venue not found or access unavailable.', 'status', 404);
    end if;
    if p_starts is null or p_ends is null or p_ends <= p_starts then
        return jsonb_build_object('error', 'The end must be after the start.', 'status', 400);
    end if;
    if reason = '' or length(reason) > 500 then
        return jsonb_build_object('error', 'Enter a reason (maximum 500 characters).', 'status', 400);
    end if;

    insert into public.venue_blocks (venue_id, starts_at, ends_at, reason, created_by)
    values (p_venue_id, p_starts, p_ends, reason, auth.uid()) returning * into block;

    with cancelled as (
        update public.venue_booking_requests b
        set status = 'cancelled', cancelled_at = now(), cancellation_reason = 'Venue unavailable: ' || reason
        where b.venue_id = p_venue_id and b.status in ('submitted', 'approved')
          and tstzrange(b.occupied_from, b.occupied_until, '[)') && tstzrange(p_starts, p_ends, '[)')
        returning b.*
    )
    select coalesce(jsonb_agg(jsonb_build_object(
        'booking_id', c.booking_id, 'event_id', c.event_id, 'event_name', c.event_name,
        'starts_at', c.starts_at, 'ends_at', c.ends_at) order by c.starts_at), '[]'::jsonb)
    into affected from cancelled c;

    return jsonb_build_object('block', to_jsonb(block), 'affected', affected);
end;
$$;

create or replace function public.hold_venue_booking(p_booking_id uuid, p_expires_at timestamptz)
returns jsonb
language plpgsql security definer set search_path = public as $$
declare booking public.venue_booking_requests;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can place a tentative hold.', 'status', 403);
    end if;
    select * into booking from public.venue_booking_requests where booking_id = p_booking_id for update;
    if not found then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    if booking.status <> 'submitted' or booking.hold_expires_at is not null then
        return jsonb_build_object('error', 'Only a pending request without a hold can be held.', 'status', 409);
    end if;
    if p_expires_at is null or p_expires_at <= now() or p_expires_at >= booking.starts_at then
        return jsonb_build_object('error', 'Choose an expiry in the future and before the booking starts.',
                                  'errors', jsonb_build_object('expires_at', 'A valid expiry is required.'), 'status', 400);
    end if;
    if jsonb_array_length(public.venue_booking_conflicts(booking.venue_id, booking.starts_at, booking.ends_at,
                                                         booking.booking_id, true)) > 0 then
        return jsonb_build_object('error', 'The venue is already booked, held or unavailable at this time.', 'status', 409);
    end if;
    update public.venue_booking_requests set hold_expires_at = p_expires_at
    where booking_id = p_booking_id returning * into booking;
    return jsonb_build_object('booking', to_jsonb(booking));
end;
$$;

create or replace function public.release_venue_hold(p_booking_id uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare booking public.venue_booking_requests;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can release a tentative hold.', 'status', 403);
    end if;
    update public.venue_booking_requests set hold_expires_at = null
    where booking_id = p_booking_id and status = 'submitted' and hold_expires_at > now()
    returning * into booking;
    if not found then
        return jsonb_build_object('error', 'This request has no active hold.', 'status', 409);
    end if;
    return jsonb_build_object('booking', to_jsonb(booking));
end;
$$;

-- Run every minute by pg_cron (042).
create or replace function public.expire_venue_holds()
returns void
language sql security definer set search_path = public as $$
    update public.venue_booking_requests set status = 'expired', expired_at = now()
    where status = 'submitted' and hold_expires_at <= now();
$$;

drop function if exists public.notify_venue_booking(public.venue_booking_requests, text, text);
drop table if exists public.notification cascade;
drop function if exists public.discard_legacy_notification();

commit;
