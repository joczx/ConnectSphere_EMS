# Registration story unit tests

Run from `backend` to measure all six complete modules used by these stories:

```powershell
python -m coverage run --branch --source=app.schemas.registration,app.services.registration_service,app.routes.events,app.routes.venue_bookings,app.routes.equipment_requests,app.services.equipment_request_service -m pytest tests/ --ignore=tests/integration -q -p no:cacheprovider
python -m coverage report --fail-under=100 -m
python -m coverage html -d ../outputs/registration-full-coverage/html
```

Verified result: **882 tests pass, with 100% statement and branch coverage**
across all six measured modules: **458/458 statements and 154/154 branches**.
The existing supporting tests cover the other workflows sharing these modules;
no extra tests, production changes or coverage exclusions were needed.
Live database integration tests are explicitly ignored. External services are
mocked; no production email is sent.

The five story-specific test files remain:

| Story | Test file | Passing cases |
| --- | --- | --- |
| SCRUM-33 | `backend/tests/test_register_for_event.py` | 25 |
| SCRUM-34 | `backend/tests/test_view_my_registrations.py` | 9 |
| SCRUM-35 | `backend/tests/test_withdraw_event_registration.py` | 8 |
| SCRUM-36 | `backend/tests/test_view_event_registrations.py` | 10 |
| SCRUM-157 | `backend/tests/test_confirmed_event_information.py` | 29 |
| Total | | 81 |

## Coverage scope

The full-module run covers these entire Python source files, including their
imports and all functions:

- `app/schemas/registration.py` — 100%
- `app/services/registration_service.py` — 100%
- `app/routes/events.py` — 100%
- `app/routes/venue_bookings.py` — 100%
- `app/routes/equipment_requests.py` — 100%
- `app/services/equipment_request_service.py` — 100%

The report command exits unsuccessfully if measured coverage falls below 100%.
The HTML report identifies uncovered lines and branches when a future change
introduces a gap. The recorded text report is under
`outputs/registration-full-coverage/summary.txt`.

Running only the five story files gives 100% for their 21 relevant functions,
but 48% across the complete six shared modules. Use the full offline suite above
to obtain complete module coverage. This is not whole-backend coverage: shared
authentication internals, SQL execution and React rendering remain outside the
six-module scope.

## Consolidation

- SCRUM-34's duplicate empty/nonempty API test was removed. The ignored client
  attendee ID check was retained in the common request helper.
- SCRUM-35's success, returned status and confirmation assertions now share one
  test with all three case IDs. The ignored client attendee ID check was retained.
  Identical mocked at/after-start refusals were combined, and the repeated 409
  refusal was removed. Capacity scenarios remain separate.
- SCRUM-36's authorised roster, contact details and status assertions now share
  one test, retaining each case ID. The client organiser ID remains ignored.
  Duplicate unauthorised-response tests were removed; organiser, coordinator and
  attendee refusal cases remain.
- Missing registration-setting validation, service error, event lookup, venue
  refusal and equipment authentication paths were added with meaningful assertions.

## Limits of the AC assertions

Supabase calls are mocked. These tests assert the Python API contract; they do
not prove database role/assignment enforcement, actual registration timing,
capacity calculation, notification delivery, or the visible UI labels/messages.
In SCRUM-157, AC4 supplies an already-confirmed-only list; the shared events API
does not itself filter mixed statuses. Passing unit tests and 100% Python
function coverage do not establish that every story is fully implemented.
