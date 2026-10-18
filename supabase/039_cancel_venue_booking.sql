-- ConnectSphere EMS: Cancel an individual venue booking
-- Run in the Supabase SQL Editor after 038.
--
-- An Event Coordinator may cancel one of their own pending or approved bookings
-- while its event is in planning or under safety review. Only that booking
-- changes; the event and its other bookings stay active. A cancelled booking no
-- longer holds its slot: the double-booking constraint (027), conflicts and the
-- availability calendar only count pending and approved bookings. The existing
-- arrangement trigger (030/035) re-evaluates the event, which returns to planning
-- if this booking was its only matching venue, and otherwise needs a fresh
-- safety review.

begin;

alter table public.venue_booking_requests
    add column if not exists cancelled_at timestamptz,
    drop constraint if exists venue_booking_status_known,
    drop constraint if exists venue_booking_decision_recorded,
    add constraint venue_booking_status_known
        check (status in ('submitted', 'approved', 'rejected', 'cancelled')),
    add constraint venue_booking_decision_recorded
        check (status = 'cancelled' or (status = 'submitted') = (reviewed_at is null and reviewed_by is null));

create or replace function public.cancel_venue_booking(p_booking_id uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare booking public.venue_booking_requests;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    select * into booking from public.venue_booking_requests
    where booking_id = p_booking_id and requested_by = auth.uid() for update;
    if not found then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    if booking.status not in ('submitted', 'approved') then
        return jsonb_build_object('error', 'Only pending or approved bookings can be cancelled.', 'status', 409);
    end if;
    if not exists (select 1 from public.events where event_id = booking.event_id
                   and status in ('planning', 'pending_safety_checks') and start_datetime > now()) then
        return jsonb_build_object('error', 'Bookings can only be cancelled before the event is confirmed and has started.', 'status', 409);
    end if;
    update public.venue_booking_requests set status = 'cancelled', cancelled_at = now()
    where booking_id = p_booking_id returning * into booking;
    return jsonb_build_object('booking', to_jsonb(booking));
end;
$$;
revoke all on function public.cancel_venue_booking(uuid) from public, anon;
grant execute on function public.cancel_venue_booking(uuid) to authenticated;

commit;
