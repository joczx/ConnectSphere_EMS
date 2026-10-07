-- Requires venues, users, roles and user_roles. Run using a trusted administrator.
begin;
-- Role assignments must only be managed by trusted administrators.
revoke insert, update, delete, truncate on public.roles, public.user_roles from anon, authenticated;

create function public.has_booking_role(p_role text) returns boolean
language sql stable security definer set search_path = public as $$
    select exists (select 1 from public.user_roles ur join public.roles r using (role_id)
        where ur.user_id = auth.uid()
        and replace(lower(trim(r.role_name)), ' ', '_') = p_role);
$$;
revoke all on function public.has_booking_role(text) from public, anon;
grant execute on function public.has_booking_role(text) to authenticated;

create table public.venue_booking_requests (
    booking_id uuid primary key default gen_random_uuid(),
    venue_id uuid not null references public.venues(venue_id),
    requested_by uuid not null references auth.users(id),
    event_name text not null check (length(trim(event_name)) between 1 and 200),
    starts_at timestamptz not null,
    ends_at timestamptz not null check (ends_at > starts_at),
    attendance integer not null check (attendance > 0),
    venue_requirements text not null check (length(trim(venue_requirements)) between 1 and 5000),
    status text not null default 'submitted' check (status = 'submitted'),
    submitted_at timestamptz not null default now()
);
create index venue_booking_submitter_idx on public.venue_booking_requests(requested_by, submitted_at desc);
alter table public.venue_booking_requests enable row level security;
revoke all on public.venue_booking_requests from anon, authenticated;
grant select on public.venue_booking_requests to authenticated;
create policy booking_read on public.venue_booking_requests for select to authenticated
using (requested_by = auth.uid() or public.has_booking_role('venue_staff'));

create function public.submit_venue_booking(p_booking jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare saved public.venue_booking_requests;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator') then
        return jsonb_build_object('error', 'Only Event Coordinators can submit venue bookings.', 'status', 403);
    end if;
    if jsonb_typeof(p_booking) is distinct from 'object'
        or not (p_booking ?& array['venue_id','event_name','starts_at','ends_at','attendance','venue_requirements'])
        or jsonb_typeof(p_booking->'attendance') is distinct from 'number'
        or jsonb_typeof(p_booking->'event_name') is distinct from 'string'
        or jsonb_typeof(p_booking->'venue_requirements') is distinct from 'string'
        or (p_booking->>'attendance') !~ '^[0-9]+$'
        or (p_booking->>'starts_at') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$'
        or (p_booking->>'ends_at') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' then
        return jsonb_build_object('error', 'Provide all required booking details.', 'status', 400);
    end if;
    if (p_booking->>'starts_at')::timestamptz <= now() then
        return jsonb_build_object('error', 'Start must be in the future.', 'status', 400);
    end if;
    if not exists (select 1 from public.venues where venue_id = (p_booking->>'venue_id')::uuid) then
        return jsonb_build_object('error', 'Select an existing venue.', 'status', 400);
    end if;
    insert into public.venue_booking_requests
        (venue_id, requested_by, event_name, starts_at, ends_at, attendance, venue_requirements)
    values ((p_booking->>'venue_id')::uuid, auth.uid(), trim(p_booking->>'event_name'),
        (p_booking->>'starts_at')::timestamptz, (p_booking->>'ends_at')::timestamptz,
        (p_booking->>'attendance')::integer, trim(p_booking->>'venue_requirements')) returning * into saved;
    return to_jsonb(saved);
exception when invalid_text_representation or datetime_field_overflow or invalid_datetime_format
    or numeric_value_out_of_range or check_violation or not_null_violation or foreign_key_violation then
    return jsonb_build_object('error', 'Provide valid, complete booking details.', 'status', 400);
end;
$$;

create function public.list_venue_bookings() returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare staff boolean := public.has_booking_role('venue_staff'); result jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not staff and not public.has_booking_role('event_coordinator') then
        return jsonb_build_object('error', 'Venue bookings are available to Event Coordinators and Venue Staff.', 'status', 403);
    end if;
    select coalesce(jsonb_agg(to_jsonb(b) || jsonb_build_object('venue_name', v.venue_name)
        order by b.submitted_at desc), '[]'::jsonb) into result
    from public.venue_booking_requests b join public.venues v using (venue_id)
    where staff or b.requested_by = auth.uid();
    return jsonb_build_object('bookings', result, 'can_submit', public.has_booking_role('event_coordinator'), 'can_review', staff);
end;
$$;
revoke all on function public.submit_venue_booking(jsonb), public.list_venue_bookings() from public, anon;
grant execute on function public.submit_venue_booking(jsonb), public.list_venue_bookings() to authenticated;
commit;
