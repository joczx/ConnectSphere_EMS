# SCRUM-214 registration period integration tests

File: [test_registration_period_integration.py](../backend/tests/integration/test_registration_period_integration.py).

```powershell
cd backend
$env:RUN_INTEGRATION_TESTS = '1'
python -m pytest tests/integration/test_registration_period_integration.py -v -p no:cacheprovider
```

Requires the separate test project and role credentials in `backend/.env.integration-test`. Shared fixtures reject the development project URL. Normal requests use real role tokens, API routes and database functions. Service-key requests verify persisted values; shared fixtures clean up owned events, venues, registrations, notifications and temporary users.

| Case | AC | Integration coverage |
| --- | --- | --- |
| TC-SCRUM214-001 | AC1 | Initially unset confirmed event accepts opening/closing dates; response and persisted values match; forwarding spy checks UTC arguments. |
| TC-SCRUM214-002 | AC2 | Closing before or equal to opening returns 400 without RPC or data changes. |
| TC-SCRUM214-003 | AC3 | Update both dates before opening and during registration; verify returned and stored changes. |
| TC-SCRUM214-004 | AC4 | Enable and disable waiting list on confirmed events; verify real persistence and RPC preferences. Shares setup with 001. |
| TC-SCRUM214-005 | AC5 | Real registration succeeds only in the open period; early/late attempts return 409 without a registration row. |
| TC-SCRUM214-006 | AC6 | Attendee catalogue shows updated opening and closing after an Organiser saves them; no-store headers on both reads. |
| TC-SCRUM214-007 | AC7 | Exact not-yet-open and closed registration messages. Shares workflow with 005. |
| TC-SCRUM214-008 | AC2 | Invalid date, missing timezone, null opening, invalid waiting-list type and unexpected field return field errors without RPC or data changes. |
| TC-SCRUM214-009 | AC2 | Singapore opening and UTC closing 100 milliseconds later are accepted and persisted as matching instants. |
| TC-SCRUM214-010 | AC1 supporting | No authentication returns 401 without registration RPC. |
| TC-SCRUM214-011 | AC2 | Real database rejects closing after event start with field-specific error; dates unchanged. |
| TC-SCRUM214-012 | AC2 supporting | Injected RPC refusal without status becomes HTTP 400 and exact error; no save. |
| TC-SCRUM214-013 | AC3 | Closed registration period cannot be reopened; real 409 and unchanged dates. |
| TC-SCRUM214-014 | AC1 supporting | Separate unassigned Organiser cannot save dates; 403 and unchanged settings. |
| TC-SCRUM214-015 | AC7 | Current requirement: not-open and closed events are hidden from attendee catalogue; visible events include the restored `registration_status` field. |
| TC-SCRUM214-016 | AC1, AC3 supporting | Planning, pending-safety and cancelled events reject settings before registration RPC. Completed and null stages remain covered by unit tests only. |
| TC-SCRUM214-017 | AC1, AC3 | Missing-RPC transport failure returns 503, exact configuration guidance and no event; settings unchanged. |
| TC-SCRUM214-018 | AC1, AC3 | Transport outage returns 503 and service-unavailable error without event; settings unchanged. |

28 executions cover the case variants. Cases 012/017/018 inject only the period RPC HTTP transport; real authentication and event reads continue. No shared database function is removed or modified. Forwarding spies call the real service.

The event availability field `registration_status` has been restored at the API boundary and is derived from current dates. Events outside the registration window remain hidden, so returned catalogue rows have status `open`. The attachment's expectation of visible not-open/closed events still differs from the current visibility requirement. Attendee registration status (`registered`, `waiting_list`, `withdrawn`) is separate and unchanged.

Example event IDs and fixed 2027 dates are replaced with generated IDs and times relative to the run, avoiding stale timing data. Exact clock equality at opening/closing is not asserted across live HTTP calls. These tests check API messages rather than browser rendering. SCRUM-33's integration suite separately tests full-capacity behaviour with waiting lists enabled/disabled.

Verified on 4 November 2026: **28 passed, 0 failed, 0 skipped** in 113.51 seconds, including cleanup. Supabase emitted 64 dependency deprecation warnings. JUnit evidence: `outputs/scrum214-integration-results.xml`.

Restored availability field: 929 backend unit tests passed before the new regression cases were added; the affected suites then passed all 66 tests, including seven new status/boundary cases. The updated live cases 006/015 were not run because the execution approval was declined. The earlier 28-pass result predates this field restoration. No remote SQL migration is needed for the backend API to derive the field.
