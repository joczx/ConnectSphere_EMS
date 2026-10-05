-- ConnectSphere EMS: Limit event visibility to the people assigned to it
-- Run this file in the Supabase SQL Editor.
--
-- READ THIS BEFORE RUNNING. This is the only migration in this change that
-- can take functionality away from users, and it is deliberately separate from
-- 022 so it can be run, tested and reverted on its own.
--
-- Supports the "View Event Information" acceptance criterion "Users can only
-- view events they are authorised to access".
--
-- Today public.events has:
--     create policy authenticated_read_events ... using (true)
-- which means any signed-in user can read every event. The Flask API already
-- passes the caller's own access token, so the plumbing is right and only the
-- policy is permissive. This replaces it with the four assignments the table
-- already records.
--
-- WHAT THIS CHANGES
-- "My events" stops listing events the user has nothing to do with, and
-- /api/events/<id> returns 404 for an event they are not assigned to.
--
-- WHAT TO CHECK AFTER RUNNING
-- Anything that reads public.events for a user who is not assigned to it will
-- now see nothing. The equipment availability functions are SECURITY DEFINER
-- and so are unaffected, but venue suitability and any admin style listing are
-- worth exercising before you rely on this. If a role genuinely needs to see
-- every event, add it as another arm of the using() clause rather than
-- returning to using (true).
--
-- TO REVERT
--     drop policy if exists authenticated_read_events on public.events;
--     create policy authenticated_read_events on public.events
--         for select to authenticated using (true);

begin;

drop policy if exists authenticated_read_events on public.events;

create policy authenticated_read_events on public.events
    for select to authenticated
    using (
        event_organiser_id = (select auth.uid())
        or event_coordinator_id = (select auth.uid())
        or technical_support_id = (select auth.uid())
        or venue_staff_id = (select auth.uid())
    );

-- An event's history is only as private as the event, so it follows the same
-- rule rather than staying open to every authenticated user.
drop policy if exists authenticated_read_event_activity on public.event_activity;

create policy authenticated_read_event_activity on public.event_activity
    for select to authenticated
    using (
        exists (
            select 1 from public.events e
            where e.event_id = event_activity.event_id
        )
    );

comment on policy authenticated_read_events on public.events is
    'A user sees an event only when they are its organiser, coordinator, '
    'technical support or venue staff.';

commit;
