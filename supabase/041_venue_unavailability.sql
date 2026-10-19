-- ConnectSphere EMS: Mark a venue temporarily unavailable, and handle the bookings it affects
-- Run in the Supabase SQL Editor after 040.
--
-- Venue Staff may block any venue for any period with a reason, even over
-- existing bookings. Every pending or approved booking whose held period (040)
-- overlaps the block is cancelled with the reason, and its Event Coordinator is
-- notified and asked to request another venue. Cancelling fires the arrangement
-- trigger (030/035), so each affected event is re-evaluated as usual.
--
-- From then on the block counts as a conflict wherever conflicts are checked:
-- new requests (027), approvals (028), modifications (038) and search. Times
-- outside the block are unaffected.
--
-- hold_expires_at is used by the tentative holds story (042). It is added here
-- so the conflict functions below are rewritten once: an unexpired hold already
-- reserves the venue like an approved booking.

begin;

alter table public.venue_booking_requests
    add column if not exists cancellation_reason text,
    add column if not exists hold_expires_at timestamptz;

-- As in 040, but an unexpired hold reports itself as 'held'.
create or replace function public.venue_booking_summary(b public.venue_booking_requests)
returns jsonb
language sql stable security definer set search_path = public as $$
    select jsonb_build_object(
        'booking_id', b.booking_id, 'venue_id', b.venue_id,
        'status', case when b.status = 'submitted' and b.hold_expires_at > now() then 'held' else b.status end,
        'starts_at', b.starts_at, 'ends_at', b.ends_at, 'hold_expires_at', b.hold_expires_at,
        'occupied_from', b.occupied_from, 'occupied_until', b.occupied_until
    ) || case
        when public.has_booking_role('venue_staff') or b.requested_by = auth.uid()
        then jsonb_build_object('event_id', b.event_id, 'event_name', b.event_name, 'visible', true)
        else jsonb_build_object('visible', false)
    end;
$$;

create or replace function public.venue_block_summary(k public.venue_blocks)
returns jsonb
language sql stable security definer set search_path = public as $$
    select jsonb_build_object('block_id', k.block_id, 'venue_id', k.venue_id, 'status', 'blocked',
                              'starts_at', k.starts_at, 'ends_at', k.ends_at, 'reason', k.reason);
$$;

-- As in 040, plus blocks and unexpired holds, which make the venue unavailable
-- just as an approved booking does.
create or replace function public.venue_booking_conflicts(
    p_venue_id uuid, p_starts timestamptz, p_ends timestamptz,
    p_exclude uuid default null, p_approved_only boolean default false
) returns jsonb
language sql stable security definer set search_path = public as $$
    with wanted as (
        select tstzrange(p_starts - make_interval(mins => v.default_setup_minutes),
                         p_ends + make_interval(mins => v.default_turnaround_minutes), '[)') as period
        from public.venues v where v.venue_id = p_venue_id and auth.uid() is not null
    )
    select coalesce(jsonb_agg(item order by item->>'starts_at'), '[]'::jsonb) from (
        select public.venue_booking_summary(b) as item
        from public.venue_booking_requests b, wanted
        where b.venue_id = p_venue_id and b.booking_id is distinct from p_exclude
          and tstzrange(b.occupied_from, b.occupied_until, '[)') && wanted.period
          and (b.status = 'approved'
               or (b.status = 'submitted' and b.hold_expires_at > now())
               or (not p_approved_only and b.status = 'submitted'
                   and (public.has_booking_role('venue_staff') or b.requested_by = auth.uid())))
        union all
        select public.venue_block_summary(k)
        from public.venue_blocks k, wanted
        where k.venue_id = p_venue_id and tstzrange(k.starts_at, k.ends_at, '[)') && wanted.period
    ) found;
$$;

create or replace function public.venue_unavailability(p_starts timestamptz, p_ends timestamptz)
returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(item order by item->>'starts_at'), '[]'::jsonb) from (
        select public.venue_booking_summary(b) as item
        from public.venue_booking_requests b join public.venues v on v.venue_id = b.venue_id
        where (b.status = 'approved' or (b.status = 'submitted' and b.hold_expires_at > now()))
          and tstzrange(b.occupied_from, b.occupied_until, '[)')
           && tstzrange(p_starts - make_interval(mins => v.default_setup_minutes),
                        p_ends + make_interval(mins => v.default_turnaround_minutes), '[)')
        union all
        select public.venue_block_summary(k)
        from public.venue_blocks k join public.venues v on v.venue_id = k.venue_id
        where tstzrange(k.starts_at, k.ends_at, '[)')
           && tstzrange(p_starts - make_interval(mins => v.default_setup_minutes),
                        p_ends + make_interval(mins => v.default_turnaround_minutes), '[)')
    ) found
    where auth.uid() is not null;
$$;

create or replace function public.block_venue(
    p_venue_id uuid, p_starts timestamptz, p_ends timestamptz, p_reason text
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    block public.venue_blocks;
    venue text;
    reason text := trim(coalesce(p_reason, ''));
    affected jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can mark a venue unavailable.', 'status', 403);
    end if;
    select venue_name into venue from public.venues where venue_id = p_venue_id and deleted_at is null;
    if not found then
        return jsonb_build_object('error', 'Venue not found or access unavailable.', 'status', 404);
    end if;
    if p_starts is null or p_ends is null or p_ends <= p_starts then
        return jsonb_build_object('error', 'The end must be after the start.', 'status', 400);
    end if;
    if reason = '' or length(reason) > 500 then
        return jsonb_build_object('error', 'Enter a reason (maximum 500 characters).', 'status', 400);
    end if;

    insert into public.venue_blocks (venue_id, starts_at, ends_at, reason, created_by)
    values (p_venue_id, p_starts, p_ends, reason, auth.uid()) returning * into block;

    with cancelled as (
        update public.venue_booking_requests b
        set status = 'cancelled', cancelled_at = now(), cancellation_reason = 'Venue unavailable: ' || reason
        where b.venue_id = p_venue_id and b.status in ('submitted', 'approved')
          and tstzrange(b.occupied_from, b.occupied_until, '[)') && tstzrange(p_starts, p_ends, '[)')
        returning b.*
    ), told as (
        -- The event's current coordinator is told, who may not be the one who
        -- requested the booking if the event was reassigned. A coordinator
        -- missing from public.users cannot be notified (026), but the booking is
        -- still cancelled and shows the reason.
        insert into public.notification (recipient_id, venue_booking_id, notification_type, message)
        select r.recipient, c.booking_id, 'venue_booking_cancelled',
               format('%s is unavailable from %s to %s (%s). Your booking for %s was cancelled. Please request another venue.',
                      venue, to_char(p_starts at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
                      to_char(p_ends at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'), reason, c.event_name)
        from cancelled c
        left join public.events e on e.event_id = c.event_id
        cross join lateral (select coalesce(e.event_coordinator_id, c.requested_by) as recipient) r
        where exists (select 1 from public.users u where u.user_id = r.recipient)
    )
    select coalesce(jsonb_agg(jsonb_build_object(
        'booking_id', c.booking_id, 'event_id', c.event_id, 'event_name', c.event_name,
        'starts_at', c.starts_at, 'ends_at', c.ends_at) order by c.starts_at), '[]'::jsonb)
    into affected from cancelled c;

    return jsonb_build_object('block', to_jsonb(block), 'affected', affected);
end;
$$;

-- Removes an unavailable period, reopening it for new requests. Bookings it
-- already cancelled stay cancelled; their coordinators have been told to rebook.
create or replace function public.unblock_venue(p_block_id uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare removed public.venue_blocks;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can remove an unavailable period.', 'status', 403);
    end if;
    delete from public.venue_blocks where block_id = p_block_id returning * into removed;
    if not found then
        return jsonb_build_object('error', 'Unavailable period not found.', 'status', 404);
    end if;
    return jsonb_build_object('block', to_jsonb(removed));
end;
$$;

revoke all on function public.block_venue(uuid, timestamptz, timestamptz, text), public.unblock_venue(uuid),
    public.venue_block_summary(public.venue_blocks) from public, anon;
grant execute on function public.block_venue(uuid, timestamptz, timestamptz, text), public.unblock_venue(uuid),
    public.venue_block_summary(public.venue_blocks) to authenticated;

commit;
