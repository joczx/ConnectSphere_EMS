-- Apply after 049. Strict ordering: registration opens < closes < event starts.
-- Existing violations must be corrected before this migration can be applied.
begin;
alter table public.events add constraint registration_before_event_start check (
    registration_opens_at is null or (
        start_datetime is not null and isfinite(start_datetime)
        and registration_closes_at < start_datetime
    )
);
    create or replace function public.set_event_registration_period(
        p_event_id integer, p_registration_opens_at timestamptz,
        p_registration_closes_at timestamptz, p_waiting_list_enabled boolean
    ) returns jsonb language plpgsql security definer set search_path = public as $$
    declare saved public.events;
    begin
        if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
        select * into saved from public.events where event_id = p_event_id for update;
        if not found or saved.event_organiser_id is distinct from auth.uid()
            or not public.has_booking_role('event_organiser') then
            return jsonb_build_object('error', 'Only the assigned Event Organiser can manage registration.', 'status', 403);
        end if;
        if saved.status not in ('planning', 'pending_safety_checks', 'confirmed')
            or saved.end_datetime <= clock_timestamp()
            or saved.registration_closes_at <= clock_timestamp() then
            return jsonb_build_object('error', 'Registration settings can only change before or during registration.', 'status', 409);
        end if;
        if p_registration_opens_at is null or p_registration_closes_at is null
            or not isfinite(p_registration_opens_at) or not isfinite(p_registration_closes_at)
            or p_registration_closes_at <= p_registration_opens_at or p_waiting_list_enabled is null then
            return jsonb_build_object('error', 'Provide valid opening and closing times; closing must be after opening.', 'status', 400);
        end if;
        if saved.start_datetime is null or not isfinite(saved.start_datetime) then
            return jsonb_build_object('error', 'Set a valid event start time before configuring registration.', 'status', 400,
                'errors', jsonb_build_object('registration_opens_at', 'Set a valid event start time first.'));
        end if;
        if p_registration_opens_at >= saved.start_datetime then
            return jsonb_build_object('error', 'Registration must open before the event starts.', 'status', 400,
                'errors', jsonb_build_object('registration_opens_at', 'Registration must open before the event starts.'));
        end if;
        if p_registration_closes_at >= saved.start_datetime then
            return jsonb_build_object('error', 'Registration must close before the event starts.', 'status', 400,
                'errors', jsonb_build_object('registration_closes_at', 'Registration must close before the event starts.'));
        end if;
        update public.events set registration_opens_at = p_registration_opens_at,
            registration_closes_at = p_registration_closes_at,
            waiting_list_enabled = p_waiting_list_enabled
        where event_id = p_event_id returning * into saved;
        return jsonb_build_object('event', to_jsonb(saved));
    end;
    $$;

notify pgrst, 'reload schema';
commit;
