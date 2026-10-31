-- Restrict Event Organiser change requests to Planning events.
-- Safe to run in the Supabase SQL Editor: it replaces only two RPC functions.
begin;

create or replace function public.eligible_event_change_request_events()
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare result jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_organiser') then
        return jsonb_build_object('error', 'Only Event Organisers can submit event change requests.', 'status', 403);
    end if;

    select coalesce(jsonb_agg(to_jsonb(e) order by e.start_datetime), '[]'::jsonb)
      into result
      from public.events e
     where e.event_organiser_id = auth.uid()
       and e.status = 'planning'
       and not exists (
           select 1
             from public.event_change_request c
            where c.event_id = e.event_id
              and c.status = 'pending_review'
       );

    return jsonb_build_object('events', result);
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
    if planned.status <> 'planning' then
        return jsonb_build_object('error', 'Event change requests can only be submitted while the event is in Planning.', 'status', 409);
    end if;
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

notify pgrst, 'reload schema';
commit;
