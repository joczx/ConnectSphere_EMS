-- ConnectSphere EMS: Tentative venue holds that expire
-- Run in the Supabase SQL Editor after 041.
--
-- Venue Staff may place a tentative hold, with a required expiry, on a pending
-- request. While unexpired it reserves the venue like an approved booking (041).
-- Venue Staff confirm it by approving it as usual (028) before it expires. If
-- they do not, a scheduled job marks it 'expired' (recording expired_at), the
-- venue becomes available again, and the event's coordinator is notified. The
-- coordinator is also told when the hold is placed, with its expiry time, and
-- reminded 24 hours before it expires. A hold placed with less than 24 hours to
-- go counts its placement notice as the reminder. Whether a reminder was sent is
-- read from the notification itself, so reminding never updates the booking
-- (which would make the safety workflow re-check its event, 030/035).
--
-- An expired booking is no longer 'submitted', so it can never be approved, and
-- only 'approved' bookings count towards an event's readiness (036).

begin;

alter table public.venue_booking_requests
    add column if not exists expired_at timestamptz,
    drop constraint if exists venue_booking_status_known,
    drop constraint if exists venue_booking_decision_recorded,
    add constraint venue_booking_status_known
        check (status in ('submitted', 'approved', 'rejected', 'cancelled', 'expired')),
    add constraint venue_booking_decision_recorded
        check (status in ('cancelled', 'expired') or (status = 'submitted') = (reviewed_at is null and reviewed_by is null));

-- One pending (including held) or approved booking per event per venue: a
-- coordinator cannot request a venue again for the same event until the earlier
-- request is rejected, cancelled or has expired. Applies to new requests (027)
-- and to changing a booking's venue (038).
create unique index if not exists venue_booking_one_active_per_event_venue
    on public.venue_booking_requests (event_id, venue_id)
    where status in ('submitted', 'approved');

-- As in 040, plus: moving a booking to another venue or time releases its hold.
create or replace function public.set_venue_booking_occupied() returns trigger
language plpgsql security definer set search_path = public as $$
begin
    select new.starts_at - make_interval(mins => v.default_setup_minutes),
           new.ends_at + make_interval(mins => v.default_turnaround_minutes)
    into new.occupied_from, new.occupied_until
    from public.venues v where v.venue_id = new.venue_id;
    if tg_op = 'UPDATE' and (new.venue_id, new.starts_at, new.ends_at)
        is distinct from (old.venue_id, old.starts_at, old.ends_at) then
        new.hold_expires_at := null;
    end if;
    return new;
end;
$$;

-- Notifies the event's current coordinator about one booking (as in 041).
create or replace function public.notify_venue_booking(b public.venue_booking_requests, p_type text, p_message text)
returns void
language sql security definer set search_path = public as $$
    insert into public.notification (recipient_id, venue_booking_id, notification_type, message)
    select r.recipient, b.booking_id, p_type, p_message
    from (select coalesce((select event_coordinator_id from public.events where event_id = b.event_id),
                          b.requested_by) as recipient) r
    where exists (select 1 from public.users u where u.user_id = r.recipient);
$$;

create or replace function public.hold_venue_booking(p_booking_id uuid, p_expires_at timestamptz)
returns jsonb
language plpgsql security definer set search_path = public as $$
declare booking public.venue_booking_requests; venue text;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can place a tentative hold.', 'status', 403);
    end if;
    select * into booking from public.venue_booking_requests where booking_id = p_booking_id for update;
    if not found then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    if booking.status <> 'submitted' or booking.hold_expires_at is not null then
        return jsonb_build_object('error', 'Only a pending request without a hold can be held.', 'status', 409);
    end if;
    if p_expires_at is null or p_expires_at <= now() or p_expires_at >= booking.starts_at then
        return jsonb_build_object('error', 'Choose an expiry in the future and before the booking starts.',
                                  'errors', jsonb_build_object('expires_at', 'A valid expiry is required.'), 'status', 400);
    end if;
    if jsonb_array_length(public.venue_booking_conflicts(booking.venue_id, booking.starts_at, booking.ends_at,
                                                         booking.booking_id, true)) > 0 then
        return jsonb_build_object('error', 'The venue is already booked, held or unavailable at this time.', 'status', 409);
    end if;

    update public.venue_booking_requests set hold_expires_at = p_expires_at
    where booking_id = p_booking_id returning * into booking;
    select venue_name into venue from public.venues where venue_id = booking.venue_id;
    perform public.notify_venue_booking(booking,
        case when p_expires_at <= now() + interval '24 hours' then 'venue_booking_hold_expiring' else 'venue_booking_held' end,
        format(
        '%s is tentatively held for %s until %s. Venue Staff will confirm it before then, or the hold expires.',
        venue, booking.event_name, to_char(p_expires_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI')));
    return jsonb_build_object('booking', to_jsonb(booking));
end;
$$;

-- Venue Staff release a hold before it expires. The request stays pending and
-- the venue is free again; the coordinator is told.
create or replace function public.release_venue_hold(p_booking_id uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare booking public.venue_booking_requests;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can release a tentative hold.', 'status', 403);
    end if;
    update public.venue_booking_requests set hold_expires_at = null
    where booking_id = p_booking_id and status = 'submitted' and hold_expires_at > now()
    returning * into booking;
    if not found then
        return jsonb_build_object('error', 'This request has no active hold.', 'status', 409);
    end if;
    perform public.notify_venue_booking(booking, 'venue_booking_hold_released', format(
        'The tentative hold on %s for %s was released by Venue Staff. Your request is still awaiting review.',
        (select venue_name from public.venues where venue_id = booking.venue_id), booking.event_name));
    return jsonb_build_object('booking', to_jsonb(booking));
end;
$$;

-- Run every minute by pg_cron (as 031).
create or replace function public.expire_venue_holds()
returns void
language plpgsql security definer set search_path = public as $$
declare booking public.venue_booking_requests;
begin
    for booking in
        select * from public.venue_booking_requests b
        where b.status = 'submitted' and b.hold_expires_at > now()
          and b.hold_expires_at <= now() + interval '24 hours'
          and not exists (select 1 from public.notification n where n.venue_booking_id = b.booking_id
                          and n.notification_type = 'venue_booking_hold_expiring'
                          and n.created_at > b.hold_expires_at - interval '24 hours')
    loop
        perform public.notify_venue_booking(booking, 'venue_booking_hold_expiring', format(
            'Reminder: the tentative hold on %s for %s expires on %s. If Venue Staff do not confirm it by then, the venue will be released.',
            (select venue_name from public.venues where venue_id = booking.venue_id), booking.event_name,
            to_char(booking.hold_expires_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI')));
    end loop;

    for booking in
        update public.venue_booking_requests set status = 'expired', expired_at = now()
        where status = 'submitted' and hold_expires_at <= now()
        returning *
    loop
        perform public.notify_venue_booking(booking, 'venue_booking_expired', format(
            'The tentative hold on %s for %s expired on %s without being confirmed, so the venue is available to others again. Please request a venue again if you still need one.',
            (select venue_name from public.venues where venue_id = booking.venue_id), booking.event_name,
            to_char(booking.hold_expires_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI')));
    end loop;
end;
$$;

revoke all on function public.hold_venue_booking(uuid, timestamptz), public.release_venue_hold(uuid) from public, anon;
grant execute on function public.hold_venue_booking(uuid, timestamptz), public.release_venue_hold(uuid) to authenticated;
revoke all on function public.expire_venue_holds(),
    public.notify_venue_booking(public.venue_booking_requests, text, text) from public, anon, authenticated;

-- As in 031; enables the scheduler if this project does not have it yet.
create extension if not exists pg_cron;
select cron.schedule('connectsphere-expire-venue-holds', '* * * * *', 'select public.expire_venue_holds()');

commit;
