# SCRUM-157 confirmed event information integration tests

File: [test_confirmed_event_information_integration.py](../backend/tests/integration/test_confirmed_event_information_integration.py).

```powershell
cd backend
$env:RUN_INTEGRATION_TESTS = '1'
python -m pytest tests/integration/test_confirmed_event_information_integration.py -v -p no:cacheprovider
```

Uses only `backend/.env.integration-test`, real role tokens, API requests and database functions. Fixtures create an event, approve a venue booking, reserve and accept two equipment units with HDMI requirements, and approve safety checks. Fixture teardown removes its equipment requests/reservations before shared scoped cleanup removes its events, venues, notifications and temporary user.

| Case | AC | Coverage |
| --- | --- | --- |
| 001 | AC1 | Both manager roles retrieve confirmed date/time and approved venue; caching disabled. |
| 002 | AC2 | Accepted equipment, requested/accepted quantity 2, HDMI requirements and assigned Technical Support ID. |
| 003 | AC3 | Real Organiser saves period; forwarding spy checks UTC normalisation, then real event retrieval verifies persistence. |
| 004 | AC4 | Mixed real planning and confirmed data; asserts `/api/events?status=confirmed` contains confirmed events only and excludes the planning fixture. This is an acceptance assertion, not a mocked confirmed-only response. |
| 005 | AC3 | Missing fields, malformed dates, missing timezone, non-boolean waiting list and closing before opening return 400 without RPC. |
| 006 | AC3 | Real Coordinator cannot change registration period; 403 and no event data. |
| 007 | AC3 | Real planning, pending-safety and cancelled events reject settings with 409 without registration RPC. Completed remains covered only by existing unit tests; this suite does not bypass lifecycle guards to manufacture completed events. |

Only cases 001-007 are retained in this integration file. There are 14 integration executions, including role and validation variants. IDs and equipment names are generated to avoid collisions; illustrative IDs and dates in the test specification are not hard-coded. The API implements the requested confirmed-only filter. The unfiltered `/api/events` management list still includes every lifecycle stage. No shared database functions are changed.

## Coverage limits and verification

Verified on 4 November 2026: **14 passed, 0 failed, 0 skipped** in 39.67 seconds, including cleanup. The 94 affected unit tests also passed. Supabase emitted 20 dependency deprecation warnings. JUnit evidence: `outputs/scrum157-integration-results.xml`.

TC-004 uses `/api/events?status=confirmed` with real planning and confirmed event fixtures. API filtering excludes non-confirmed rows; no catalogue response is mocked. The shared management list `/api/events` retains its existing behaviour.

Useful additional coverage, if required:

- A completed event for TC-007 (currently covered only by unit tests).
- An empty confirmed catalogue in the live project for TC-004 (the unit test covers mixed input with no confirmed rows).
- Missing authentication and an unassigned user's access to event/equipment/venue details, especially given the earlier unassigned-event access finding.

The unit AC4 test also checks mixed input with and without a confirmed event. Supporting unit tests remain in their existing file.
