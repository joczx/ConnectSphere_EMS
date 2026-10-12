-- Coordinator Lead dashboard: global read and reassignment through role-checked
-- functions, without widening the assignment-scoped RLS policies.
-- Apply after 029_event_coordinator_assignment.sql.

begin;

alter type public.event_status
    add value if not exists 'pending_safety_checks' after 'planning';

comment on column public.events.status is
    'Operational phase of the event lifecycle. ''planning'' while arrangements '
    'are being made, ''pending_safety_checks'' while required safety checks '
    'remain, ''confirmed'' once arrangements are settled, and ''completed'' '
    'once the event is over. ''cancelled'' is reachable from any stage.';

create or replace function public.event_coordinator_lead_dashboard()
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
    dashboard_items jsonb;
    available_coordinators jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator_lead') then
        return jsonb_build_object(
            'error', 'Only Event Coordinator Leads can view this dashboard.',
            'status', 403
        );
    end if;

    select coalesce(jsonb_agg(
        dashboard.item
        order by dashboard.item->>'start_datetime' nulls last,
                 dashboard.item->>'event_name'
    ), '[]'::jsonb)
    into dashboard_items
    from (
        select jsonb_build_object(
            'item_type', 'request',
            'event_id', null,
            'event_request_id', r.event_request_id,
            'event_name', r.event_name,
            'purpose', r.purpose,
            'description', r.description,
            'start_datetime', r.start_datetime,
            'end_datetime', r.end_datetime,
            'capacity_needed', r.capacity_needed,
            'status', r.status::text,
            'event_coordinator_id', r.event_coordinator_id,
            'event_coordinator_name', coalesce(
                nullif(btrim(coordinator.name), ''),
                nullif(btrim(coordinator.email), '')
            ),
            'event_organiser_name', coalesce(
                nullif(btrim(organiser.name), ''),
                nullif(btrim(organiser.email), '')
            )
        ) as item
        from public.event_request r
        left join public.users coordinator
            on coordinator.user_id = r.event_coordinator_id
        left join public.users organiser
            on organiser.user_id = r.event_organiser_id
        where r.status = 'submitted'::public.event_status

        union all

        select jsonb_build_object(
            'item_type', 'event',
            'event_id', e.event_id,
            'event_request_id', e.event_request_id,
            'event_name', e.event_name,
            'purpose', e.purpose,
            'description', e.description,
            'start_datetime', e.start_datetime,
            'end_datetime', e.end_datetime,
            'capacity_needed', e.capacity_needed,
            'status', e.status::text,
            'event_coordinator_id', e.event_coordinator_id,
            'event_coordinator_name', coalesce(
                nullif(btrim(coordinator.name), ''),
                nullif(btrim(coordinator.email), '')
            ),
            'event_organiser_name', coalesce(
                nullif(btrim(organiser.name), ''),
                nullif(btrim(organiser.email), '')
            )
        ) as item
        from public.events e
        left join public.users coordinator
            on coordinator.user_id = e.event_coordinator_id
        left join public.users organiser
            on organiser.user_id = e.event_organiser_id
        where e.status::text in (
            'planning',
            'pending_safety_checks',
            'confirmed'
        )
    ) dashboard;

    select coalesce(jsonb_agg(
        jsonb_build_object(
            'id', eligible.user_id,
            'name', coalesce(
                nullif(btrim(u.name), ''),
                nullif(btrim(u.email), ''),
                u.user_id::text
            )
        ) order by coalesce(
            nullif(btrim(u.name), ''),
            nullif(btrim(u.email), ''),
            u.user_id::text
        )
    ), '[]'::jsonb)
    into available_coordinators
    from (
        select distinct ur.user_id
        from public.user_roles ur
        join public.roles ro on ro.role_id = ur.role_id
        where replace(lower(trim(ro.role_name)), ' ', '_') = 'event_coordinator'
    ) eligible
    join public.users u on u.user_id = eligible.user_id;

    return jsonb_build_object(
        'items', dashboard_items,
        'coordinators', available_coordinators
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

        insert into public.notification (
            recipient_id, event_request_id, notification_type, message
        ) values (
            p_coordinator_id,
            p_event_request_id,
            'event_request_assigned',
            'You have been assigned to coordinate "' || assigned_request.event_name || '".'
        );
    end if;

    return jsonb_build_object(
        'message', 'Event Coordinator reassigned successfully.',
        'event_request', to_jsonb(assigned_request)
    );
end;
$$;

drop function if exists public.reassign_event_coordinator_for_lead(uuid, uuid);

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

            insert into public.notification (
                recipient_id, event_request_id, notification_type, message
            ) values (
                p_coordinator_id,
                assigned_event.event_request_id,
                'event_request_assigned',
                'You have been assigned to coordinate "' || assigned_event.event_name || '".'
            );
        end if;
    end if;

    return jsonb_build_object(
        'message', 'Event Coordinator reassigned successfully.',
        'event', to_jsonb(assigned_event)
    );
end;
$$;

revoke all on function public.event_coordinator_lead_dashboard() from public, anon;
revoke all on function public.reassign_submitted_request_coordinator(bigint, uuid)
    from public, anon;
revoke all on function public.reassign_event_coordinator_for_lead(integer, uuid)
    from public, anon;
grant execute on function public.event_coordinator_lead_dashboard() to authenticated;
grant execute on function public.reassign_submitted_request_coordinator(bigint, uuid)
    to authenticated;
grant execute on function public.reassign_event_coordinator_for_lead(integer, uuid)
    to authenticated;

notify pgrst, 'reload schema';

commit;
