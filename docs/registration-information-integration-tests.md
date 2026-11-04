# SCRUM-36 registration information integration tests

File: [test_view_event_registrations_integration.py](../backend/tests/integration/test_view_event_registrations_integration.py).

Run from the project root in PowerShell:

```powershell
cd backend
$env:RUN_INTEGRATION_TESTS = '1'
python -m pytest tests/integration/test_view_event_registrations_integration.py -v -p no:cacheprovider
```

Requires the separate test project credentials and role accounts in `backend/.env.integration-test`. Shared fixtures reject the development project URL. Temporary users, events and registrations are removed after the module finishes.

| Case | AC | Checks |
| --- | --- | --- |
| TC-SCRUM36-001 | AC1 | Real owning Organiser and assigned Coordinator can retrieve the roster; HTTP 200 and no-store. |
| TC-SCRUM36-002 | AC2 | Alex Tan, Jamie Lim and Sam Lee have the expected IDs, names, contact emails and phone numbers; compare API responses with persisted records. |
| TC-SCRUM36-003 | AC3 | Real registered totals 0, 1 and 3 are counted separately from one waitlisted and one withdrawn record. |
| TC-SCRUM36-004 | AC4 | Real registered, waiting_list and withdrawn statuses and applicable withdrawal timestamps are returned. |
| TC-SCRUM36-005 | AC5 | Separate unassigned Organiser and Coordinator accounts get 404; an Attendee gets 403; each response contains only the error. |
| TC-SCRUM36-006 | AC3 | Empty events return zero totals and an empty list to either manager role. |
| TC-SCRUM36-007 | AC1, AC5 | Missing authentication returns 401 without calling the registration RPC. |
| TC-SCRUM36-008 | AC1, AC5 | Injected missing-RPC transport error returns 503 and exact configuration guidance, without exposing data. |
| TC-SCRUM36-009 | AC1, AC5 | Injected database transport outage returns 503 and the exact service error, without exposing data. |

Cases 001, 002 and 004 share one workflow, run for each manager role. Parameterised counts, roles and failures produce 13 pytest executions in total. Normal scenarios use real authentication, registration, withdrawal and roster database functions. Only cases 008/009 inject transport faults; authentication still reaches the test project. Contact emails are registration details; these tests send no email.

Generated event and user IDs replace illustrative IDs such as 41. Counts and statuses are arranged through actual attendee registration and withdrawal requests, rather than mocked roster results. Assertions do not depend on roster ordering.

Verified on 4 November 2026: **13 passed, 0 failed, 0 skipped** in 56.21 seconds, including fixture cleanup. Supabase emitted 20 dependency deprecation warnings about its HTTP client configuration. JUnit evidence: `outputs/scrum36-integration-results.xml`.
