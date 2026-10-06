-- ConnectSphere EMS: Narrow who may write to events, requests and history
-- Run this file in the Supabase SQL Editor.
--
-- 023 restricted who may READ an event, and a policy audit afterwards showed
-- reading was the only thing it restricted:
--
--   authenticated_read_events                 SELECT   assignment based (023)
--   authenticated_reassign_event_coordinator  UPDATE   using (true) check (true)
--   authenticated_manage_event_requests       ALL      assignment based (023)
--
-- So any authenticated user could update any event, including one they cannot
-- see. That predates this work; 023 simply made the gap visible by closing the
-- read side and leaving the write side open.
--
-- This migration also:
--   * splits the event_request ALL policy, which carried DELETE with it, so a
--     request can no longer be deleted straight from the table API at any
--     status. Deleting a draft is a real feature, so DELETE is kept but scoped
--     to the Organiser's own drafts, matching delete_draft() in the service.
--   * binds event_activity.changed_by to the signed-in user, so a history
--     entry cannot be written under somebody else's name. An append-only
--     record that anyone can forge is not an audit trail.
--
-- WHAT TO CHECK AFTER RUNNING
--   * Edit an event you are assigned to: still saves.
--   * Reassign a coordinator: still works, including handing it to someone
--     else (see the note on with check below).
--   * Delete one of your own drafts: still works.
--   * Submitting a new event request: still works. The insert policy now
--     requires the organiser on the row to be you, which is new.
--
-- TO REVERT
--     drop policy if exists authenticated_update_events on public.events;
--     create policy authenticated_reassign_event_coordinator on public.events
--         for update to authenticated using (true) with check (true);
--     -- and recreate authenticated_manage_event_requests as "for all"
--     -- using/with check (organiser = auth.uid() or coordinator = auth.uid())

begin;

-- 1. An event may only be changed by the people assigned to it.
--
--    using decides which rows you may touch: only your own.
--    with check decides what the row may look like afterwards, and is
--    deliberately NOT the same predicate. If it were, a Coordinator could
--    never hand an event to a colleague, because the row they wrote would no
--    longer name them. It instead refuses to leave an event orphaned.
drop policy if exists authenticated_reassign_event_coordinator on public.events;
drop policy if exists authenticated_update_events on public.events;

create policy authenticated_update_events on public.events
    for update to authenticated
    using (
        event_organiser_id = (select auth.uid())
        or event_coordinator_id = (select auth.uid())
        or technical_support_id = (select auth.uid())
        or venue_staff_id = (select auth.uid())
    )
    with check (
        event_organiser_id is not null
        and event_coordinator_id is not null
    );

-- 2. Replace the single "for all" request policy with one per operation, so
--    that DELETE is no longer granted by implication.
drop policy if exists authenticated_manage_event_requests on public.event_request;

create policy authenticated_read_event_requests on public.event_request
    for select to authenticated
    using (
        event_organiser_id = (select auth.uid())
        or event_coordinator_id = (select auth.uid())
    );

-- An Organiser raises their own requests, not somebody else's.
create policy authenticated_create_event_requests on public.event_request
    for insert to authenticated
    with check (event_organiser_id = (select auth.uid()));

create policy authenticated_update_event_requests on public.event_request
    for update to authenticated
    using (
        event_organiser_id = (select auth.uid())
        or event_coordinator_id = (select auth.uid())
    )
    with check (
        event_organiser_id = (select auth.uid())
        or event_coordinator_id = (select auth.uid())
    );

-- Only the Organiser, and only while it is still a draft. Once a request has
-- been submitted it is part of the record and is cancelled, not erased.
create policy authenticated_delete_draft_event_requests on public.event_request
    for delete to authenticated
    using (
        event_organiser_id = (select auth.uid())
        and status = 'draft'::public.event_status
    );

-- 3. A history entry must name whoever actually made the change.
drop policy if exists authenticated_write_event_activity on public.event_activity;

create policy authenticated_write_event_activity on public.event_activity
    for insert to authenticated
    with check (
        changed_by = (select auth.uid())
        and exists (
            select 1 from public.events e
            where e.event_id = event_activity.event_id
        )
    );

comment on policy authenticated_update_events on public.events is
    'Only the four people assigned to an event may change it, and they may '
    'not leave it without an organiser or a coordinator.';

comment on policy authenticated_delete_draft_event_requests on public.event_request is
    'An Organiser may delete their own request only while it is a draft.';

commit;
