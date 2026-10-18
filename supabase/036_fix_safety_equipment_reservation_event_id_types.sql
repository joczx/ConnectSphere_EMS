-- Repair the stored definitions already applied by 030, 034, and 035.
-- All involved event_id columns are integer, so reservations must be compared
-- to events as integers rather than casting event IDs to text.
begin;

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
    if nullif(btrim(p_event.registration_needs), '') is not null and not p_event.registration_ready then
        blockers := array_append(blockers, 'The Event Coordinator must confirm registration readiness.');
    end if;
    return blockers;
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
                where r.event_id = event_row.event_id
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

create or replace function public.event_safety_check_blockers(p_event public.events)
returns text[] language plpgsql volatile security definer set search_path = public as $$
declare blockers text[]; requirements text[] := coalesce(p_event.safety_rework_arrangements, array[]::text[]);
begin
    blockers := public.event_confirmation_blockers(p_event);
    blockers := array_remove(blockers, 'An Event Coordinator must be assigned.');
    blockers := array_remove(blockers, 'The Event Coordinator must confirm registration readiness.');
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

commit;
