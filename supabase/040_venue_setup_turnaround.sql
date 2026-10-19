-- ConnectSphere EMS: Setup and turnaround time block the venue around a booking
-- Run in the Supabase SQL Editor after 039.
--
-- A booking now holds its venue from (start - setup) to (end + turnaround),
-- using the venue's default_setup_minutes / default_turnaround_minutes. Two
-- bookings at a venue clash when those held periods overlap, so back-to-back
-- bookings need the turnaround and the setup between them.
--
-- The held period is stored on the booking (occupied_from / occupied_until) and
-- set whenever the booking is requested, changed, approved or cancelled. A later
-- change to a venue's minutes therefore applies to new requests and approvals,
-- not to bookings already approved, so it can never make approved bookings
-- clash after the fact.
--
-- The functions below keep their signatures, so submit (027), review (028),
-- modify (038), search and the calendar (037) all use the held period unchanged.

begin;

alter table public.venues
    add constraint venue_setup_within_a_day check (default_setup_minutes <= 1440),
    add constraint venue_turnaround_within_a_day check (default_turnaround_minutes <= 1440);

alter table public.venue_booking_requests
    add column if not exists occupied_from timestamptz,
    add column if not exists occupied_until timestamptz;

create or replace function public.set_venue_booking_occupied() returns trigger
language plpgsql security definer set search_path = public as $$
begin
    select new.starts_at - make_interval(mins => v.default_setup_minutes),
           new.ends_at + make_interval(mins => v.default_turnaround_minutes)
    into new.occupied_from, new.occupied_until
    from public.venues v where v.venue_id = new.venue_id;
    return new;
end;
$$;
create trigger venue_booking_occupied before insert or update on public.venue_booking_requests
    for each row execute function public.set_venue_booking_occupied();

-- Backfill without re-evaluating every event through the safety workflow's
-- arrangement trigger (030/035): nothing about the arrangements changes here.
alter table public.venue_booking_requests disable trigger venue_updates_event_status;
update public.venue_booking_requests set starts_at = starts_at;
alter table public.venue_booking_requests enable trigger venue_updates_event_status;

alter table public.venue_booking_requests
    alter column occupied_from set not null,
    alter column occupied_until set not null,
    drop constraint venue_booking_no_double_booking,
    add constraint venue_booking_no_double_booking
        exclude using gist (venue_id with =, tstzrange(occupied_from, occupied_until, '[)') with &&)
        where (status = 'approved');

create or replace function public.venue_booking_summary(b public.venue_booking_requests)
returns jsonb
language sql stable security definer set search_path = public as $$
    select jsonb_build_object(
        'booking_id', b.booking_id, 'venue_id', b.venue_id, 'status', b.status,
        'starts_at', b.starts_at, 'ends_at', b.ends_at,
        'occupied_from', b.occupied_from, 'occupied_until', b.occupied_until
    ) || case
        when public.has_booking_role('venue_staff') or b.requested_by = auth.uid()
        then jsonb_build_object('event_id', b.event_id, 'event_name', b.event_name, 'visible', true)
        else jsonb_build_object('visible', false)
    end;
$$;

-- A candidate period is extended by the venue's own setup and turnaround before
-- it is compared with the held periods of existing bookings.
create or replace function public.venue_booking_conflicts(
    p_venue_id uuid, p_starts timestamptz, p_ends timestamptz,
    p_exclude uuid default null, p_approved_only boolean default false
) returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(public.venue_booking_summary(b) order by b.starts_at), '[]'::jsonb)
    from public.venue_booking_requests b
    join public.venues v on v.venue_id = p_venue_id
    where auth.uid() is not null
      and b.venue_id = p_venue_id
      and b.booking_id is distinct from p_exclude
      and tstzrange(b.occupied_from, b.occupied_until, '[)')
       && tstzrange(p_starts - make_interval(mins => v.default_setup_minutes),
                    p_ends + make_interval(mins => v.default_turnaround_minutes), '[)')
      and (
          b.status = 'approved'
          or (not p_approved_only
              and b.status = 'submitted'
              and (public.has_booking_role('venue_staff') or b.requested_by = auth.uid()))
      );
$$;

create or replace function public.venue_unavailability(p_starts timestamptz, p_ends timestamptz)
returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(public.venue_booking_summary(b) order by b.starts_at), '[]'::jsonb)
    from public.venue_booking_requests b
    join public.venues v on v.venue_id = b.venue_id
    where auth.uid() is not null
      and b.status = 'approved'
      and tstzrange(b.occupied_from, b.occupied_until, '[)')
       && tstzrange(p_starts - make_interval(mins => v.default_setup_minutes),
                    p_ends + make_interval(mins => v.default_turnaround_minutes), '[)');
$$;

-- As in 037, with bookings found by their held period so setup and turnaround
-- at the edge of the visible range are shown.
create or replace function public.venue_availability(
    p_venue_id uuid, p_starts timestamptz, p_ends timestamptz
) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare period tstzrange;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not (public.has_booking_role('event_coordinator') or public.has_booking_role('venue_staff')) then
        return jsonb_build_object('error', 'Only Event Coordinators and Venue Staff can view venue availability.', 'status', 403);
    end if;
    if p_ends <= p_starts or p_ends - p_starts > interval '100 days' then
        return jsonb_build_object('error', 'Choose a period of up to 100 days.', 'status', 400);
    end if;
    if not exists (select 1 from public.venues where venue_id = p_venue_id and deleted_at is null) then
        return jsonb_build_object('error', 'Venue not found or access unavailable.', 'status', 404);
    end if;
    period := tstzrange(p_starts, p_ends, '[)');
    return jsonb_build_object(
        'bookings', coalesce((
            select jsonb_agg(public.venue_booking_summary(b) order by b.starts_at)
            from public.venue_booking_requests b
            where b.venue_id = p_venue_id and b.status in ('approved', 'submitted')
              and tstzrange(b.occupied_from, b.occupied_until, '[)') && period
        ), '[]'::jsonb),
        'blocks', coalesce((
            select jsonb_agg(jsonb_build_object('block_id', k.block_id, 'starts_at', k.starts_at,
                                                'ends_at', k.ends_at, 'reason', k.reason) order by k.starts_at)
            from public.venue_blocks k
            where k.venue_id = p_venue_id and tstzrange(k.starts_at, k.ends_at, '[)') && period
        ), '[]'::jsonb)
    );
end;
$$;

commit;
