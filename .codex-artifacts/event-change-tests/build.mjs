import fs from "node:fs/promises";
import { Workbook, SpreadsheetFile } from "file:///C:/Users/josch/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const outputPath = "C:/Users/josch/OneDrive/Documents/GitHub/ConnectSphere_EMS/outputs/event-change-request-test-cases-20261103/Event Change Request Unit Test Cases.xlsx";
const previewPath = "C:/Users/josch/OneDrive/Documents/GitHub/ConnectSphere_EMS/.codex-artifacts/event-change-tests/preview.png";
const executedOn = new Date("2026-11-03T00:00:00+08:00");

const submitStory = {
  title: "Submit Event Change Request",
  description: "As an Event Organiser, I want to submit a change request for an already-submitted event, so that I can allow the Event Coordinator to review and process the request.",
  ac: [
    "AC1: The Event Organiser can select an existing submitted event and enter proposed updates to permitted fields: date, time, expected attendance, venue requirements, or equipment requirements.",
    "AC2: A required text field is provided for the reason for the change request.",
    "AC3: Successful submission shows a confirmation message and changes the request status to Pending Review.",
    "AC4: Submission is prevented and an error is shown when no change is made.",
    "AC5: A blank reason prevents submission and shows: Please provide a reason for this change request.",
    "AC6: A warning modal appears when critical fields that may affect existing arrangements are changed on a Confirmed event.",
    "AC7: The user must review or confirm the impact of critical changes before they are saved.",
    "AC8: Confirmed critical changes are saved and a Critical Edit entry is logged in Activity History.",
    "AC9: Cancelling the warning discards pending edits and keeps the current Confirmed status.",
  ].join("\n"),
};

const reviewStory = {
  title: "Review Event Change Request",
  description: "As an Event Coordinator, I want to review and process requests that change important information for an already-submitted event so that I can consider whether I can adjust preparations to handle changes in date, time, or any other requirements.",
  ac: [
    "AC1: The Event Coordinator can view change requests for events they are responsible for.",
    "AC2: Changes to important information such as date, time, expected attendance, venue requirements, or equipment requirements require approval.",
    "AC3: Non-important changes such as name or description do not require approval.",
    "AC4: The Event Coordinator is clearly shown which important information is being changed.",
    "AC5: The Event Coordinator can accept or reject a request and provide a reason when necessary.",
    "AC6: When there are no change requests, the Event Coordinator sees a No change requests message.",
    "AC7: Accepting a request updates the event information.",
  ].join("\n"),
};

const schemaFile = "backend/tests/test_event_change_request_schema.py";
const requestFile = "backend/tests/test_event_change_requests.py";

const submitTests = [
  ["AC1", "Allow only the event fields supported by the story", "Run the schema unit test through pytest.", "Permitted-field list containing event name and description but not status.", "All supported story fields are permitted and system-controlled status is excluded.", "Happy Path", schemaFile, "test_only_story_fields_are_permitted"],
  ["AC2, AC5", "Reject a missing change reason", "Run the parameterised schema unit test through pytest.", "reason=None", "Validation returns the exact required-reason inline message.", "Negative Path", schemaFile, "test_reason_is_required_with_the_exact_inline_message[None]"],
  ["AC2, AC5", "Reject an empty change reason", "Run the parameterised schema unit test through pytest.", "reason=empty string", "Validation returns the exact required-reason inline message.", "Negative Path", schemaFile, "test_reason_is_required_with_the_exact_inline_message[empty]"],
  ["AC2, AC5", "Reject a whitespace-only change reason", "Run the parameterised schema unit test through pytest.", "reason=three spaces", "Validation returns the exact required-reason inline message.", "Negative Path", schemaFile, "test_reason_is_required_with_the_exact_inline_message[spaces]"],
  ["AC1", "Reject a proposed change to an unpermitted field", "Run the schema unit test through pytest.", "proposed_values contains purpose.", "Validation reports proposed_values as invalid.", "Negative Path", schemaFile, "test_unpermitted_change_is_rejected"],
  ["AC1", "Normalise valid proposed values using the existing event rules", "Run the schema unit test through pytest.", "capacity_needed='200' and a timezone-aware future start.", "Capacity is converted to 200 and the timestamp remains timezone-aware.", "Happy Path", schemaFile, "test_values_are_cleaned_by_existing_event_rules"],
  ["AC4", "Reject a submission body that is not an object", "Run the schema unit test through pytest.", "Request body=None.", "Validation returns the expected JSON-object error.", "Negative Path", schemaFile, "test_non_object_submission_is_rejected"],
  ["AC1", "Reject an unknown top-level submission field", "Run the schema unit test through pytest.", "Valid body plus extra=true.", "Validation identifies the unrecognised field.", "Negative Path", schemaFile, "test_unknown_body_field_is_rejected"],
  ["AC2", "Reject a change reason above the maximum length", "Run the schema unit test through pytest.", "2,001-character reason.", "Validation reports that the reason must be 2,000 characters or fewer.", "Boundary / Edge Case", schemaFile, "test_overlong_reason_is_rejected"],
  ["AC1, AC4", "Reject null proposed changes", "Run the parameterised schema unit test through pytest.", "proposed_values=None.", "Validation requires proposed changes to be a JSON object.", "Negative Path", schemaFile, "test_proposed_values_must_be_an_object[None]"],
  ["AC1, AC4", "Reject proposed changes supplied as text", "Run the parameterised schema unit test through pytest.", "proposed_values='capacity_needed=200'.", "Validation requires proposed changes to be a JSON object.", "Negative Path", schemaFile, "test_proposed_values_must_be_an_object[text]"],
  ["AC1, AC4", "Return a field error for an invalid permitted value", "Run the schema unit test through pytest.", "capacity_needed='many'.", "Validation reports that expected attendance must be a whole number.", "Negative Path", schemaFile, "test_invalid_permitted_value_returns_field_error"],
  ["AC7, AC8", "Reject a missing event-version timestamp", "Run the parameterised schema unit test through pytest.", "expected_event_updated_at=None.", "Validation instructs the user to reload the event.", "Negative Path", schemaFile, "test_event_version_timestamp_must_be_an_aware_iso_datetime[None]"],
  ["AC7, AC8", "Reject an empty event-version timestamp", "Run the parameterised schema unit test through pytest.", "expected_event_updated_at=empty string.", "Validation instructs the user to reload the event.", "Negative Path", schemaFile, "test_event_version_timestamp_must_be_an_aware_iso_datetime[empty]"],
  ["AC7, AC8", "Reject a malformed event-version timestamp", "Run the parameterised schema unit test through pytest.", "expected_event_updated_at='not-a-date'.", "Validation instructs the user to reload the event.", "Negative Path", schemaFile, "test_event_version_timestamp_must_be_an_aware_iso_datetime[not-a-date]"],
  ["AC7, AC8", "Reject a timezone-free event-version timestamp", "Run the parameterised schema unit test through pytest.", "expected_event_updated_at='2030-01-01T12:00:00'.", "Validation instructs the user to reload the event.", "Boundary / Edge Case", schemaFile, "test_event_version_timestamp_must_be_an_aware_iso_datetime[timezone-free]"],
  ["AC6, AC7", "Require the critical-change confirmation flag to be Boolean", "Run the schema unit test through pytest.", "confirm_critical='yes'.", "Validation reports that confirmation must be true or false.", "Negative Path", schemaFile, "test_confirmation_flag_must_be_boolean"],
  ["AC2, AC7", "Normalise a valid reason and critical confirmation", "Run the schema unit test through pytest.", "Reason with surrounding spaces and confirm_critical=true.", "The reason is trimmed, version retained, and confirmation remains true.", "Happy Path", schemaFile, "test_valid_confirmation_and_whitespace_are_normalised"],
  ["AC3, AC8", "Submit through the atomic database workflow", "Run the service unit test through pytest with the database call mocked.", "Event ID 4, valid change body, confirm_critical omitted.", "The submit RPC receives event ID 4 and confirm_critical=false; Pending Review result is returned.", "Happy Path", requestFile, "test_submission_calls_the_atomic_database_function"],
  ["AC6, AC7", "Preserve critical-field details for the warning modal", "Run the service unit test through pytest with a mocked conflict response.", "HTTP 409 with critical_fields=['Expected attendance'].", "The application error retains the 409 status and critical-field list.", "Boundary / Edge Case", requestFile, "test_database_critical_warning_is_preserved_for_the_modal"],
  ["AC5", "Stop an invalid submission before any database call", "Run the service unit test through pytest.", "Valid body with a blank reason.", "The exact reason error is returned and the database is not called.", "Negative Path", requestFile, "test_invalid_body_never_calls_the_database"],
  ["AC1", "Require authentication to submit a change request", "POST the submission route through the Flask test client without a token.", "No Authorization header.", "HTTP 401 is returned with no-store caching.", "Negative Path", requestFile, "test_submission_endpoint_requires_authentication"],
  ["AC1, AC8", "Prevent the organiser from bypassing the request workflow", "PATCH the event route through the Flask test client as its organiser.", "Direct capacity edit to a planning event.", "HTTP 403 directs the organiser to use a change request.", "Negative Path", requestFile, "test_organiser_cannot_bypass_requests_with_direct_event_edit"],
  ["AC4, AC6, AC7", "Serialise all optional change-request error details", "Run the error-object unit test through pytest.", "Error with field errors, critical fields, and stale=true; then a plain error.", "Optional details appear when supplied and are omitted from a plain error.", "Boundary / Edge Case", requestFile, "test_change_request_error_serialises_every_optional_detail"],
  ["AC1, AC3", "List eligible events and the organiser's change-request history", "Run service methods with mocked RPC responses.", "Eligible event, organiser history, and event-specific history responses.", "Each method returns the expected list and sends the correct event filter.", "Happy Path", requestFile, "test_submission_service_lists_eligible_events_and_history"],
  ["AC1", "Default missing or malformed list responses to empty lists", "Run service list methods with empty and non-object RPC responses.", "Three empty objects followed by a list response.", "All list methods return empty lists without crashing.", "Boundary / Edge Case", requestFile, "test_submission_service_list_defaults_and_non_object_rpc_result"],
  ["AC7, AC8", "Preserve validation details and stale state from the database", "Run the submission database wrapper with a mocked error result.", "Error='Event changed', event reload field error, stale=true.", "The application error preserves the details and stale marker.", "Boundary / Edge Case", requestFile, "test_submission_database_error_preserves_errors_and_stale_marker"],
  ["AC1", "Return eligible events from the submission GET route", "Call the eligible-events route through the Flask test client.", "Authenticated user and one eligible event.", "HTTP 200 returns the events and no-store caching.", "Happy Path", requestFile, "test_submission_get_routes_return_service_results[eligible-events]"],
  ["AC3", "Return the organiser's change-request history", "Call the mine route through the Flask test client.", "Authenticated organiser and one prior change request.", "HTTP 200 returns change_requests and no-store caching.", "Happy Path", requestFile, "test_submission_get_routes_return_service_results[mine]"],
  ["AC1, AC3", "Return change requests for the selected event", "Call the event change-request route through the Flask test client.", "Authenticated organiser and event ID 4.", "HTTP 200 returns the event's change requests and no-store caching.", "Happy Path", requestFile, "test_submission_get_routes_return_service_results[event]"],
  ["AC3", "Return the created change request and confirmation", "POST a valid request through the Flask test client with the service mocked.", "Valid body and saved request ID 7.", "HTTP 201 returns the service confirmation and saved request.", "Happy Path", requestFile, "test_submission_post_route_returns_created_result"],
  ["AC1", "Translate authentication failure on a submission route", "Call the eligible-events route with the authentication lookup mocked to fail.", "StoreError status 401.", "HTTP 401 returns Please sign in again.", "Negative Path", requestFile, "test_submission_routes_translate_store_errors[401]"],
  ["AC3, AC4", "Translate service outage on a submission route", "Call the eligible-events route with the backing service mocked to fail.", "StoreError status 503.", "HTTP 503 reports that event change requests are temporarily unavailable.", "Negative Path", requestFile, "test_submission_routes_translate_store_errors[503]"],
  ["AC4, AC6, AC7", "Return structured submission application errors", "POST a valid request while the service raises a stale conflict.", "EventChangeRequestError status 409 and stale=true.", "HTTP 409 preserves the error and stale marker.", "Negative Path", requestFile, "test_submission_route_serialises_application_error"],
];

const reviewTests = [
  ["AC5, AC7", "Send an approval decision through the atomic review workflow", "Run the review service unit test with the database call mocked.", "Request ID 7, decision=approve, blank reason.", "The review RPC receives approve with a null reason and returns the updated-event message.", "Happy Path", requestFile, "test_review_service_calls_atomic_decision_function"],
  ["AC5", "Reject a missing review decision body", "Run the parameterised review-schema unit test through pytest.", "Review payload=None.", "Validation reports: Provide a review decision.", "Negative Path", requestFile, "test_review_decision_rejects_each_invalid_shape[None]"],
  ["AC5", "Reject an unsupported review decision", "Run the parameterised review-schema unit test through pytest.", "decision='wait'.", "Validation reports: Choose Approve or Reject.", "Negative Path", requestFile, "test_review_decision_rejects_each_invalid_shape[decision]"],
  ["AC5", "Reject a non-text decision reason", "Run the parameterised review-schema unit test through pytest.", "decision=approve, reason=4.", "Validation reports that the decision reason must be text.", "Negative Path", requestFile, "test_review_decision_rejects_each_invalid_shape[reason-type]"],
  ["AC5", "Reject an overlong decision reason", "Run the parameterised review-schema unit test through pytest.", "decision=approve, 2,001-character reason.", "Validation reports that the reason must be 2,000 characters or fewer.", "Boundary / Edge Case", requestFile, "test_review_decision_rejects_each_invalid_shape[reason-length]"],
  ["AC5", "Require a reason when rejecting a change request", "Run the parameterised review-schema unit test through pytest.", "decision=reject, whitespace-only reason.", "Validation returns the required rejection-reason message.", "Negative Path", requestFile, "test_review_decision_rejects_each_invalid_shape[reject-no-reason]"],
  ["AC5", "Accept approval without a reason and rejection with a reason", "Run the review-schema unit test through pytest.", "Approval without reason; rejection with spaced reason text.", "Approval produces a null reason and rejection produces a trimmed reason.", "Happy Path", requestFile, "test_review_decision_accepts_optional_approval_and_reasoned_rejection"],
  ["AC1, AC4, AC6", "List the coordinator queue and load request details", "Run review service list and detail methods with mocked RPC responses.", "Pending Review filter, empty unfiltered list, and request ID 7 detail.", "The queue uses the requested filter, empty lists remain empty, and detail ID 7 is returned.", "Happy Path", requestFile, "test_review_service_lists_filters_and_loads_details"],
  ["AC1, AC5", "Reject invalid queue filters and decisions before database access", "Run review service methods with the database call mocked.", "status=unknown; rejection with blank reason.", "Both validations fail and no database request is made.", "Negative Path", requestFile, "test_review_service_rejects_invalid_filter_and_decision_before_database"],
  ["AC4, AC5", "Preserve review error details and stale state", "Load a review detail while the mocked database returns an error.", "Stale request, event reload field error, stale=true.", "The application error preserves the field error and stale marker.", "Boundary / Edge Case", requestFile, "test_review_database_error_preserves_details_and_default_status"],
  ["AC1, AC4, AC5, AC7", "Return the review queue, detail, and decision results", "Call all three review routes through the Flask test client with services mocked.", "Pending Review queue, request ID 7 detail, approval decision.", "The queue, request detail, and approval response are returned with no-store caching.", "Happy Path", requestFile, "test_review_routes_return_queue_detail_and_decision"],
  ["AC1", "Translate authentication failure on the review queue", "Call the review queue with authentication mocked to fail.", "StoreError status 401.", "HTTP 401 returns Please sign in again.", "Negative Path", requestFile, "test_review_routes_translate_store_errors[401]"],
  ["AC1, AC6", "Translate service outage on the review queue", "Call the review queue with the backing service mocked to fail.", "StoreError status 503.", "HTTP 503 reports that event change requests are temporarily unavailable.", "Negative Path", requestFile, "test_review_routes_translate_store_errors[503]"],
  ["AC5", "Return structured review application errors", "Call the review queue while the service raises a decision error.", "EventChangeRequestError status 409 with decision='Already decided'.", "HTTP 409 preserves the application error and decision detail.", "Negative Path", requestFile, "test_review_route_serialises_application_error"],
];

if (submitTests.length !== 34 || reviewTests.length !== 14) {
  throw new Error(`Unexpected test counts: submit=${submitTests.length}, review=${reviewTests.length}`);
}

const headers = [
  "User Story", "Description", "Acceptance Criteria", "Test Case ID", "Corresponding AC",
  "Test Scenario", "Test Steps", "Test Data", "Expected Result", "Actual Result", "Path",
  "Status", "Remarks", "Created By", "Date of Creation", "Executed By", "Date of Execution",
];
const explanations = [
  "User story title", "User story description", "Specific acceptance criteria", "Unique ID",
  "Acceptance criterion covered", "Summary of test case", "Procedure used to execute the test",
  "Inputs and mocked data", "Expected result", "Result from the test run",
  "Happy / Negative / Boundary or Edge Case", "Pass / Fail / Not Executed / Blocked",
  "Backend source test", "Author of test case", "Date test case created", "Person who ran test case",
  "Date test case was run",
];

function buildRows(story, tests, prefix) {
  return tests.map((test, index) => {
    const [ac, scenario, steps, data, expected, path, file, functionName] = test;
    return [
      index === 0 ? story.title : "",
      index === 0 ? story.description : "",
      index === 0 ? story.ac : "",
      `TC-${prefix}-${String(index + 1).padStart(3, "0")}`,
      ac,
      scenario,
      steps,
      data,
      expected,
      "Passed - pytest (automated)",
      path,
      "Pass",
      `${file}::${functionName}`,
      "",
      "",
      "Codex",
      executedOn,
    ];
  });
}

const submitRows = buildRows(submitStory, submitTests, "SECR");
const reviewRows = buildRows(reviewStory, reviewTests, "RECR");
const rows = [headers, explanations, ...submitRows, ...reviewRows];

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Event Change Requests");
sheet.showGridLines = true;
sheet.getRange(`A1:Q${rows.length}`).values = rows;

const submitStart = 3;
const submitEnd = submitStart + submitRows.length - 1;
const reviewStart = submitEnd + 1;
const reviewEnd = reviewStart + reviewRows.length - 1;
for (const col of ["A", "B", "C"]) {
  sheet.mergeCells(`${col}${submitStart}:${col}${submitEnd}`);
  sheet.mergeCells(`${col}${reviewStart}:${col}${reviewEnd}`);
}

const used = sheet.getRange(`A1:Q${reviewEnd}`);
used.format.font = { name: "Arial", size: 10 };
used.format.wrapText = true;
used.format.verticalAlignment = "top";
used.format.borders = { preset: "all", style: "thin", color: "#BFBFBF" };

sheet.getRange("A1:Q1").format.font = { name: "Arial", size: 10, bold: true };
sheet.getRange("A2:Q2").format.font = { name: "Arial", size: 9, italic: true };
sheet.getRange("A1:Q2").format.verticalAlignment = "center";
sheet.getRange("A1:Q2").format.rowHeight = 30;
sheet.getRange(`A${submitStart}:C${reviewEnd}`).format.font = { name: "Arial", size: 10 };
sheet.getRange(`D${submitStart}:Q${reviewEnd}`).format.rowHeight = 48;
sheet.getRange(`Q${submitStart}:Q${reviewEnd}`).format.numberFormat = "yyyy-mm-dd";

const widths = {
  A: 30, B: 45, C: 62, D: 16, E: 18, F: 38, G: 38, H: 36, I: 40,
  J: 23, K: 22, L: 12, M: 58, N: 16, O: 17, P: 16, Q: 17,
};
for (const [col, width] of Object.entries(widths)) {
  sheet.getRange(`${col}1:${col}${reviewEnd}`).format.columnWidth = width;
}

sheet.freezePanes.freezeRows(2);
sheet.freezePanes.freezeColumns(3);

workbook.recalculate();

const check = await workbook.inspect({
  kind: "table",
  range: "Event Change Requests!A1:I8",
  include: "values,formulas",
  tableMaxRows: 8,
  tableMaxCols: 9,
});
console.log(check.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const preview = await workbook.render({
  sheetName: "Event Change Requests",
  range: "A1:I12",
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

await fs.mkdir(outputPath.slice(0, outputPath.lastIndexOf("/")), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`SAVED ${outputPath}`);
