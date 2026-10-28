-- Apply after 045. Registration times are independent of event arrangements.
    begin;
    alter table public.events
        add column registration_opens_at timestamptz,
        add column registration_closes_at timestamptz,
        add column waiting_list_enabled boolean not null default false,
        add constraint event_registration_period_check check (
            (registration_opens_at is null and registration_closes_at is null)
            or (registration_opens_at is not null and registration_closes_at is not null
                and isfinite(registration_opens_at) and isfinite(registration_closes_at)
                and registration_closes_at > registration_opens_at)
        );

    create table public.event_registration (
        event_id integer not null references public.events(event_id) on delete cascade,
        attendee_id uuid not null references auth.users(id) on delete cascade,
        status text not null check (status in ('registered', 'waiting_list')),
        created_at timestamptz not null default clock_timestamp(),
        primary key (event_id, attendee_id)
    );
    alter table public.event_registration enable row level security;
    revoke all on public.event_registration from public, anon, authenticated;
    grant select on public.event_registration to authenticated;
    create policy own_registration on public.event_registration for select to authenticated
        using (attendee_id = (select auth.uid()));

    -- Preserve lifecycle and safety rules while allowing independent registration settings.
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
                (to_jsonb(new) - array['registration_opens_at', 'registration_closes_at', 'waiting_list_enabled', 'status', 'registration_ready', 'updated_at',
                                    'safety_rework_required', 'safety_rework_requested_at',
                                    'safety_rework_arrangements', 'safety_approved_at']) is distinct from
                (to_jsonb(old) - array['registration_opens_at', 'registration_closes_at', 'waiting_list_enabled', 'status', 'registration_ready', 'updated_at',
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
            if (to_jsonb(new) - array['registration_opens_at', 'registration_closes_at', 'waiting_list_enabled', 'status', 'updated_at', 'registration_ready',
                                    'safety_rework_required', 'safety_rework_requested_at',
                                    'safety_rework_arrangements', 'safety_approved_at'])
                    is distinct from
                    (to_jsonb(old) - array['registration_opens_at', 'registration_closes_at', 'waiting_list_enabled', 'status', 'updated_at', 'registration_ready',
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

    -- Enforced even on direct event writes. The assigned organiser alone manages
    -- registration, before or during its period; ended events cannot be reopened.
    create function public.guard_registration_settings() returns trigger
    language plpgsql security definer set search_path = public as $$
    begin
        if row(new.registration_opens_at, new.registration_closes_at, new.waiting_list_enabled)
            is distinct from row(old.registration_opens_at, old.registration_closes_at, old.waiting_list_enabled) then
            if auth.uid() is null or auth.uid() is distinct from old.event_organiser_id
                or not public.has_booking_role('event_organiser') then
                raise insufficient_privilege using message = 'Only the assigned Event Organiser can manage registration.';
            end if;
            if old.status not in ('planning', 'pending_safety_checks', 'confirmed')
                or old.end_datetime <= clock_timestamp()
                or old.registration_closes_at <= clock_timestamp() then
                raise check_violation using message = 'Registration settings can only change before or during registration.';
            end if;
        end if;
        return new;
    end;
    $$;
    create trigger guard_registration_settings before update on public.events
        for each row execute function public.guard_registration_settings();

    create function public.set_event_registration_period(
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
        update public.events set registration_opens_at = p_registration_opens_at,
            registration_closes_at = p_registration_closes_at,
            waiting_list_enabled = p_waiting_list_enabled
        where event_id = p_event_id returning * into saved;
        return jsonb_build_object('event', to_jsonb(saved));
    end;
    $$;

    -- A deliberately narrow attendee projection; staff identities, requirements
    -- and internal planning notes remain private.
    create function public.attendee_registration_events() returns jsonb
    language sql stable security definer set search_path = public as $$
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
            and e.status in ('confirmed', 'completed', 'cancelled');
    $$;

    create function public.register_for_event(p_event_id integer) returns jsonb
    language plpgsql security definer set search_path = public as $$
    declare planned public.events; saved public.event_registration; total integer; instant timestamptz;
    begin
        if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
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

    revoke all on function public.guard_registration_settings(),
        public.set_event_registration_period(integer,timestamptz,timestamptz,boolean),
        public.attendee_registration_events(), public.register_for_event(integer) from public, anon, authenticated;
    grant execute on function public.set_event_registration_period(integer,timestamptz,timestamptz,boolean),
        public.attendee_registration_events(), public.register_for_event(integer) to authenticated;

    notify pgrst, 'reload schema';
    commit;
