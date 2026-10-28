-- ConnectSphere EMS: Notify about venue booking requests, venue unavailability
-- and tentative holds.
-- Run in the Supabase SQL Editor after 050.
--
-- Every change below already happens to public.venue_booking_requests (049), so
-- one trigger covers them all: a request submitted (027), approved or rejected
-- (review_venue_booking), cancelled because the venue became unavailable
-- (block_venue, which records 'Venue unavailable: <reason>'), held
-- (hold_venue_booking) and expired (expire_venue_holds). The coordinator is the
-- requester; the event's Venue Staff is events.venue_staff_id (043).
--
-- expire_venue_holds, already run every minute (042), also reminds the
-- coordinator once when a hold has 24 hours or less to go. Whether a reminder
-- was sent is read from the notification itself, so reminding never updates the
-- booking (which would make the safety workflow re-check its event, 042).

begin;

create or replace function public.notify_venue_booking_change() returns trigger
language plpgsql security definer set search_path = public as $$
declare
    venue text := coalesce((select venue_name from public.venues where venue_id = new.venue_id), 'the venue');
    booking text := format('%s for %s (%s – %s SGT)', venue, coalesce(new.event_name, 'an unnamed event'),
        to_char(new.starts_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
        to_char(new.ends_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'));
    expiry text := to_char(new.hold_expires_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI');
    link text := '/venue-bookings/' || new.booking_id;
    block public.venue_blocks;
begin
    if tg_op = 'INSERT' then
        if new.status = 'submitted' then
            perform public.notify_user(new.requested_by, 'venue_booking_submitted', 'Venue booking request submitted',
                format('Your venue booking request for %s has been submitted. Status: pending Venue Staff review.', booking), link);
            perform public.notify_user((select venue_staff_id from public.events where event_id = new.event_id),
                'venue_booking_submitted', 'New venue booking request',
                format('%s has requested %s. Status: pending review.',
                       coalesce((select name from public.users where user_id = new.requested_by), 'An Event Coordinator'), booking),
                '/review-venue-bookings/' || new.booking_id);
        end if;
    elsif new.status is distinct from old.status then
        if old.status = 'submitted' and new.status in ('approved', 'rejected') then
            perform public.notify_user(new.requested_by, 'venue_booking_' || new.status, 'Venue booking ' || new.status,
                format('Your venue booking request for %s has been %s by %s.%s', booking, new.status,
                       coalesce((select name from public.users where user_id = new.reviewed_by), 'Venue Staff'),
                       case when new.status = 'rejected' then ' Reason: ' || coalesce(new.review_comments, 'none given') else '' end),
                link);
        elsif new.status = 'cancelled' and new.cancellation_reason like 'Venue unavailable: %' then
            select * into block from public.venue_blocks k
            where k.venue_id = new.venue_id
              and tstzrange(k.starts_at, k.ends_at, '[)') && tstzrange(new.occupied_from, new.occupied_until, '[)')
            order by k.created_at desc limit 1;
            perform public.notify_user(new.requested_by, 'venue_unavailable', 'Venue unavailable',
                format('%s is unavailable from %s to %s SGT (%s), which affects your %s %s. It has been cancelled.', venue,
                       to_char(block.starts_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
                       to_char(block.ends_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'), block.reason,
                       case when old.status = 'approved' then 'approved booking of' else 'pending booking request for' end, booking),
                link);
        elsif old.status = 'submitted' and new.status = 'expired' then
            perform public.notify_user(new.requested_by, 'venue_hold_expired', 'Tentative hold expired',
                format('The tentative hold on %s expired on %s SGT. The venue is now available to other requests.', booking, expiry),
                link);
        end if;
    elsif old.hold_expires_at is null and new.hold_expires_at is not null and new.status = 'submitted' then
        perform public.notify_user(new.requested_by, 'venue_hold_placed', 'Tentative hold placed',
            format('Venue Staff have placed a tentative hold on %s. It expires on %s SGT.', booking, expiry), link);
    end if;
    return null;
end;
$$;
drop trigger if exists notify_venue_booking_change on public.venue_booking_requests;
create trigger notify_venue_booking_change after insert or update of status, hold_expires_at on public.venue_booking_requests
    for each row execute function public.notify_venue_booking_change();

-- Run every minute by pg_cron (042).
create or replace function public.expire_venue_holds()
returns void
language plpgsql security definer set search_path = public as $$
declare held public.venue_booking_requests;
begin
    for held in
        select * from public.venue_booking_requests b
        where b.status = 'submitted' and b.hold_expires_at > now() and b.hold_expires_at <= now() + interval '24 hours'
          and not exists (select 1 from public.notifications n
                          where n.recipient_id = b.requested_by and n.kind = 'venue_hold_reminder'
                            and n.link = '/venue-bookings/' || b.booking_id
                            and n.created_at > b.hold_expires_at - interval '24 hours')
    loop
        perform public.notify_user(held.requested_by, 'venue_hold_reminder', 'Tentative hold expiring soon',
            format('Reminder: the tentative hold on %s for %s expires on %s SGT. Unless Venue Staff confirm the booking by then, the venue becomes available to other requests.',
                   coalesce((select venue_name from public.venues where venue_id = held.venue_id), 'the venue'),
                   coalesce(held.event_name, 'an unnamed event'),
                   to_char(held.hold_expires_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI')),
            '/venue-bookings/' || held.booking_id);
    end loop;

    update public.venue_booking_requests set status = 'expired', expired_at = now()
    where status = 'submitted' and hold_expires_at <= now();
end;
$$;

revoke all on function public.notify_venue_booking_change() from public, anon, authenticated;

commit;
