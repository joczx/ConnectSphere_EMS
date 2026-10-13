-- ConnectSphere EMS: Event Coordinator Leads assign submitted requests
-- Apply after 028_approval_matches_event.sql.
--
-- New requests remain unassigned until a Lead assigns an Event Coordinator.
-- The assignment is stored on event_request; the existing approval trigger
-- copies that coordinator onto the planning event. The update below also
-- keeps an already-created event in sync if an eligible request is assigned.

begin;

drop trigger if exists trg_assign_event_coordinator on public.event_request;

grant select on public.notification to authenticated;
drop policy if exists authenticated_read_own_notifications on public.notification;
create policy authenticated_read_own_notifications on public.notification
    for select to authenticated
    using (recipient_id = (select auth.uid()));

create or replace function public.event_request_assignment_queue()
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
    requests jsonb;
    coordinators jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator_lead') then
        return jsonb_build_object(
            'error', 'Only Event Coordinator Leads can view unassigned event requests.',
            'status', 403
        );
    end if;

    select coalesce(jsonb_agg(
        jsonb_build_object(
            'event_request_id', r.event_request_id,
            'event_name', r.event_name,
            'purpose', r.purpose,
            'description', r.description,
            'start_datetime', r.start_datetime,
            'end_datetime', r.end_datetime,
            'capacity_needed', r.capacity_needed,
            'room_layout', r.room_layout,
            'event_organiser_name', coalesce(nullif(btrim(u.name), ''), nullif(btrim(u.email), ''))
        ) order by r.submitted_at, r.event_request_id
    ), '[]'::jsonb)
    into requests
    from public.event_request r
    left join public.users u on u.user_id = r.event_organiser_id
    where r.status = 'submitted'::public.event_status
      and r.event_coordinator_id is null;

    select coalesce(jsonb_agg(
        jsonb_build_object(
            'id', u.user_id,
            'name', coalesce(nullif(btrim(u.name), ''), nullif(btrim(u.email), ''), u.user_id::text)
        ) order by coalesce(nullif(btrim(u.name), ''), nullif(btrim(u.email), ''), u.user_id::text)
    ), '[]'::jsonb)
    into coordinators
    from (
        select distinct ur.user_id
        from public.user_roles ur
        join public.roles ro on ro.role_id = ur.role_id
        where replace(lower(trim(ro.role_name)), ' ', '_') = 'event_coordinator'
    ) assigned
    join public.users u on u.user_id = assigned.user_id;

    return jsonb_build_object('event_requests', requests, 'coordinators', coordinators);
end;
$$;

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

    insert into public.notification (
        recipient_id, event_request_id, notification_type, message
    ) values (
        p_coordinator_id,
        p_event_request_id,
        'event_request_assigned',
        'You have been assigned to coordinate "' || assigned_request.event_name || '".'
    );

    return jsonb_build_object(
        'message', 'Event Coordinator assigned successfully.',
        'event_request', to_jsonb(assigned_request)
    );
end;
$$;

revoke all on function public.event_request_assignment_queue() from public, anon;
revoke all on function public.assign_event_request_coordinator(bigint, uuid) from public, anon;
grant execute on function public.event_request_assignment_queue() to authenticated;
grant execute on function public.assign_event_request_coordinator(bigint, uuid) to authenticated;

notify pgrst, 'reload schema';

commit;
