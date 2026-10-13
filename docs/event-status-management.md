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
| Planning → Confirmed | Matching approved suitable venue; full equipment reservations; registration readiness |
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

Registration readiness defaults to false. Only the assigned coordinator can
acknowledge it, from the event detail page. No acknowledgement is needed when
there are no registration requirements. Changing those requirements clears the
acknowledgement. This acknowledgement confirms arrangements, not attendee counts.

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
```

The database tests cover transitions, required arrangements, quantities,
unauthorised actions, terminal states, stale venue bookings, and time-based
completion. They stub the separate venue suitability function, not the lifecycle
rules. pg_cron's scheduler and production RLS require staging verification.
