-- ConnectSphere EMS: Modify an individual venue booking
-- Run in the Supabase SQL Editor after 037.
--
-- An Event Coordinator may change the venue and setup notes of one of their own
-- pending or approved bookings. The date, time and attendance are copied fresh
-- from the event, and the booking is rechecked for suitability (025), conflicts
-- (027) and blocked time (037). It then returns to Venue Staff for review, even
-- if it was approved. Only this booking changes, and it keeps its event.
--
-- Allowed while the event is in planning (before safety review, or after Safety
-- sends it back) or under safety review. A change during safety review returns
-- the event to planning: the venue is marked as needing fresh approval using the
-- safety workflow's own rework fields (035), so the event re-enters safety
-- review by itself once Venue Staff approve the change. Confirmed events are
-- not changed.

begin;

create or replace function public.modify_venue_booking(
    p_booking_id uuid, p_venue_id uuid, p_venue_requirements text
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    booking public.venue_booking_requests;
    planned public.events;
    chosen public.venues;
    shortfalls text[];
    blocking jsonb;
    notes text := trim(coalesce(p_venue_requirements, ''));
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator') then
        return jsonb_build_object('error', 'Only Event Coordinators can modify venue bookings.', 'status', 403);
    end if;

    select * into booking from public.venue_booking_requests
    where booking_id = p_booking_id and requested_by = auth.uid() for update;
    if not found then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    if booking.status not in ('submitted', 'approved') then
        return jsonb_build_object('error', 'Only pending or approved bookings can be modified.', 'status', 409);
    end if;

    select * into planned from public.events where event_id = booking.event_id;
    if not found or planned.status not in ('planning', 'pending_safety_checks')
        or planned.start_datetime <= now() then
        return jsonb_build_object('error', 'Bookings can only be modified before the event is confirmed and has started.', 'status', 409);
    end if;

    select * into chosen from public.venues where venue_id = p_venue_id and deleted_at is null;
    if not found then
        return jsonb_build_object('error', 'Select an existing venue.', 'status', 400);
    end if;
    if notes = '' or length(notes) > 5000 then
        return jsonb_build_object('error', 'Venue requirements are required (maximum 5000 characters).', 'status', 400);
    end if;

    shortfalls := public.venue_shortfalls_for_event(chosen, planned);
    if cardinality(shortfalls) > 0 then
        return jsonb_build_object('error', 'This venue does not meet the requirements recorded for this event.',
                                  'unmet_requirements', to_jsonb(shortfalls), 'status', 409);
    end if;
    blocking := public.venue_booking_conflicts(chosen.venue_id, planned.start_datetime,
                                               planned.end_datetime, booking.booking_id, true);
    if jsonb_array_length(blocking) > 0 then
        return jsonb_build_object('error', 'This venue is already booked for part of this event''s time.',
                                  'conflicts', blocking, 'status', 409);
    end if;
    if exists (select 1 from public.venue_blocks k where k.venue_id = chosen.venue_id
               and tstzrange(k.starts_at, k.ends_at, '[)')
                && tstzrange(planned.start_datetime, planned.end_datetime, '[)')) then
        return jsonb_build_object('error', 'This venue is blocked for part of this event''s time.', 'status', 409);
    end if;

    update public.venue_booking_requests
    set venue_id = chosen.venue_id, venue_requirements = notes, event_name = planned.event_name,
        starts_at = planned.start_datetime, ends_at = planned.end_datetime,
        attendance = coalesce(planned.capacity_needed, booking.attendance),
        status = 'submitted', reviewed_by = null, reviewed_at = null, review_comments = null,
        submitted_at = now()
    where booking_id = booking.booking_id
    returning * into booking;

    if planned.status = 'pending_safety_checks' then
        perform set_config('connectsphere.safety_workflow', 'true', true);
        update public.events
        set safety_rework_requested_at = clock_timestamp(), safety_rework_arrangements = array['venue'],
            safety_approved_at = null
        where event_id = planned.event_id;
    end if;
    return jsonb_build_object('booking', to_jsonb(booking));
end;
$$;
revoke all on function public.modify_venue_booking(uuid, uuid, text) from public, anon;
grant execute on function public.modify_venue_booking(uuid, uuid, text) to authenticated;

commit;
