-- Event Organiser change requests. Apply after the event lifecycle migrations.
begin;

do $$ begin
    create type public.event_change_request_status as enum
        ('pending_review', 'approved', 'rejected');
exception when duplicate_object then null;
end $$;

create table if not exists public.event_change_request (
    event_change_request_id bigint generated always as identity primary key,
    event_id integer not null references public.events(event_id) on delete cascade,
    requested_by uuid not null references public.users(user_id),
    assigned_coordinator_id uuid not null references public.users(user_id),
    reason text not null check (nullif(btrim(reason), '') is not null and length(reason) <= 2000),
    proposed_values jsonb not null check (jsonb_typeof(proposed_values) = 'object' and proposed_values <> '{}'::jsonb),
    changes jsonb not null check (jsonb_typeof(changes) = 'object' and changes <> '{}'::jsonb),
    status public.event_change_request_status not null default 'pending_review',
    expected_event_updated_at timestamptz not null,
    submitted_at timestamptz not null default clock_timestamp(),
    reviewed_at timestamptz,
    reviewed_by uuid references public.users(user_id),
    constraint event_change_request_review_state check (
        (status = 'pending_review' and reviewed_at is null and reviewed_by is null)
        or (status in ('approved', 'rejected') and reviewed_at is not null and reviewed_by is not null)
    )
);

create index if not exists event_change_request_event_idx
    on public.event_change_request(event_id, submitted_at desc);
create unique index if not exists event_change_request_one_pending_idx
    on public.event_change_request(event_id) where status = 'pending_review';

alter table public.notification add column if not exists event_change_request_id bigint
    references public.event_change_request(event_change_request_id) on delete cascade;
alter table public.event_activity add column if not exists event_change_request_id bigint
    references public.event_change_request(event_change_request_id) on delete set null;

alter table public.event_change_request enable row level security;
drop policy if exists event_change_request_read_participants on public.event_change_request;
create policy event_change_request_read_participants on public.event_change_request
    for select to authenticated using (
        requested_by = (select auth.uid())
        or assigned_coordinator_id = (select auth.uid())
    );
revoke insert, update, delete, truncate on public.event_change_request from anon, authenticated;
grant select on public.event_change_request to authenticated;

-- Organisers use the controlled change-request RPC rather than updating their
-- operational event directly. Coordinator/staff access required by existing
-- planning stories remains unchanged.
drop policy if exists authenticated_update_events on public.events;
create policy authenticated_update_events on public.events
    for update to authenticated
    using (
        event_coordinator_id = (select auth.uid())
        or technical_support_id = (select auth.uid())
        or venue_staff_id = (select auth.uid())
    )
    with check (event_organiser_id is not null and event_coordinator_id is not null);

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
      into result from public.events e
     where e.event_organiser_id = auth.uid()
       and e.status in ('planning', 'pending_safety_checks', 'confirmed')
       and not exists (
           select 1 from public.event_change_request c
            where c.event_id = e.event_id and c.status = 'pending_review'
       );
    return jsonb_build_object('events', result);
end;
$$;

create or replace function public.event_change_requests_for_event(p_event_id integer)
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare planned public.events; result jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    select * into planned from public.events where event_id = p_event_id;
    if not found or (auth.uid() is distinct from planned.event_organiser_id
                 and auth.uid() is distinct from planned.event_coordinator_id) then
        return jsonb_build_object('error', 'Event not found or access unavailable.', 'status', 404);
    end if;
    select coalesce(jsonb_agg(to_jsonb(c) order by c.submitted_at desc), '[]'::jsonb)
      into result from public.event_change_request c where c.event_id = p_event_id;
    return jsonb_build_object('change_requests', result);
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
    allowed_fields constant text[] := array[
        'start_datetime', 'end_datetime', 'capacity_needed', 'room_layout',
        'required_facilities', 'need_wheelchair_accessibility',
        'need_blind_accessibility', 'equipment_requirements'
    ];
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_organiser') then
        return jsonb_build_object('error', 'Only Event Organisers can submit event change requests.', 'status', 403);
    end if;
    if nullif(btrim(coalesce(p_reason, '')), '') is null then
        return jsonb_build_object(
            'error', 'The change request could not be submitted because some details are invalid.',
            'errors', jsonb_build_object('reason', 'Please provide a reason for this change request'), 'status', 400
        );
    end if;
    if length(btrim(p_reason)) > 2000 then
        return jsonb_build_object('error', 'The reason must be 2000 characters or fewer.', 'status', 400);
    end if;
    if jsonb_typeof(p_proposed_values) is distinct from 'object' then
        return jsonb_build_object('error', 'Proposed changes must be a JSON object.', 'status', 400);
    end if;
    if exists (select 1 from jsonb_object_keys(p_proposed_values) key where not (key = any(allowed_fields))) then
        return jsonb_build_object('error', 'One or more proposed fields cannot be changed.', 'status', 400);
    end if;

    select * into planned from public.events where event_id = p_event_id for update;
    if not found or planned.event_organiser_id is distinct from auth.uid() then
        return jsonb_build_object('error', 'Event not found or access unavailable.', 'status', 404);
    end if;
    if planned.status not in ('planning', 'pending_safety_checks', 'confirmed') then
        return jsonb_build_object('error', 'This event can no longer accept change requests.', 'status', 409);
    end if;
    if planned.updated_at is distinct from p_expected_event_updated_at then
        return jsonb_build_object('error', 'This event changed while you were editing. Reload it and try again.', 'stale', true, 'status', 409);
    end if;
    if exists (select 1 from public.event_change_request where event_id = p_event_id and status = 'pending_review') then
        return jsonb_build_object('error', 'This event already has a change request pending review.', 'status', 409);
    end if;

    begin
        select * into candidate from jsonb_populate_record(planned, p_proposed_values);
    exception when others then
        return jsonb_build_object('error', 'One or more proposed values are invalid.', 'status', 400);
    end;

    for changed_key in select jsonb_object_keys(p_proposed_values) loop
        if (to_jsonb(candidate) -> changed_key) = 'null'::jsonb then
            return jsonb_build_object('error', 'Proposed values cannot be empty.', 'status', 400);
        end if;
        if (to_jsonb(candidate) -> changed_key) is distinct from (to_jsonb(planned) -> changed_key) then
            calculated_changes := calculated_changes || jsonb_build_object(
                changed_key, jsonb_build_object('from', to_jsonb(planned) -> changed_key, 'to', to_jsonb(candidate) -> changed_key)
            );
        end if;
    end loop;

    if calculated_changes = '{}'::jsonb then
        return jsonb_build_object('error', 'Make at least one change before submitting.', 'status', 400);
    end if;
    if candidate.end_datetime <= candidate.start_datetime then
        return jsonb_build_object('error', 'The event must end after it starts.', 'status', 400);
    end if;
    if p_proposed_values ? 'start_datetime' and candidate.start_datetime <= now() then
        return jsonb_build_object('error', 'The event must start in the future.', 'status', 400);
    end if;
    if candidate.capacity_needed < 1 then
        return jsonb_build_object('error', 'Expected attendance must be at least 1.', 'status', 400);
    end if;

    if planned.status = 'confirmed' and not coalesce(p_confirm_critical, false) then
        select coalesce(jsonb_agg(case key
            when 'start_datetime' then 'Proposed start date and time'
            when 'end_datetime' then 'Proposed end date and time'
            when 'capacity_needed' then 'Expected attendance'
            when 'room_layout' then 'Room layout'
            when 'required_facilities' then 'Venue requirements'
            when 'need_wheelchair_accessibility' then 'Wheelchair accessibility'
            when 'need_blind_accessibility' then 'Accessibility for blind attendees'
            when 'equipment_requirements' then 'Equipment requirements'
            end order by key), '[]'::jsonb)
          into readable_fields from jsonb_object_keys(calculated_changes) key;
        return jsonb_build_object(
            'error', 'Review and confirm changes that may affect existing arrangements.',
            'critical_fields', readable_fields, 'status', 409
        );
    end if;

    insert into public.event_change_request (
        event_id, requested_by, assigned_coordinator_id, reason,
        proposed_values, changes, expected_event_updated_at
    ) values (
        planned.event_id, auth.uid(), planned.event_coordinator_id, btrim(p_reason),
        p_proposed_values, calculated_changes, planned.updated_at
    ) returning * into saved;

    if planned.status = 'confirmed' then
        insert into public.event_activity (event_id, changed_by, change_type, changes, event_change_request_id)
        values (planned.event_id, auth.uid(), 'critical_edit', calculated_changes, saved.event_change_request_id);
    end if;

    insert into public.notification (recipient_id, event_change_request_id, notification_type, message)
    values (planned.event_coordinator_id, saved.event_change_request_id,
            'event_change_request_submitted',
            'A change request for ' || planned.event_name || ' is awaiting your review.');

    return jsonb_build_object(
        'message', 'Event change request submitted successfully.',
        'change_request', to_jsonb(saved)
    );
end;
$$;

revoke all on function public.eligible_event_change_request_events(),
    public.event_change_requests_for_event(integer),
    public.submit_event_change_request(integer, text, jsonb, timestamptz, boolean) from public, anon;
grant execute on function public.eligible_event_change_request_events(),
    public.event_change_requests_for_event(integer),
    public.submit_event_change_request(integer, text, jsonb, timestamptz, boolean) to authenticated;

notify pgrst, 'reload schema';
commit;
