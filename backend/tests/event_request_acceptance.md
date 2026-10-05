# Create and Submit Event Request acceptance checks

Run automated validation and HTTP/service tests from `backend`:

```powershell
python -m pytest tests/test_event_request_schema.py tests/test_event_request_submission.py -v -p no:cacheprovider
```

The HTTP tests replace Supabase at the database boundary. They verify the
actual route and service together, including validation before writes,
server-controlled status/timestamp, returning the database-generated ID,
success messages, failure messages, malformed bodies and incomplete drafts.
They do not prove database ID uniqueness or browser behaviour.

## Browser and deployed database checks

Use an Event Organiser account and disposable test requests. These checks
create real records; run in the team's test environment.

| AC | Steps | Expected result |
| --- | --- | --- |
| 1: Enter details | Open `/event-requests/new`; fill every field, including equipment and registration needs. | All details can be entered. Facilities/equipment may explicitly be answered as none. |
| 2: Submit | Choose Review before submitting, then Confirm and submit. | The request is created and its details page opens. |
| 3: Mandatory fields | Leave each required field blank in turn and attempt submission. | Submission is blocked; no submitted request is created. |
| 4: Missing-information message | Repeat AC 3; also enter only spaces for event name. | Browser validation or the API field error explains what is required. |
| 5: Invalid details | Try zero/fractional attendance, past start time, end before start and equipment quantity zero. | Validation blocks creation and reports the error; entered values remain available through Back to edit. |
| 6: Unique ID | Submit two separate completed requests. Reload both details pages and inspect their stored rows. | Each has a different non-null request ID. Verify `event_request_id` has a primary-key/unique constraint and a database-generated default/identity in Supabase. |
| 7: Submission time | Submit a request and compare the stored `submitted_at` with the submission time. | A timezone-aware timestamp is stored and displayed in the browser's local time. |
| 8: Submitted status | Inspect a newly submitted request and its stored row. | UI shows Submitted; database stores `submitted`. |
| 9: Review | Choose Review before submitting. Check every summary value, choose Back to edit, change a field and review again. | Summary contains the entered details, including equipment notes; edits are preserved and reflected. No write occurs until confirmation. |
| 10: Confirmation | Complete a successful submission. | The details page displays Event request submitted successfully, ID, timestamp and status. |
| 11: Creation failure | In the test environment, simulate a failed POST using browser request interception or make the API unavailable before confirming. | An error is displayed, no success message appears, and the summary and form values remain available for retry/edit. |

Also check that double-clicking Confirm and submit sends one in-flight request,
and that saving an incomplete draft still works without submitting it.

## Suggested refinements for product agreement

- Enumerate mandatory fields and define explicit none answers for facilities,
  equipment and registration, including accessibility defaults.
- Define invalid details: positive whole-number attendance/equipment quantities,
  future start, end after start, and allowed layouts/facilities.
- Require Back to edit from the review summary without losing entered values.
- Require failed submissions to preserve entered details and permit retry.
- Define duplicate prevention across network retries separately. Disabling the
  button prevents concurrent clicks, but server idempotency is not implemented.
- Track authenticated identity and request ownership under the authentication
  story; event request endpoints still trust the client organiser ID.
