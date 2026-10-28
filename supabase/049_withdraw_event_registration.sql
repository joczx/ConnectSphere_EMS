-- Apply after 048. Withdrawals preserve the registration record and release its place.
begin;
alter table public.event_registration
    drop constraint event_registration_status_check,
    add constraint event_registration_status_check check (status in ('registered', 'waiting_list', 'withdrawn')),
    add column withdrawn_at timestamptz;

create function public.withdraw_event_registration(p_event_id integer) returns jsonb
language plpgsql security definer set search_path = public as $$
declare planned public.events; saved public.event_registration; instant timestamptz;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('attendee') then
        return jsonb_build_object('error', 'Only attendees can withdraw registrations.', 'status', 403);
    end if;
    -- Use the registration lock, then read the clock: waiting across event start
    -- must not allow a withdrawal that is now too late.
    select * into planned from public.events where event_id = p_event_id for update;
    instant := clock_timestamp();
    if not found then
        return jsonb_build_object('error', 'Registration not found.', 'status', 404);
    end if;
    select * into saved from public.event_registration
        where event_id = p_event_id and attendee_id = auth.uid();
    if not found then
        return jsonb_build_object('error', 'Registration not found.', 'status', 404);
    end if;
    if planned.start_datetime is null or instant >= planned.start_datetime then
        return jsonb_build_object('error', 'Registration cannot be withdrawn at or after the event start time.', 'status', 409);
    end if;
    if saved.status <> 'withdrawn' then
        update public.event_registration set status = 'withdrawn', withdrawn_at = instant
            where event_id = p_event_id and attendee_id = auth.uid() returning * into saved;
        -- Do not send a pending attendance confirmation after withdrawal.
        delete from public.registration_email_outbox
            where event_id = p_event_id and attendee_id = auth.uid() and sent_at is null;
    end if;
    return jsonb_build_object('message', 'Your registration has been successfully withdrawn.',
        'registration', to_jsonb(saved),
        'available_capacity', greatest(0, planned.capacity_needed - (select count(*)
            from public.event_registration where event_id = p_event_id and status = 'registered')));
end;
$$;
revoke all on function public.withdraw_event_registration(integer) from public, anon;
grant execute on function public.withdraw_event_registration(integer) to authenticated;

create or replace function public.register_for_event(p_event_id integer, p_full_name text, p_contact_email text, p_contact_phone text) returns jsonb
    language plpgsql security definer set search_path = public as $$
    declare planned public.events; saved public.event_registration; total integer; instant timestamptz;
    begin
        if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('attendee') then
        return jsonb_build_object('error', 'Only attendees can register for events.', 'status', 403);
    end if;
        if p_full_name is null or length(btrim(p_full_name)) not between 1 and 150
            or p_full_name ~ '[[:cntrl:]]'
            or p_contact_email is null or length(btrim(p_contact_email)) > 254
            or btrim(p_contact_email) !~ '^[A-Za-z0-9.!#$%&''*+/=?^_`{|}~-]+@[A-Za-z0-9-]+([.][A-Za-z0-9-]+)+$'
            or p_contact_phone is null or length(btrim(p_contact_phone)) > 30
            or btrim(p_contact_phone) !~ '^\+?[0-9 ()-]{7,30}$'
            or length(regexp_replace(p_contact_phone, '[^0-9]', '', 'g')) < 7 then
            return jsonb_build_object('error', 'Provide a valid full name, contact email and phone number.', 'status', 400);
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
        if found and saved.status <> 'withdrawn' then
            return jsonb_build_object('registration', to_jsonb(saved), 'notification',
                coalesce((select case when sent_at is null then 'queued' else 'sent' end
                    from public.registration_email_outbox where event_id = p_event_id and attendee_id = auth.uid()), 'unavailable'));
        end if;
        select count(*) into total from public.event_registration
            where event_id = p_event_id and status = 'registered';
        if planned.capacity_needed is null or planned.capacity_needed < 1 then
            return jsonb_build_object('error', 'Registration capacity is not configured.', 'status', 409);
        end if;
        if total >= planned.capacity_needed and not planned.waiting_list_enabled then
            return jsonb_build_object('error', 'This event is full. The waiting list is disabled.', 'status', 409);
        end if;
        insert into public.event_registration(event_id, attendee_id, status, full_name, contact_email, contact_phone)
        values (p_event_id, auth.uid(), case when total >= planned.capacity_needed then 'waiting_list' else 'registered' end, btrim(p_full_name), btrim(p_contact_email), btrim(p_contact_phone))
        on conflict (event_id, attendee_id) do update set
            status = excluded.status, full_name = excluded.full_name,
            contact_email = excluded.contact_email, contact_phone = excluded.contact_phone,
            created_at = clock_timestamp(), withdrawn_at = null
        returning * into saved;
        insert into public.registration_email_outbox(event_id, attendee_id, recipient, subject, body)
        values (p_event_id, auth.uid(), saved.contact_email,
            case when saved.status = 'registered' then 'Event registration confirmed' else 'Event waiting list confirmation' end,
            'Hello ' || saved.full_name || E',\n\n' ||
            case when saved.status = 'registered' then 'Your registration is confirmed for ' else 'You have joined the waiting list for ' end ||
            planned.event_name || E'.\n' ||
            case when saved.status = 'waiting_list' then 'This does not confirm a place at the event.' else 'We look forward to seeing you.' end)
        on conflict (event_id, attendee_id) do update set
            recipient = excluded.recipient, subject = excluded.subject, body = excluded.body,
            created_at = clock_timestamp(), sent_at = null;
        return jsonb_build_object('registration', to_jsonb(saved), 'notification', 'queued');
    end;
    $$;

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
            'available_capacity', greatest(0, e.capacity_needed - (select count(*) from public.event_registration r
                where r.event_id = e.event_id and r.status = 'registered')),
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

notify pgrst, 'reload schema';
commit;
