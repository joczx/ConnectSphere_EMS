# SCRUM-35 withdrawal integration tests

Test file: [test_withdraw_event_registration_integration.py](../backend/tests/integration/test_withdraw_event_registration_integration.py).

Run in PowerShell from the project root:

```powershell
cd backend
$env:RUN_INTEGRATION_TESTS = '1'
python -m pytest tests/integration/test_withdraw_event_registration_integration.py -v -p no:cacheprovider
```

Requires the separate test project's credentials and role accounts in `backend/.env.integration-test`. The shared integration fixtures reject the development project URL. Tests create their own event data and temporary users and clean them up afterward.

| Case | AC | Integration assertion |
| --- | --- | --- |
| TC-SCRUM35-001 | AC1 | Real authenticated withdrawal before the event starts returns HTTP 200 and the registration. |
| TC-SCRUM35-002 | AC2 | Withdrawal after the start returns HTTP 409, only the expected error, and leaves the stored registration unchanged. |
| TC-SCRUM35-003 | AC3 | Returned and persisted registration status is `withdrawn`; withdrawal timestamps match. |
| TC-SCRUM35-004 | AC4 | Exact success message, no error, and `Cache-Control: no-store`. |
| TC-SCRUM35-005 | AC5 | Capacity increases for a registered attendee, including a full event; withdrawing a waitlisted attendee releases no place. Checks the response, catalogue and stored registration counts. |
| TC-SCRUM35-006 | AC1 supporting | Missing authentication returns HTTP 401 without calling the registration RPC. |
| TC-SCRUM35-007 | AC1 supporting | A real Event Organiser receives HTTP 403; registration remains unchanged. |
| TC-SCRUM35-008 | AC1 supporting | Another Attendee without a registration receives HTTP 404 and cannot affect the owner's record. |
| TC-SCRUM35-009 | AC4 | Missing RPC produces HTTP 503 and configuration guidance, with no confirmation or data change. |
| TC-SCRUM35-010 | AC4 | Database transport failure produces HTTP 503 and the unavailable-service error, with no confirmation or data change. |

Cases 001, 003 and 004 share one successful workflow to avoid duplicate setup. Case 005 has three parameter variants, resulting in **10 pytest executions** overall.

Normal scenarios use real authentication, API routes and database functions. Cases 009 and 010 inject faults only at the withdrawal RPC transport; authentication remains real. Case 006 spies on the RPC to verify it is not called.

For case 002, setup creates a historical registration on a planning event using the test service key, without disabling triggers or changing a confirmed event. Withdrawal then uses the real attendee token and RPC. This verifies the after-start guard; exact equality with the event start time is not tested across the live HTTP/database clocks.

Verified on 4 November 2026: **10 passed, 0 failed, 0 skipped** in 58.94 seconds. JUnit evidence: `outputs/scrum35-integration-results.xml`.
