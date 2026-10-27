-- Apply after 046. Registration browsing and submissions require the Attendee role.
begin;

create or replace function public.attendee_registration_events() returns jsonb
    language plpgsql stable security definer set search_path = public as $$
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('attendee') then
        return jsonb_build_object('error', 'Only attendees can browse registration events.', 'status', 403);
    end if;
    return (
        select jsonb_build_object('events', coalesce(jsonb_agg(jsonb_build_object(
            'event_id', e.event_id, 'event_name', e.event_name, 'description', e.description,
            'start_datetime', e.start_datetime, 'end_datetime', e.end_datetime,
            'status', e.status, 'registration_opens_at', e.registration_opens_at,
            'registration_closes_at', e.registration_closes_at,
            'waiting_list_enabled', e.waiting_list_enabled, 'capacity', e.capacity_needed,
            'registration_status', case
                when e.status <> 'confirmed' or e.end_datetime <= now() then 'unavailable'
                when now() < e.registration_opens_at then 'not_open'
                when now() >= e.registration_closes_at then 'closed'
                else 'open' end,
            'my_registration', (select r.status from public.event_registration r
                where r.event_id = e.event_id and r.attendee_id = auth.uid())
        ) order by e.start_datetime), '[]'::jsonb))
        from public.events e where auth.uid() is not null
            and e.registration_opens_at is not null
            and e.status in ('confirmed', 'completed', 'cancelled'));
    end;
$$;

create or replace function public.register_for_event(p_event_id integer) returns jsonb
    language plpgsql security definer set search_path = public as $$
    declare planned public.events; saved public.event_registration; total integer; instant timestamptz;
    begin
        if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('attendee') then
        return jsonb_build_object('error', 'Only attendees can register for events.', 'status', 403);
    end if;
        -- The same lock serialises registrations and period edits. Read the clock
        -- after acquiring it so requests waiting across closing time are refused.
        select * into planned from public.events where event_id = p_event_id for update;
        instant := clock_timestamp();
        if not found or planned.status <> 'confirmed' or planned.end_datetime <= instant
            or planned.registration_opens_at is null then
            return jsonb_build_object('error', 'Registration is unavailable for this event.', 'status', 409);
        end if;
        if instant < planned.registration_opens_at then
            return jsonb_build_object('error', 'Registration is not yet open.', 'status', 409);
        end if;
        if instant >= planned.registration_closes_at then
            return jsonb_build_object('error', 'Registration has closed.', 'status', 409);
        end if;
        select * into saved from public.event_registration
            where event_id = p_event_id and attendee_id = auth.uid();
        if found then return jsonb_build_object('registration', to_jsonb(saved)); end if;
        select count(*) into total from public.event_registration
            where event_id = p_event_id and status = 'registered';
        if planned.capacity_needed is null or planned.capacity_needed < 1 then
            return jsonb_build_object('error', 'Registration capacity is not configured.', 'status', 409);
        end if;
        if total >= planned.capacity_needed and not planned.waiting_list_enabled then
            return jsonb_build_object('error', 'This event is full. The waiting list is disabled.', 'status', 409);
        end if;
        insert into public.event_registration(event_id, attendee_id, status)
        values (p_event_id, auth.uid(), case when total >= planned.capacity_needed then 'waiting_list' else 'registered' end)
        returning * into saved;
        return jsonb_build_object('registration', to_jsonb(saved));
    end;
    $$;

-- Keep direct RPC calls protected as well as the frontend route.
revoke all on function public.attendee_registration_events(), public.register_for_event(integer)
    from public, anon;
grant execute on function public.attendee_registration_events(), public.register_for_event(integer)
    to authenticated;
notify pgrst, 'reload schema';
commit;
