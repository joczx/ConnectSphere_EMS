# SCRUM-34 registration status integration tests

File: [test_view_my_registrations_integration.py](../backend/tests/integration/test_view_my_registrations_integration.py).

Run from `backend` in PowerShell:

```powershell
$env:RUN_INTEGRATION_TESTS = '1'
python -m pytest tests/integration/test_view_my_registrations_integration.py -v -p no:cacheprovider
```

Uses the existing `.env.integration-test` configuration and its development-project
guard. Request, venue, safety, registration and My Registrations migrations must
be applied. Fixture helpers from the SCRUM-33 integration file provide confirmed
events and cleanup; real temporary Attendee accounts keep these records separate
from pre-existing shared accounts.

| Case | AC | Integration check |
| --- | --- | --- |
| TC-SCRUM34-001 | AC1 | A fresh owner reads all three real registration records, with no-store. |
| TC-SCRUM34-002 | AC2 | Registered, waitlisted and withdrawn codes match the persisted workflows; three executions. |
| TC-SCRUM34-003 | AC3 | Event ID/name, timezone-aware start/end instants and the actual approved venue match persisted information. |
| TC-SCRUM34-004 | AC4 | A separate fresh Attendee receives an empty list with no-store. |
| TC-SCRUM34-005 | AC2 | A dedicated Attendee registers, reads Confirmed, withdraws through the real API, then reads Withdrawn and its timestamp. |
| TC-SCRUM34-006 | Supporting | No token returns 401 without calling the registration RPC. |
| TC-SCRUM34-007 | Supporting | Supplying the owner's ID cannot expose records to the empty Attendee; supplying the empty user's ID cannot override the real owner. |
| TC-SCRUM34-008 | AC4 | Controlled missing-function HTTP response returns 503 and exact configuration guidance, without a registrations list. |
| TC-SCRUM34-009 | AC4 | Controlled RPC transport outage returns 503, not an empty successful response. |
| TC-SCRUM34-010 | AC4 | A real Organiser token is refused by the database with 403 and no registrations list. |

There are **12 pytest instances for ten case IDs**. Generated IDs replace the
unit-test examples 41/42. The owner has three records to exercise every status;
one capacity-one event is filled by another temporary Attendee to produce a real
waiting-list record. A different event is withdrawn to produce the history row.
The subsequent-update test has its own account/event so it cannot change the
fixtures used by other status assertions.

Normal actions use real user tokens and the isolated database. Service-role
access is limited to arranging accounts, verifying stored values and scoped
cleanup. Cleanup removes only this run's fixture data and temporary accounts.

Cases 008/009 replace only the `my_event_registrations` HTTP transport, forwarding
real authentication and exercising the actual store/service/route translators.
No shared database function is dropped and no database service is stopped.
Case 006 uses a forwarding spy solely to prove the unauthenticated request never
calls the registration RPC.

The empty-state message and human-readable Confirmed/Waitlisted/Withdrawn labels
are rendered by React. This suite verifies their API inputs, not browser display;
see `frontend/e2e/my-registrations.spec.js` and
`frontend/tests/attendee-dashboard.test.mjs` for UI assertions.

JUnit output: `outputs/scrum34-integration-results.xml`.

## Verification

Live run on 4 November 2026: **12 passed in 46.84 seconds**. The run includes
real ownership checks, all three persisted statuses, withdrawal freshness and
the two controlled transport-failure cases. Fixture cleanup completed without
errors. No production code or database schema was changed.
