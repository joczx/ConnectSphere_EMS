-- Contact email remains required but its address format is not checked.
-- Single-line text and length limits remain enforced for safe email headers.
begin;
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
            or p_contact_email is null or length(btrim(p_contact_email)) not between 1 and 254
            or p_contact_email ~ '[[:cntrl:]]'
            or p_contact_phone is null or length(btrim(p_contact_phone)) > 30
            or btrim(p_contact_phone) !~ '^\+?[0-9 ()-]{7,30}$'
            or length(regexp_replace(p_contact_phone, '[^0-9]', '', 'g')) < 7 then
            return jsonb_build_object('error', 'Provide your full name, contact email and a valid phone number.', 'status', 400);
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

notify pgrst, 'reload schema';
commit;
