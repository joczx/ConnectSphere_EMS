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
| Pre-opening behaviour | AC1 | A confirmed event is hidden before opening, and an actual early registration request returns 409. |
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

The current requirement is that events are hidden until registration opens.
The suite checks both pre-opening invisibility and a real early-registration
refusal. The JUnit report is `outputs/scrum32-integration-results.xml`.
Live verification on 4 November 2026: **10 passed in 58.01 seconds**, including
pre-opening invisibility, refusal of early registration and successful cleanup.

## AC4 fix and database rollout

The backend catalogue now compares the actual dates: it requires a confirmed
event, `opening <= now < closing`, and a future start/end time. Events are hidden
before opening and after closing. Direct early-registration attempts still return
"Registration is not yet open." It does not use
or expose a derived registration-status field. The API projects only the public
event fields, including when an older RPC returns additional legacy fields.
This supports databases still running the older RPC. Registration attempts outside the window continue
to return the existing not-open/closed refusal messages. My Registrations keeps
historical and cancelled events, as before.

Apply [migration 060](../supabase/060_hide_events_before_registration_opens.sql)
after 059 in the intended Supabase project's SQL Editor. It restricts the RPC
itself to confirmed upcoming events with `opening <= now < closing`, preserves
venue information and access checks, omits the derived field, and is safe to reapply. No live schema was
changed automatically: no integration-project SQL connection is configured.

The registration workflow and migration are tested in isolated PGlite:

```powershell
node --test frontend/tests/registration-db.mjs
```

The Playwright cancelled-event assertion is a normal test without an expected
failure marker. Browser display also has a pre-opening hidden-event case.

## End-to-end checks

From `frontend`, with ports 5000 and 5173 available:

```powershell
npx --no-install playwright test e2e/attendee-events.spec.js e2e/registration-period.spec.js
```

The catalogue checks wait for a successful API response and a known open event
to render before asserting absence. This prevents an empty loading screen from
passing a hidden-event assertion. The refresh scenario postpones an existing
event's opening, verifies it disappears, restores the actual previous period in
`finally`, and verifies it reappears. Registration-period tests check that a
hidden event becomes visible only after its opening is moved into the past.

On 4 November 2026 both updated files passed `node --check`. The browser run
could not start because port 5000 was already occupied; no E2E pass result is
claimed for this update. Playwright's integration server must own the test ports
so tests cannot accidentally run against an unrelated backend.
