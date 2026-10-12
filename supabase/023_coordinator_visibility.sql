-- ConnectSphere EMS: An event request belongs to one Event Coordinator
-- Run this file in the Supabase SQL Editor.
--
-- READ THIS BEFORE RUNNING. This migration takes access away, and it changes
-- existing rows. It is the only one in this change that does either.
--
-- Supports "each event request, once submitted, is received by a single
-- coordinator" and the "users can only view events they are authorised to
-- access" criterion of the View Event Information story.
--
-- WHAT IS WRONG TODAY
-- public.event_request and public.events both carry an event_coordinator_id,
-- and trg_assign_event_coordinator fills it on insert, but the policies are:
--     authenticated_manage_event_requests ... using (true)
--     authenticated_read_events           ... using (true)
-- so the assignment is recorded, displayed, and governs nothing. Every
-- coordinator sees and may act on every request and every event.
--
-- WHY THE BACKFILL COMES FIRST
-- trg_assign_event_coordinator was added after most of these rows, so 8 of 12
-- requests and 3 of 6 events have no coordinator. Applying the policies
-- without backfilling would hide two already-submitted requests from every
-- coordinator, leaving them permanently unreviewable. The backfill is written
-- to be safe to re-run: it only ever touches rows that are still null.
--
-- WHAT TO CHECK AFTER RUNNING
-- Sign in as a coordinator and confirm "Review event requests" lists only
-- their own, and that an event they are not assigned to returns not-found.
-- Anything else reading these tables for an unassigned user now sees nothing;
-- the equipment availability functions are SECURITY DEFINER and unaffected,
-- but venue suitability is worth exercising.
--
-- TO REVERT (the policies; the backfilled assignments are kept)
--     drop policy if exists authenticated_manage_event_requests on public.event_request;
--     create policy authenticated_manage_event_requests on public.event_request
--         for all to authenticated using (true) with check (true);
--     drop policy if exists authenticated_read_events on public.events;
--     create policy authenticated_read_events on public.events
--         for select to authenticated using (true);

begin;

-- 1. Give every unassigned request a coordinator, the same way the trigger
--    does for new ones.
--
--    APPLIED 2026-10-06. Note for anyone reading this as an example: the
--    subquery does not correlate with the outer row, so PostgreSQL evaluated
--    it once for the whole statement rather than per row, and all 8 backfilled
--    requests went to the same coordinator. Every row got exactly one
--    coordinator, which is what the policy below needs, so this was left as
--    it ran. To spread them, correlate the subquery with the outer row (for
--    example by referencing event_request_id in the order by).
update public.event_request
set event_coordinator_id = (
    select u.user_id
    from public.users u
    join public.user_roles ur on ur.user_id = u.user_id
    join public.roles ro on ro.role_id = ur.role_id
    where ro.role_name = 'Event Coordinator'
    order by random()
    limit 1
)
where event_coordinator_id is null;

-- 2. An event inherits its request's coordinator, so the two agree. Event 3
--    currently has one its request does not, which is how that drift looks.
update public.events e
set event_coordinator_id = r.event_coordinator_id
from public.event_request r
where r.event_request_id = e.event_request_id
  and e.event_coordinator_id is null
  and r.event_coordinator_id is not null;

-- 3. Any event with no request to inherit from still needs someone.
update public.events
set event_coordinator_id = (
    select u.user_id
    from public.users u
    join public.user_roles ur on ur.user_id = u.user_id
    join public.roles ro on ro.role_id = ur.role_id
    where ro.role_name = 'Event Coordinator'
    order by random()
    limit 1
)
where event_coordinator_id is null;

-- 4. A request is visible to the Organiser who raised it and the Coordinator
--    it was assigned to, and nobody else.
--
--    "for all" rather than "for select": the same two people are the only ones
--    who may edit it, and with check mirrors using so a row cannot be updated
--    into someone else's hands.
drop policy if exists authenticated_manage_event_requests on public.event_request;

create policy authenticated_manage_event_requests on public.event_request
    for all to authenticated
    using (
        event_organiser_id = (select auth.uid())
        or event_coordinator_id = (select auth.uid())
    )
    with check (
        event_organiser_id = (select auth.uid())
        or event_coordinator_id = (select auth.uid())
    );

-- 5. An event is visible to the four people the row names. Technical support
--    and venue staff are included because they are assigned to the event and
--    need its details to do their own work.
drop policy if exists authenticated_read_events on public.events;

create policy authenticated_read_events on public.events
    for select to authenticated
    using (
        event_organiser_id = (select auth.uid())
        or event_coordinator_id = (select auth.uid())
        or technical_support_id = (select auth.uid())
        or venue_staff_id = (select auth.uid())
    );

-- 6. An event's history is exactly as private as the event. The subquery is
--    subject to the policy above, so this needs no copy of its conditions.
drop policy if exists authenticated_read_event_activity on public.event_activity;

create policy authenticated_read_event_activity on public.event_activity
    for select to authenticated
    using (
        exists (
            select 1 from public.events e
            where e.event_id = event_activity.event_id
        )
    );

drop policy if exists authenticated_write_event_activity on public.event_activity;

create policy authenticated_write_event_activity on public.event_activity
    for insert to authenticated
    with check (
        exists (
            select 1 from public.events e
            where e.event_id = event_activity.event_id
        )
    );

comment on policy authenticated_manage_event_requests on public.event_request is
    'A request is seen and managed only by the Organiser who raised it and the '
    'single Event Coordinator it was assigned to.';

comment on policy authenticated_read_events on public.events is
    'A user sees an event only when they are its organiser, coordinator, '
    'technical support or venue staff.';

commit;
