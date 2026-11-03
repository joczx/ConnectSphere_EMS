# Registration story unit tests

Run from the repository root:

```powershell
python backend/run_registration_story_tests.py
```

This runs exactly these five files, without a database or email delivery:

| Story | Test file | Passing cases |
| --- | --- | --- |
| SCRUM-33 | `backend/tests/test_register_for_event.py` | 25 |
| SCRUM-34 | `backend/tests/test_view_my_registrations.py` | 9 |
| SCRUM-35 | `backend/tests/test_withdraw_event_registration.py` | 8 |
| SCRUM-36 | `backend/tests/test_view_event_registrations.py` | 10 |
| SCRUM-157 | `backend/tests/test_confirmed_event_information.py` | 29 |
| Total | | 81 |

## Coverage scope

The runner requires **100% statement and branch coverage for the 21 Python
functions listed in its `FUNCTIONS` mapping**. This includes the complete
registration validation and shared registration service functions, the relevant
event handlers, event ID validation and error handlers, and the venue/equipment
read functions exercised by SCRUM-157. The two registration modules also have
100% coverage as complete modules.

No production code or coverage exclusions were changed to reach the target.
The runner saves JSON, HTML and text reports under
`outputs/registration-story-coverage/`, and exits unsuccessfully if any test fails
or any listed function has uncovered statements or branches.

Shared modules also implement unrelated workflows. Their complete-module report
is printed separately; it is **not 100%** (48% across the six measured modules in
this run). This is not whole-backend coverage. Shared authentication internals,
SQL execution and React rendering are outside this gate.

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
