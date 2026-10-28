-- ConnectSphere EMS: An event's venue bookings, readable by everyone assigned
-- to the event
-- Run this file in the Supabase SQL Editor after 043, which adds
-- events.safety_officer_id.
--
-- The event page shows the event's venue booking requests. list_venue_bookings
-- (026) serves only Event Coordinators and Venue Staff, and refuses everyone
-- else with a 403, so the event's Organiser, Technical Support Staff and
-- Safety Officer could not see the requests at all. This function returns
-- one event's bookings, read only, to the people the event names. It changes
-- nothing about who may request, review, hold or cancel a booking.
--
-- TO REVERT
--     drop function if exists public.event_venue_bookings(integer);

begin;

create or replace function public.event_venue_bookings(p_event_id integer)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare planned public.events;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    select * into planned from public.events where event_id = p_event_id;
    if not found then
        return jsonb_build_object('error', 'Event not found or access unavailable.', 'status', 404);
    end if;
    if auth.uid() is distinct from planned.event_organiser_id
       and auth.uid() is distinct from planned.event_coordinator_id
       and auth.uid() is distinct from planned.technical_support_id
       and auth.uid() is distinct from planned.venue_staff_id
       and auth.uid() is distinct from planned.safety_officer_id then
        return jsonb_build_object('error', 'Only the people assigned to this event can view its venue bookings.', 'status', 403);
    end if;
    return jsonb_build_object('bookings', coalesce((
        select jsonb_agg(to_jsonb(b) || jsonb_build_object(
            'venue_name', v.venue_name,
            'reviewed_by_name', reviewer.name
        ) order by b.submitted_at desc)
        from public.venue_booking_requests b
        join public.venues v on v.venue_id = b.venue_id
        left join public.users reviewer on reviewer.user_id = b.reviewed_by
        where b.event_id = p_event_id
    ), '[]'::jsonb));
end;
$$;

revoke all on function public.event_venue_bookings(integer) from public, anon;
grant execute on function public.event_venue_bookings(integer) to authenticated;

notify pgrst, 'reload schema';

commit;
