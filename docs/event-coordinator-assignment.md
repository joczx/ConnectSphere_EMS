# Assign event requests to Event Coordinators

An Event Coordinator Lead assigns each submitted, unassigned event request to
an Event Coordinator. The assignment queue is available from the **Assign
Event Requests** home tile.

## Database setup

Apply `supabase/029_event_coordinator_assignment.sql` after
`supabase/028_approval_matches_event.sql`. It reuses the existing
`event_request`, `events`, `roles`, `user_roles` and `notification` tables; it
does not create another assignment or notification table.
Run the migration in the Supabase SQL Editor, then refresh the project if the
RPC still reports that it cannot find `event_request_assignment_queue`.
The migration sends a PostgREST schema-cache reload notification, but if the
database API did not receive it, run `NOTIFY pgrst, 'reload schema';` in the
SQL Editor.

Assign users the `Event Coordinator Lead` and `Event Coordinator` roles through
trusted administrator tooling. The browser cannot grant roles to itself.
New event requests are left without a coordinator. Only submitted requests
with no coordinator appear in the Lead-only queue.

## How assignment works

The Flask API calls database functions with the signed-in user's bearer token.
The database checks the Lead role before it returns the queue or changes an
assignment. Assignment also checks that the selected person has the Event
Coordinator role, then atomically:

1. Assigns the coordinator to the submitted request, provided it is still
   unassigned.
2. Updates the linked event if one already exists. When the request is later
   approved, the existing event-creation trigger copies the assignment to the
   planning event.
3. Writes an `event_request_assigned` notification for that coordinator.

The existing row-level security policies make the assigned coordinator a
permitted reader of the request and planning event. A request that was assigned
by another Lead, or is no longer submitted, is refused rather than overwritten.
The in-app notification is available to its recipient through the authenticated
notifications API and is shown in the account menu.

## Verification

Run `python -m pytest tests/test_event_request_assignment.py` from `backend`
and `npm run build` from `frontend`. These tests mock the Supabase calls; they
do not replace applying the migration or checking role assignments and RLS in
the deployed Supabase project.
