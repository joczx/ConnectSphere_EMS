# SCRUM-32 integration tests

The test file is
[test_view_upcoming_events_integration.py](../backend/tests/integration/test_view_upcoming_events_integration.py).

Run from `backend` in PowerShell:

```powershell
$env:RUN_INTEGRATION_TESTS = '1'
python -m pytest tests/integration/test_view_upcoming_events_integration.py -v -p no:cacheprovider
```

The integration conftest loads `.env.integration-test`, requires service and
publishable credentials, and refuses the development project URL. Configure
Attendee, Event Organiser, Coordinator Lead, Coordinator, Venue Staff and Safety
Officer accounts. Apply the venue/safety workflow migrations, registration
migrations 046--050, and migration 058 for attendee venue names.

| Case | AC | Check |
| --- | --- | --- |
| TC-SCRUM32-001 | AC1 | Two persisted upcoming confirmed events open for registration, with capacity and no-store. |
| TC-SCRUM32-002 | AC2 | Stored name, description, dates/times, registration settings, capacity and approved venue. |
| TC-SCRUM32-003 | AC3 | A real permitted registration-setting change appears on the next attendee read. |
| TC-SCRUM32-004 | AC4 | This run's cancelled and closed events are excluded; two executions. |
| Pre-opening behaviour | AC1 | A configured confirmed event is visible before opening, but an actual registration request returns 409. |
| TC-SCRUM32-005 | Supporting | Unauthenticated requests are refused. |
| TC-SCRUM32-006 | AC1 | Missing-function HTTP response produces setup guidance and 503. |
| TC-SCRUM32-007 | AC1 | RPC transport outage produces 503 instead of an empty successful result. |
| TC-SCRUM32-008 | AC1 | Real non-attendee token is refused by the database. |

There are **10 pytest instances for eight case IDs**. Cases 006/007 use controlled
HTTP transport faults while keeping authentication real. No shared function is
dropped and no service is stopped. The other cases use the real isolated project.

Events are created through request approval, approved venue booking and safety
approval. TC-003 has its own event and changes registration settings because
confirmed arrangements cannot be edited directly. TC-004 checks the absence of
owned ineligible records without deleting other suites' data to force a globally
empty catalogue. Cleanup is limited to the run's events, requests, bookings,
venues and uniquely named notifications.

The initial live run recorded **7 passed and 3 failed**: TC-004 exposed that the
catalogue still returned cancelled, closed and not-open events. These tests are
not skipped or marked as expected failures.

The user clarified that pre-opening events must be visible. The current suite
therefore replaces the old not-open exclusion assertion with a positive visibility
test and a real early-registration refusal. The JUnit report is
`outputs/scrum32-integration-results.xml`.
Live verification on 3 November 2026: **10 passed in 57.19 seconds**, including
visibility before opening, rejection of early registration and successful cleanup.

## AC4 fix and database rollout

The backend catalogue now compares the actual dates: it requires a confirmed
event, configured valid opening/closing times, `now < closing`, and a future
start/end time. Events are visible before opening, with the Register button
disabled and a "Registration is not yet open." message. Registration itself
still requires `opening <= now < closing`. It does not use
or expose a derived registration-status field. The API projects only the public
event fields, including when an older RPC returns additional legacy fields.
This supports databases still running the older RPC. Registration attempts outside the window continue
to return the existing not-open/closed refusal messages. My Registrations keeps
historical and cancelled events, as before.

Apply [migration 059](../supabase/059_filter_attendee_registration_events.sql)
after 058 in the intended Supabase project's SQL Editor. It restricts the RPC
itself to confirmed upcoming events with configured times and `now < closing`, preserves
venue information and access checks, omits the derived field, and is safe to reapply. No live schema was
changed automatically: no integration-project SQL connection is configured.

The SQL migration is tested in isolated PGlite with exact opening/closing/start
boundaries, cancelled/completed states, empty results and access refusals:

```powershell
node --test frontend/tests/attendee-catalogue-db.test.mjs frontend/tests/registration-db.mjs
```

The React component test verifies that pre-opening events render with a disabled
Register button and that controls enable during the registration window:

```powershell
node --test frontend/tests/attendee-event-availability.test.mjs
```

The Playwright cancelled-event assertion is a normal test without an expected
failure marker. Browser display also has a pre-opening visible/disabled case.
