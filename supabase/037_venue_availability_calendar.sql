-- ConnectSphere EMS: Venue availability calendar
-- Run in the Supabase SQL Editor after 036. Uses venue_booking_summary() from 027.
--
-- venue_availability() returns one venue's approved bookings (confirmed),
-- pending requests (tentatively held) and blocked periods for a date range.
-- Only Event Coordinators and Venue Staff may call it. Other coordinators'
-- events are named "Another event" by venue_booking_summary().
--
-- venue_blocks is filled by the later "block venue time" story; one dummy
-- block is seeded below so the Blocked status can be seen meanwhile.

begin;

create table if not exists public.venue_blocks (
    block_id uuid primary key default gen_random_uuid(),
    venue_id uuid not null references public.venues(venue_id),
    starts_at timestamptz not null,
    ends_at timestamptz not null check (ends_at > starts_at),
    reason text,
    created_by uuid references auth.users(id),
    created_at timestamptz not null default now()
);
alter table public.venue_blocks enable row level security;
revoke all on public.venue_blocks from anon, authenticated;

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
              and tstzrange(b.starts_at, b.ends_at, '[)') && period
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
revoke all on function public.venue_availability(uuid, timestamptz, timestamptz) from public, anon;
grant execute on function public.venue_availability(uuid, timestamptz, timestamptz) to authenticated;

-- Test data: remove once Venue Staff can block time themselves.
insert into public.venue_blocks (venue_id, starts_at, ends_at, reason)
select venue_id, '2026-10-27 09:00+08', '2026-10-27 17:00+08', 'Maintenance (test block)'
from public.venues
where venue_name = 'ConnectSphere Test - Shared Conference Hall'
  and not exists (select 1 from public.venue_blocks);

commit;
