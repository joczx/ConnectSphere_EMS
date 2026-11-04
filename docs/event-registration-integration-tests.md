# SCRUM-33 registration integration tests

File: [test_register_for_event_integration.py](../backend/tests/integration/test_register_for_event_integration.py).

From `backend` in PowerShell:

```powershell
$env:RUN_INTEGRATION_TESTS = '1'
python -m pytest tests/integration/test_register_for_event_integration.py -v -p no:cacheprovider
```

The existing integration conftest loads `.env.integration-test`, checks required
credentials and refuses the development project URL. The test role accounts and
the request, venue, safety, registration migrations including 061 must be configured.

The retained case IDs 001--014 map to 27 executions, including extra AC4 capacity and
pre-opening refusal scenarios. Combined cases 003/009 avoid duplicate validation
tests, and use distinct parameter labels for missing/unsafe input.

| Case | AC | Integration check |
| --- | --- | --- |
| TC-SCRUM33-001 | AC1, AC2, AC5 | Actual registration succeeds; persisted attendee identity and all supplied details match the API confirmation. |
| TC-SCRUM33-002 | AC2 | Padded name, email and phone are trimmed before actual persistence. |
| TC-SCRUM33-003 | AC3 | Each mandatory field is omitted separately; blank/long names and invalid phone are rejected without registrations. |
| TC-SCRUM33-004 | AC3 | Empty JSON is refused; a forwarding spy verifies no registration RPC is called; real database remains unchanged. |
| TC-SCRUM33-005 | AC1 | An actually closed period returns 409 and the closed message. |
| TC-SCRUM33-006 | Supporting | A real Organiser token is refused by the database as a non-attendee. |
| TC-SCRUM33-007 | Supporting | Missing authentication returns 401. |
| TC-SCRUM33-008 | AC3 | Injected structured RPC refusal preserves fields and defaults to HTTP 400. |
| TC-SCRUM33-009 | AC3 | Numeric/control-character names, email header injection and digit-free phone are rejected. |
| TC-SCRUM33-010 | AC2, AC3 | Malformed email syntax is accepted and persisted under the current contact-email rule. |
| TC-SCRUM33-011 | Supporting | Injected PostgREST missing-function HTTP error becomes configuration guidance and 503. |
| TC-SCRUM33-012 | Supporting | Injected database permission failure reaches the HTTP boundary as 403 without leaking internal database wording. |
| TC-SCRUM33-013 | Supporting | Injected non-object RPC result is forwarded; actual serialized event ID and detail arguments are checked. |
| TC-SCRUM33-014 | Supporting | Constraint, expired-auth and outage transport failures return safe 409/401/503 responses. |
| Additional capacity scenarios | AC4 | A capacity-one event accepts one confirmed attendee; another is refused without a waiting list, or is explicitly waitlisted when enabled. Confirmed count remains one. |
| Additional pre-opening scenario | AC1 | Registration before opening returns 409 and creates no row. |

## Isolation and test boundaries

Normal events are taken through real request approval, approved venue booking and
safety approval. Service-role calls are limited to fixture setup, verification,
and cleanup. Requests under test use real authenticated user tokens. The filler
Attendee is a temporary account removed after the scenario data is cleaned up.

Cases 008 and 011--014 are controlled HTTP-transport fault tests, forwarding real
authentication requests and exercising the real JSON/error translators. They do
not drop RPC functions, stop the shared database, or mock the service result.
Case 012 checks the public HTTP outcome instead of Python exception object
identity, which is meaningful only at the unit-test boundary.

AC5 is the on-screen success alert. Case 001 verifies its API message and
persisted registration. The old delivery-only cases 015/016 have been removed;
the production sender has been removed as well. Browser alert rendering is
checked in `frontend/e2e/register.spec.js` and the React component test.

Fixtures remove only the run's events, registrations, requests,
bookings, venues, uniquely named notifications and temporary user accounts.
The report command used for verification writes JUnit results to
`outputs/scrum33-integration-results.xml`.

## Verification on 4 November 2026

After updating AC5 to alert confirmation and removing delivery-worker cases,
the live run completed with **27 passed in 113.10 seconds** and successful
fixture cleanup. The full offline backend suite has **929 passing tests**.
The React confirmation-alert test, isolated database migration/workflow test
and frontend build also pass.

Apply `supabase/061_remove_registration_confirmation_email.sql` after 060 to the
intended remote project to stop legacy database queuing and remove its old queue
table. This migration was verified locally, not applied remotely. The API already
returns only the registration and alert message, including with the older RPC.

