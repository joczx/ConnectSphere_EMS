# Event status management

The lifecycle supports Draft, Submitted, Planning, Confirmed,
Completed, Cancelled and Rejected. Under Review and Awaiting Arrangements are
not separate statuses. Approved is a review outcome rather than a status.

Requests retain the approval-stage status; operational events retain the
planning-stage status. Approval moves the request into **Planning** and creates
its **Planning** event automatically.

| Transition | Required condition |
| --- | --- |
| Draft → Submitted | Mandatory details, future start, end after start |
| Submitted → Planning / Rejected | Matching recorded review by the assigned coordinator |
| Rejected → Submitted | Amended request passes submission validation |
| Planning request → Planning event | Approval trigger creates the linked event once |
| Planning → Pending Safety Checks | Assigned coordinator submits after venue and equipment arrangements are complete |
| Pending Safety Checks → Confirmed | Assigned Safety Officer approves while venue, equipment and safety arrangements remain valid |
| Confirmed → Planning | A required arrangement becomes incomplete |
| Confirmed → Completed | End time has passed |
| Draft / Submitted / Rejected request → Cancelled | Organiser or assigned coordinator cancels |
| Planning / Confirmed event → Cancelled | Organiser or assigned coordinator cancels |

Completed and Cancelled are terminal. Status changes are guarded in PostgreSQL
so direct table API calls cannot bypass conditions. Operational changes record
Status Change entries in Activity History. Existing assignment-based RLS still
controls who can read events and requests.

Equipment is matched by trimmed, case-insensitive catalogue type. Quantities
are summed across reservations covering the complete event period. Every
additional equipment request also needs its own full linked reservation; partial
and rejected requests do not count as fulfilled. Unknown equipment requirements
(`null`) block confirmation; set an empty list when no equipment is needed.

Registration requirements and registration-period settings are independent of
the operational safety lifecycle. They do not block submission for safety checks
or confirmation. Attendee registration, waiting lists and rosters remain part of
the registration workflow.

Venue decisions, reservation changes, equipment request changes, venue edits,
and event edits re-evaluate confirmation in the writing transaction. The event
page polls every minute and reloads on focus. Its refresh RPC also completes
ended confirmed events that are visible to that authenticated user.

## Deployment

Apply these files in order using the Supabase SQL Editor:

1. `supabase/030_event_status_automation.sql` — guards, triggers and RPCs.
2. `supabase/031_schedule_event_completion.sql` — pg_cron completion every minute,
   including when no browser is open. Enable pg_cron first if required by the
   deployment's extension permissions.

Deploy migrations before the updated application. These changes have been tested
in embedded PostgreSQL with representative tables; they have not been applied to
the connected Supabase database. The live approval-copy function and existing RLS
must still be checked in staging, because their full deployed definitions are
not available in this repo. Cancellation retains booking and equipment history;
releasing allocations is outside this status-management change.

For an existing deployment, deploy the updated frontend and backend first, then
apply `supabase/053_remove_registration_readiness.sql`. The updated application
is compatible with the old schema, while the old application could still call
the RPC that this migration removes. The migration replaces the blocker and
lifecycle functions, removes the obsolete RPC and column, and promotes any
already safety-approved event that was waiting only on the removed gate.
PostgREST receives a schema reload notification from the migration; no dashboard
edits or other manual Supabase steps are required.

## Verification

```powershell
cd backend
python -m pytest tests -q -p no:cacheprovider
```

From the repository root, install the temporary database test engine in the
ignored frontend dependency directory, then execute the actual migrations:

```powershell
npm install --prefix frontend/node_modules/.event-status-qa @electric-sql/pglite --no-save --package-lock=false
node --test frontend/tests/event-status-db.mjs
node --test frontend/tests/registration-readiness-removal-db.test.mjs
```

The database tests cover transitions, required arrangements, quantities,
unauthorised actions, terminal states, stale venue bookings, and time-based
completion. They stub the separate venue suitability function, not the lifecycle
rules. pg_cron's scheduler and production RLS require staging verification.
