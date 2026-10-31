-- ConnectSphere EMS: Notify about event change requests, equipment requests and
-- events submitted for safety review.
-- Run in the Supabase SQL Editor after 054.
--
-- 1. Event change requests (053 submits, 049 reviews). Submitting inserts the
--    request: pending review, or already approved when only the name or
--    description changes. The Organiser and the assigned Coordinator are told
--    what was asked; a review then tells the Organiser the outcome, and an
--    approval tells the event's staff what changed.
-- 2. Equipment requests: the Coordinator inserts one (pending); the event's
--    Technical Support Staff accepts or rejects it (036; the app does not offer
--    partial acceptance). Both are told on submission, and the Coordinator of
--    the decision.
-- 3. submit_event_for_safety_checks (048), unchanged except that the Safety
--    Officer's notification now gives the event's date; the Coordinator is
--    told when the safety review is approved, or rejected or sent back with
--    changes requested (both return the event to Planning).

begin;

create or replace function public.event_change_value(p_key text, p_value jsonb) returns text
language sql stable set search_path = public as $$
    select case
        when p_key like '%datetime' then to_char((p_value #>> '{}')::timestamptz at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI')
        when jsonb_typeof(p_value) = 'boolean' then case when (p_value #>> '{}')::boolean then 'Yes' else 'No' end
        when jsonb_typeof(p_value) = 'array' then coalesce((select string_agg(case when jsonb_typeof(item) = 'object'
                then format('%s ×%s', item ->> 'equipment_type', coalesce(item ->> 'quantity', '1'))
                else replace(item #>> '{}', '_', ' ') end, ', ') from jsonb_array_elements(p_value) item), 'none')
        -- Only set values (room layouts, facilities) are words joined by underscores; free text is shown as typed.
        when p_key = 'room_layout' then replace(p_value #>> '{}', '_', ' ')
        else p_value #>> '{}'
    end;
$$;

-- "Start: 05 Jan 2027 10:00 → 06 Jan 2027 10:00; Expected attendance: 40 → 60"
create or replace function public.event_change_summary(p_changes jsonb) returns text
language sql stable set search_path = public as $$
    select string_agg(format('%s: %s → %s',
        case key when 'event_name' then 'Event name' when 'start_datetime' then 'Start'
                 when 'end_datetime' then 'End' when 'capacity_needed' then 'Expected attendance'
                 when 'room_layout' then 'Room layout' when 'equipment_requirements' then 'Equipment requirements'
                 when 'required_facilities' then 'Venue requirements'
                 when 'need_wheelchair_accessibility' then 'Wheelchair accessibility'
                 when 'need_blind_accessibility' then 'Accessibility for blind attendees'
                 else initcap(replace(key, '_', ' ')) end,
        public.event_change_value(key, change -> 'from'), public.event_change_value(key, change -> 'to')), '; ' order by key)
    from jsonb_each(p_changes) as c(key, change);
$$;

create or replace function public.notify_event_change_request() returns trigger
language plpgsql security definer set search_path = public as $$
declare
    planned public.events;
    summary text := public.event_change_summary(new.changes);
    staff uuid;
begin
    select * into planned from public.events where event_id = new.event_id;
    if tg_op = 'INSERT' then
        perform public.notify_user(new.requested_by, 'event_change_submitted', 'Event change request submitted',
            format('Your change request for %s has been submitted %s. Changes: %s', planned.event_name,
                   case when new.status = 'approved' then 'and applied' else 'and is awaiting review' end, summary),
            '/event-change-requests/new');
        perform public.notify_user(new.assigned_coordinator_id, 'event_change_submitted', 'New event change request',
            format('%s requested changes to %s%s. Changes: %s. Reason: %s',
                   coalesce((select name from public.users where user_id = new.requested_by), 'The Event Organiser'),
                   planned.event_name, case when new.status = 'approved' then ' (applied, no review needed)' else '' end,
                   summary, new.reason),
            case when new.status = 'approved' then '/events/' || new.event_id
                 else '/review-event-change-requests/' || new.event_change_request_id end);
    elsif new.status in ('approved', 'rejected') and old.status is distinct from new.status then
        perform public.notify_user(new.requested_by, 'event_change_' || new.status, 'Event change request ' || new.status,
            format('Your change request for %s has been %s by %s.%s', planned.event_name, new.status,
                   coalesce((select name from public.users where user_id = new.reviewed_by), 'the Event Coordinator'),
                   case when new.status = 'rejected' then ' Reason: ' || coalesce(new.decision_reason, 'none given')
                        else ' The event has been updated.' end),
            '/event-change-requests/new');
    end if;
    -- Approved changes, whether reviewed or applied straight away, reach the event's staff.
    if new.status = 'approved' and (tg_op = 'INSERT' or old.status is distinct from new.status) then
        foreach staff in array array_remove(array[planned.venue_staff_id, planned.technical_support_id, planned.safety_officer_id], null) loop
            perform public.notify_user(staff, 'event_change_approved', 'Event changes approved',
                format('Changes to %s have been approved. Changes: %s', planned.event_name, summary),
                '/events/' || new.event_id);
        end loop;
    end if;
    return null;
end;
$$;
drop trigger if exists notify_event_change_request on public.event_change_request;
create trigger notify_event_change_request after insert or update of status on public.event_change_request
    for each row execute function public.notify_event_change_request();

create or replace function public.notify_equipment_request() returns trigger
language plpgsql security definer set search_path = public as $$
declare
    planned public.events;
    item text := format('%s × %s', new.quantity, new.equipment_type);
begin
    select * into planned from public.events where event_id = new.event_id;
    if tg_op = 'INSERT' then
        perform public.notify_user(new.requested_by, 'equipment_request_submitted', 'Equipment request submitted',
            format('Your equipment request for %s for %s has been submitted. Status: pending Technical Support review.',
                   item, planned.event_name),
            '/equipment-requests');
        perform public.notify_user(planned.technical_support_id, 'equipment_request_submitted', 'New equipment request',
            format('%s requested %s for %s (%s – %s SGT). Technical requirements: %s. Status: pending review.',
                   coalesce((select name from public.users where user_id = new.requested_by), 'The Event Coordinator'),
                   item, planned.event_name,
                   to_char(planned.start_datetime at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
                   to_char(planned.end_datetime at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
                   coalesce(new.technical_requirements, 'none')),
            '/equipment');
    elsif new.status in ('accepted', 'rejected') and old.status is distinct from new.status then
        perform public.notify_user(new.requested_by, 'equipment_request_' || new.status, 'Equipment request ' || new.status,
            format('Your equipment request for %s for %s has been %s by %s.%s', item, planned.event_name, new.status,
                   coalesce((select name from public.users where user_id = new.reviewed_by), 'Technical Support'),
                   case when new.status = 'rejected' then ' Reason: ' || coalesce(new.reason_for_rejection, 'none given')
                        else '' end),
            '/equipment-requests');
    end if;
    return null;
end;
$$;
drop trigger if exists notify_equipment_request on public.equipment_request;
create trigger notify_equipment_request after insert or update of status on public.equipment_request
    for each row execute function public.notify_equipment_request();

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
        format('%s (%s – %s SGT) has been submitted for safety checks by %s.', coalesce(saved.event_name, 'An unnamed event'),
               to_char(saved.start_datetime at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
               to_char(saved.end_datetime at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'), coordinator),
        '/operational-safety-reviews/' || saved.event_id);
    return jsonb_build_object('event', to_jsonb(saved),
        'message', 'Event submitted for safety checks. The assigned Safety Officer has been notified.');
end;
$$;

-- record_safety_decision (053) inserts the decision, so a trigger tells the
-- event's Coordinator when the Safety Officer approves it, or rejects it or
-- requests changes, either of which returns the event to Planning.
create or replace function public.notify_safety_decision() returns trigger
language plpgsql security definer set search_path = public as $$
declare planned public.events;
begin
    select * into planned from public.events where event_id = new.event_id;
    perform public.notify_user(planned.event_coordinator_id, 'safety_review_' || new.outcome,
        case new.outcome when 'changes_requested' then 'Safety changes requested' else 'Safety review ' || new.outcome end,
        format('The safety review for %s (%s – %s SGT) has been %s by %s.%s', planned.event_name,
               to_char(planned.start_datetime at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
               to_char(planned.end_datetime at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
               case new.outcome when 'changes_requested' then 'sent back with changes requested' else new.outcome end,
               coalesce((select name from public.users where user_id = new.safety_officer_id), 'the Safety Officer'),
               case when new.outcome <> 'approved' then ' Remarks: ' || new.remarks || ' The event has returned to Planning.'
                    else coalesce(' Remarks: ' || new.remarks, '') end),
        '/events/' || new.event_id);
    return null;
end;
$$;
drop trigger if exists notify_safety_decision on public.operational_safety_decision;
create trigger notify_safety_decision after insert on public.operational_safety_decision
    for each row execute function public.notify_safety_decision();

revoke all on function public.notify_safety_decision(), public.notify_event_change_request(), public.notify_equipment_request(),
    public.event_change_summary(jsonb), public.event_change_value(text, jsonb) from public, anon, authenticated;

commit;
