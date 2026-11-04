# Workbook user stories: E2E file mapping

Source: `Compiled User Stories.xlsx`. Distinct story IDs are deduplicated across the raw export and Sprint 1-4; repeated IDs use the latest sprint definition. Older assignment workflows use the latest implemented Lead-managed flow, as agreed. The workbook was read only and was not changed.

One specification file is mapped to each of the **62 distinct story IDs**. **61 files contain executable browser scenarios**. SCRUM-5 has a gap file because the workbook supplies no description/ACs and the application has no self-registration UI; no dummy passing/skipped case was invented.

```powershell
cd frontend
$env:PLAYWRIGHT_CHANNEL = 'msedge'
npx playwright test --config playwright.stories.config.js
```

Use `npx playwright show-report` afterward. The full run uses the real integration project, existing role accounts and isolated local ports 5001/5174. The seven attendee-registration files retain their existing global event-fixture setup/teardown. New story arrangements are per test, uniquely named and cleaned up in fixture teardown. No API responses are mocked. Secrets are loaded from `backend/.env.integration-test`; do not commit that file.

To list without creating fixtures or contacting the database:

```powershell
npx playwright test --config playwright.stories.config.js --list
```

To run a new story independently without the attendee-fixture setup:

```powershell
$env:E2E_SKIP_REGISTRATION_FIXTURES = '1'
npx playwright test --config playwright.stories.config.js create-submit-event-request.spec.js
```

Remove `E2E_SKIP_REGISTRATION_FIXTURES` before running the entire workbook suite; that option excludes the seven specs requiring global registration data. Playwright Chromium can be used instead by omitting `PLAYWRIGHT_CHANNEL` after installing its browser.

| Story | Specification | Notes |
| --- | --- | --- |
| SCRUM-5 | [user-registration.spec.js](../frontend/e2e/user-registration.spec.js) | Blocked: missing ACs and signup implementation |
| SCRUM-6 | [authentication-authorisation.spec.js](../frontend/e2e/authentication-authorisation.spec.js) | Browser scenarios added |
| SCRUM-7 | [create-submit-event-request.spec.js](../frontend/e2e/create-submit-event-request.spec.js) | Browser scenarios added |
| SCRUM-8 | [draft-event-request.spec.js](../frontend/e2e/draft-event-request.spec.js) | Browser scenarios added |
| SCRUM-9 | [review-event-request.spec.js](../frontend/e2e/review-event-request.spec.js) | Browser scenarios added |
| SCRUM-10 | [planning-event-information.spec.js](../frontend/e2e/planning-event-information.spec.js) | Browser scenarios added |
| SCRUM-11 | [search-filter-venues.spec.js](../frontend/e2e/search-filter-venues.spec.js) | Browser scenarios added |
| SCRUM-12 | [venue-suitability.spec.js](../frontend/e2e/venue-suitability.spec.js) | Browser scenarios added |
| SCRUM-13 | [request-equipment.spec.js](../frontend/e2e/request-equipment.spec.js) | Browser scenarios added |
| SCRUM-14 | [review-equipment-request.spec.js](../frontend/e2e/review-equipment-request.spec.js) | Browser scenarios added |
| SCRUM-15 | [equipment-availability.spec.js](../frontend/e2e/equipment-availability.spec.js) | Browser scenarios added |
| SCRUM-16 | [reserve-equipment.spec.js](../frontend/e2e/reserve-equipment.spec.js) | Browser scenarios added |
| SCRUM-17 | [manage-equipment-reservation.spec.js](../frontend/e2e/manage-equipment-reservation.spec.js) | Browser scenarios added |
| SCRUM-20 | [amend-event-request.spec.js](../frontend/e2e/amend-event-request.spec.js) | Browser scenarios added |
| SCRUM-21 | [assign-event-coordinator-legacy.spec.js](../frontend/e2e/assign-event-coordinator-legacy.spec.js) | Uses latest Lead-managed workflow; historical ACs superseded |
| SCRUM-22 | [event-status-management.spec.js](../frontend/e2e/event-status-management.spec.js) | Browser scenarios added |
| SCRUM-23 | [update-event-information.spec.js](../frontend/e2e/update-event-information.spec.js) | Browser scenarios added |
| SCRUM-24 | [create-venue-catalogue.spec.js](../frontend/e2e/create-venue-catalogue.spec.js) | Browser scenarios added |
| SCRUM-25 | [view-venue-catalogue.spec.js](../frontend/e2e/view-venue-catalogue.spec.js) | Browser scenarios added |
| SCRUM-26 | [update-venue-catalogue.spec.js](../frontend/e2e/update-venue-catalogue.spec.js) | Browser scenarios added |
| SCRUM-27 | [delete-venue-catalogue.spec.js](../frontend/e2e/delete-venue-catalogue.spec.js) | Browser scenarios added |
| SCRUM-28 | [venue-availability-calendar.spec.js](../frontend/e2e/venue-availability-calendar.spec.js) | Browser scenarios added |
| SCRUM-29 | [request-venue-bookings.spec.js](../frontend/e2e/request-venue-bookings.spec.js) | Browser scenarios added |
| SCRUM-30 | [review-venue-booking.spec.js](../frontend/e2e/review-venue-booking.spec.js) | Browser scenarios added |
| SCRUM-31 | [venue-booking-conflicts.spec.js](../frontend/e2e/venue-booking-conflicts.spec.js) | Browser scenarios added |
| SCRUM-32 | [attendee-events.spec.js](../frontend/e2e/attendee-events.spec.js) | Existing specification retained |
| SCRUM-33 | [register.spec.js](../frontend/e2e/register.spec.js) | Existing specification retained |
| SCRUM-34 | [my-registrations.spec.js](../frontend/e2e/my-registrations.spec.js) | Existing specification retained |
| SCRUM-35 | [withdraw.spec.js](../frontend/e2e/withdraw.spec.js) | Existing specification retained |
| SCRUM-36 | [registration-records.spec.js](../frontend/e2e/registration-records.spec.js) | Existing specification retained |
| SCRUM-37 | [submit-event-change-request.spec.js](../frontend/e2e/submit-event-change-request.spec.js) | Browser scenarios added |
| SCRUM-38 | [review-event-change-request.spec.js](../frontend/e2e/review-event-change-request.spec.js) | Browser scenarios added |
| SCRUM-39 | [notification-system-legacy.spec.js](../frontend/e2e/notification-system-legacy.spec.js) | Legacy umbrella story: uses current SCRUM-261 behaviour |
| SCRUM-40 | [login.spec.js](../frontend/e2e/login.spec.js) | Existing specification retained |
| SCRUM-157 | [confirmed-event-info.spec.js](../frontend/e2e/confirmed-event-info.spec.js) | Existing specification retained |
| SCRUM-158 | [reassign-coordinator-legacy.spec.js](../frontend/e2e/reassign-coordinator-legacy.spec.js) | Uses latest Lead-managed workflow; historical ACs superseded |
| SCRUM-214 | [registration-period.spec.js](../frontend/e2e/registration-period.spec.js) | Existing specification retained |
| SCRUM-215 | [operational-safety-decision.spec.js](../frontend/e2e/operational-safety-decision.spec.js) | Browser scenarios added |
| SCRUM-216 | [operational-safety-arrangements.spec.js](../frontend/e2e/operational-safety-arrangements.spec.js) | Browser scenarios added |
| SCRUM-217 | [venue-setup-turnaround.spec.js](../frontend/e2e/venue-setup-turnaround.spec.js) | Browser scenarios added |
| SCRUM-218 | [coordinator-access.spec.js](../frontend/e2e/coordinator-access.spec.js) | Browser scenarios added |
| SCRUM-219 | [assign-event-coordinator.spec.js](../frontend/e2e/assign-event-coordinator.spec.js) | Browser scenarios added |
| SCRUM-220 | [manage-tentative-venue-holds.spec.js](../frontend/e2e/manage-tentative-venue-holds.spec.js) | Browser scenarios added |
| SCRUM-222 | [cancel-individual-venue-booking.spec.js](../frontend/e2e/cancel-individual-venue-booking.spec.js) | Browser scenarios added |
| SCRUM-223 | [modify-individual-venue-booking.spec.js](../frontend/e2e/modify-individual-venue-booking.spec.js) | Browser scenarios added |
| SCRUM-225 | [mark-venue-unavailable.spec.js](../frontend/e2e/mark-venue-unavailable.spec.js) | Browser scenarios added |
| SCRUM-226 | [reassign-event-coordinator.spec.js](../frontend/e2e/reassign-event-coordinator.spec.js) | Browser scenarios added |
| SCRUM-227 | [identify-affected-bookings.spec.js](../frontend/e2e/identify-affected-bookings.spec.js) | Browser scenarios added |
| SCRUM-261 | [notification-inbox.spec.js](../frontend/e2e/notification-inbox.spec.js) | Browser scenarios added |
| SCRUM-262 | [event-request-notifications.spec.js](../frontend/e2e/event-request-notifications.spec.js) | Existing specification retained |
| SCRUM-263 | [coordinator-assignment-notifications.spec.js](../frontend/e2e/coordinator-assignment-notifications.spec.js) | Browser scenarios added |
| SCRUM-264 | [venue-booking-notifications.spec.js](../frontend/e2e/venue-booking-notifications.spec.js) | Browser scenarios added |
| SCRUM-265 | [event-change-notifications.spec.js](../frontend/e2e/event-change-notifications.spec.js) | Browser scenarios added |
| SCRUM-266 | [equipment-request-notifications.spec.js](../frontend/e2e/equipment-request-notifications.spec.js) | Browser scenarios added |
| SCRUM-267 | [attendee-registration-notifications.spec.js](../frontend/e2e/attendee-registration-notifications.spec.js) | Browser scenarios added |
| SCRUM-268 | [notification-tentative-holds.spec.js](../frontend/e2e/notification-tentative-holds.spec.js) | Browser scenarios added |
| SCRUM-269 | [venue-unavailability-notifications.spec.js](../frontend/e2e/venue-unavailability-notifications.spec.js) | Browser scenarios added |
| SCRUM-270 | [safety-check-notifications.spec.js](../frontend/e2e/safety-check-notifications.spec.js) | Browser scenarios added |
| SCRUM-271 | [staff-assignment-notifications.spec.js](../frontend/e2e/staff-assignment-notifications.spec.js) | Browser scenarios added |
| SCRUM-272 | [automatic-staff-assignment.spec.js](../frontend/e2e/automatic-staff-assignment.spec.js) | Browser scenarios added |
| SCRUM-273 | [view-assigned-event-staff.spec.js](../frontend/e2e/view-assigned-event-staff.spec.js) | Browser scenarios added |
| SCRUM-275 | [coordinator-lead-notifications.spec.js](../frontend/e2e/coordinator-lead-notifications.spec.js) | Browser scenarios added |

## Coverage limits

Playwright currently collects **115 executions in 61 executable files**; the 62nd specification is the documented SCRUM-5 gap.

File existence and successful test collection do not establish complete AC coverage or a passing live run. The new files exercise real story-specific browser workflows, with API/database arrangements only for prerequisite or other-role steps. They are functional scenarios rather than a full security/concurrency audit.

- SCRUM-39: raw export supplies only the title; the existing SCRUM-261 contract is used for its persistence/isolation scenario.
- SCRUM-5: no ACs or signup implementation. Supply the intended registration/invitation requirements before an executable acceptance test can be written.
- SCRUM-7/8: normal submission, incomplete-form blocking and draft persistence are covered; exhaustive field validation and failure-message variants need additional browser cases.
- SCRUM-11/13/29/30: primary name-search, equipment-request, multi-venue-request and booking-decision workflows are covered. Advanced filter combinations, event-assignment denial and all validation/refusal branches need additional cases.
- SCRUM-9/20: the implemented review UI supports approve/reject; clarification requested in older workbook text has no decision button. Amendment is exercised through rejection/resubmission.
- SCRUM-22: visible lifecycle labels follow the implemented Submitted/Planning/Pending Safety Checks/Confirmed flow rather than the older Pending Approval/Approved terminology.
- SCRUM-10/23: registration-needs fields were removed from the product. Normal edits and critical-edit warning/confirmation/discard are covered.
- SCRUM-12/31: basic suitability and overlapping booking checks are covered. Setup/turnaround-introduced conflicts, half-open boundary adjacency and existing-booking conflict reporting need additional browser cases.
- SCRUM-15/16/17: primary availability/reservation/edit/cancel workflows are covered. Insufficient reservation quantity is also covered; concurrency and overlapping versus non-overlapping stock restoration need additional browser cases.
- SCRUM-24/25/26/27: primary create/search/detail/update/delete workflows are covered. Duplicate creation and upcoming-booking deletion refusal are also covered. Stale edits, update drafts, missing data and service outages need additional browser cases.
- SCRUM-28: Day/Week/Month toggles are covered; slot detail dialogs and all calendar state combinations need additional scenarios.
- SCRUM-35: exact event-start withdrawal refusal remains database-level coverage, as the retained spec documents.
- SCRUM-38/215/216/223: primary changes/review/safety arrangements and individual notes editing are covered; affected-arrangement rework and independent replacement-venue suitability checks need broader browser scenarios.
- SCRUM-218: coordinator access cases are retained; all-coordinator workload enumeration is limited by the current available workspace.
- SCRUM-261: generated notification popup, inbox and read behaviour are covered; exhaustive 14-day cutoffs and multi-page boundary datasets need additional cases.
- SCRUM-263/265/272: initial assignment/decision/valid staff membership are covered; previous-owner reassignment notice, all staff change recipients and statistical assignment randomness are not established by these scenarios.
- Timed-hold cases move only the test-owned hold expiry through service-key setup, then execute the actual expiry job; they do not sleep until a real-day deadline.
- SCRUM-33 follows the current on-screen success alert requirement rather than the older workbook email requirement. SCRUM-214 follows the current catalogue visibility policy: events are hidden before registration opens and after it closes.

## Verification

JavaScript syntax and Playwright collection are checked locally. Live-run results are recorded separately below; do not read unexecuted scenarios as Passed.


Verified on 5 November 2026:

- JavaScript syntax checks passed for all E2E source files.
- Manifest validation confirms **62 distinct story IDs mapped to 62 distinct specification files**.
- Playwright collected **115 tests in 61 executable files** without database fixture creation.
- **30 distinct representative browser cases passed across the sample runs and corrected-case rechecks**, using Microsoft Edge and the integration-test project. These include request submission/drafts/review, coordinator assignment/reassignment, equipment requests/reservations/refusal, venue catalogue/create/duplicate/review, safety decisions, notification inbox/Lead delivery, seven role workspaces and API role refusals. Test-owned fixture cleanup completed.
- Verification exposed label ambiguity, an outdated reassignment response URL and an incorrect safety post-navigation expectation; these test defects were corrected and their affected cases rechecked successfully.
- The **entire 115-test suite has not been executed**. Unexecuted cases and the documented AC gaps must not be reported as Passed or full coverage.

Local run evidence is in `outputs/compiled-e2e-sample-run.txt`, `outputs/compiled-e2e-workflow-run.txt` and `outputs/compiled-e2e-recheck-run.txt`. Earlier log failures show intermediate test defects; the rechecks above establish the corrected outcomes. Use the normal HTML reporter for a fresh complete run.
