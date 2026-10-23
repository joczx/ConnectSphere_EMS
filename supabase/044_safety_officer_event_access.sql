-- ConnectSphere EMS: Safety Officers can read the events assigned to them
-- Run this file in the Supabase SQL Editor after 043, which adds
-- events.safety_officer_id.
--
-- authenticated_read_events (023) lets an event's organiser, coordinator,
-- technical support and venue staff read it. This adds the assigned Safety
-- Officer as a separate policy. Policies for the same command are combined
-- with OR, so the existing four readers are untouched.
--
-- TO REVERT
--     drop policy if exists safety_officer_read_events on public.events;

begin;

drop policy if exists safety_officer_read_events on public.events;
create policy safety_officer_read_events on public.events
    for select to authenticated
    using (safety_officer_id = (select auth.uid()));

comment on policy safety_officer_read_events on public.events is
    'A Safety Officer sees the events they are assigned to review.';

commit;
