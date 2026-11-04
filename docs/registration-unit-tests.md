# Registration story unit tests

## Story-to-test-file mapping

This is the supplied inventory of **70 documented cases across seven stories**.
Each file link opens the Python unit tests for that story.

| Story | Listed cases | Test file | Current pytest instances |
| --- | --- | --- | --- |
| SCRUM-32: View an Event as an Attendee | 5 | [test_view_upcoming_events.py](../backend/tests/test_view_upcoming_events.py) | 26 |
| SCRUM-33: Register for an Event | 14 | [test_register_for_event.py](../backend/tests/test_register_for_event.py) | 26 |
| SCRUM-34: View Registration Status | 7 | [test_view_my_registrations.py](../backend/tests/test_view_my_registrations.py) | 12 |
| SCRUM-35: Withdraw Event Registration | 8 | [test_withdraw_event_registration.py](../backend/tests/test_withdraw_event_registration.py) | 10 |
| SCRUM-36: View Registration Information | 7 | [test_view_event_registrations.py](../backend/tests/test_view_event_registrations.py) | 12 |
| SCRUM-157: View Confirmed Event Information | 13 | [test_confirmed_event_information.py](../backend/tests/test_confirmed_event_information.py) | 29 |
| SCRUM-214: Set and Update Registration Period | 16 | [test_registration_period.py](../backend/tests/test_registration_period.py) | 33 |
| **Total** | **70** | **7 files** | **148** |

"Listed cases" counts rows in the supplied test-case inventory, not Python test
functions. Combined tests can cover several listed cases, parametrised tests run
once per input, and supporting tests may go beyond the original list. For
example, SCRUM-35 cases 001/003/004 share one successful-withdrawal test, while
capacity scenarios produce separate executions. Counts were checked with pytest
collection on 3 November 2026; they can change as tests are added.

## Run the seven unit-test files

From `backend`:

```powershell
python -m pytest tests/test_view_upcoming_events.py tests/test_register_for_event.py tests/test_view_my_registrations.py tests/test_withdraw_event_registration.py tests/test_view_event_registrations.py tests/test_confirmed_event_information.py tests/test_registration_period.py -q -p no:cacheprovider
```

These tests use mocked external services and need no live integration database.
Contact details remain required. SCRUM-33 AC5 now tests the on-screen confirmation
alert; the retired delivery-worker cases have been removed.
Latest full offline backend verification on 4 November 2026: **929 passed**.

The separate [SCRUM-32 integration tests](attendee-catalogue-integration-tests.md)
exercise the configured isolated Supabase project. Their results must not be
treated as results of the mocked unit tests listed above.

## Coverage commands

Run from `backend` to measure all six complete modules used by these stories:

```powershell
python -m coverage run --branch --source=app.schemas.registration,app.services.registration_service,app.routes.events,app.routes.venue_bookings,app.routes.equipment_requests,app.services.equipment_request_service -m pytest tests/ --ignore=tests/integration -q -p no:cacheprovider
python -m coverage report --fail-under=100 -m
python -m coverage html -d ../outputs/registration-full-coverage/html
```

Earlier recorded full-module result: **882 tests passed, with 100% statement and branch coverage**
across all six measured modules: **458/458 statements and 154/154 branches**.
The existing supporting tests cover the other workflows sharing these modules;
no extra tests, production changes or coverage exclusions were needed.
Live database integration tests are explicitly ignored. External services are
mocked; no production email is sent.

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

The earlier five-file audit gave 100% for 21 relevant functions,
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

## SCRUM-32: View an Event as an Attendee

`backend/tests/test_view_upcoming_events.py` currently collects 26 instances:

| AC | Case | API expectation |
| --- | --- | --- |
| AC1 | TC-SCRUM32-001 | Return multiple supplied upcoming confirmed events open for registration, with available capacity and no-store. |
| AC2 | TC-SCRUM32-002 | Preserve the twelve supplied event/venue detail fields, including dates, times and registration settings. |
| AC3 | TC-SCRUM32-003 | Fetch changed confirmed name, description, venue and times on a second read, with no-store on both responses. |
| AC4 | TC-SCRUM32-004 | Return an already-empty mocked catalogue for cancelled and closed scenario labels. |

One instance checks authentication, and three additional instances check missing
RPC configuration, an unavailable database and a refused catalogue request.
TC-SCRUM32-004 follows the supplied
test specification: its two labels use `{'events': []}`. It does not supply
cancelled/closed rows or test whether filtering removes them. Similarly, venue
fields in AC2/AC3 are supplied by a mock, not retrieved by a real lookup. These
unit tests also supply cancelled, closed, past, malformed and timezone-free
records to the real API filter, check exact time boundaries, verify public-field
projection, and verify cancellation between successive reads. Those regression tests
check actual date-based filtering even against the older RPC, while the original empty-list
case remains a response-contract test. The suite does not prove the complete
SQL/UI implementation. Run from `backend`:

```powershell
python -m pytest tests/test_view_upcoming_events.py -q -p no:cacheprovider
```

## SCRUM-214: Set and Update Registration Period

`backend/tests/test_registration_period.py` currently collects 33 instances. Run from
`backend` with:

```powershell
python -m pytest tests/test_registration_period.py -q -p no:cacheprovider
```

| AC | Python unit-test cases |
| --- | --- |
| AC1 | `test_tc_scrum214_001_004_ac1_ac4_set_dates_and_waiting_list`; authentication, unassigned-organiser refusal and confirmed-stage checks. |
| AC2 | `test_tc_scrum214_002_ac2_invalid_order_is_rejected_before_database_call`; equal/before opening, timezone and fractional-second ordering. |
| AC3 | `test_tc_scrum214_003_ac3_updates_existing_period_when_store_allows_it`; before/during scenarios and the closed-period refusal response. |
| AC4 | Both enabled and disabled waiting-list values in TC-SCRUM214-001/004; invalid preference types are rejected by schema tests. |
| AC5 | `test_tc_scrum214_005_007_ac5_ac7_registration_outcomes_and_messages`; successful open-period response and not-open/closed refusals. |
| AC6 | `test_tc_scrum214_006_ac6_attendee_reads_updated_period_after_save`; reads before/after a save, changed opening/closing/preference and no-store headers. |
| AC7 | Not-open/closed API error wording in TC-SCRUM214-005/007; unavailable events are now hidden from the catalogue under SCRUM-32 AC4. |

The before/during fixtures and not-open/closed outcomes are mocked database
decisions. They verify the Python API contract, not real clock boundary
enforcement. Visible React messages and the SQL permission/timing rules need
their own tests; Python mocks cannot establish full implementation of those ACs.

## Limits of the AC assertions

Supabase calls are mocked. These tests assert the Python API contract; they do
not prove database role/assignment enforcement, actual registration timing,
capacity calculation, notification delivery, or the visible UI labels/messages.
In SCRUM-157, AC4 checks mixed-status filtering through `/api/events?status=confirmed`;
the unfiltered management list still includes all lifecycle stages. Passing unit tests and 100% Python
function coverage do not establish that every story is fully implemented.
