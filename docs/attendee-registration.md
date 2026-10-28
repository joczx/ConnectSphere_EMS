# Attendee registration

Apply Supabase migrations 046 through 050 in order. Attendees register on
`/event-registration`, providing full name, contact email and phone number.
The API and database reject missing or malformed details. The database serialises
registrations per event, rechecks the registration window, and prevents confirmed
places exceeding capacity. A full event accepts waiting-list entries only when
the organiser enabled that option; these are explicitly not confirmed places.

Registration times must satisfy `opening < closing < event start`, with equality
refused. The form checks against the displayed event start, and the database RPC
checks the current stored event under a lock. A table constraint also prevents
direct writes or rescheduling the event to at/before registration closing.
An event needs a valid start time before registration can be configured.

Migration 050 validates existing records. Correct any periods that violate the
ordering before applying it; the migration does not silently change existing times.

Registration details are visible only to the attendee through the existing RLS
policy. Existing registrations keep null personal details; no details are invented.
The previous one-argument registration RPC is removed to prevent validation bypass.

## Email delivery

Registration atomically writes a confirmation to `registration_email_outbox`.
Duplicates return the existing registration without creating another notification.
Waiting-list notifications use different wording from confirmed registration.

Configure the backend variables shown in `backend/.env.example`. Keep the service
role key server-side. Use an SMTP server supporting STARTTLS on port 587 (or set
`SMTP_PORT`). From `backend`, schedule `python send_registration_emails.py` every
minute, with only one sender running at a time. Each invocation sends up to 100
pending messages. Monitor nonzero exit codes and rerun after failures; unsent rows
remain pending. The UI reports that email is queued, rather than claiming delivery.

Delivery is at least once: a crash after SMTP acceptance but before marking a row
sent can produce a duplicate email on retry. A stable Message-ID assists tracing.
SMTP acceptance does not establish inbox delivery. Real delivery requires configured
credentials and a verified sender; automated tests use a mocked SMTP connection.

## Validation

From `backend`:

```powershell
python -m coverage run --branch --source=app.schemas.registration,app.services.registration_service,app.services.registration_email_service -m pytest tests/test_registration.py tests/test_registration_email.py -p no:cacheprovider
python -m coverage report --fail-under=100 -m
```

From the repository root: `node --test frontend/tests/registration-db.mjs`.
The database test uses the existing local PGlite test dependency and applies the
actual migrations to an isolated database; no production email is sent.

## Withdrawal

Attendees use Withdraw registration from Event registration, My registrations,
or their dashboard, backed by
`POST /api/events/<id>/registrations/withdraw`. The database derives identity from
the session, locks the event against concurrent registrations, then reads the
clock. Withdrawal is allowed strictly before event start, including after the
registration window closes. At or after start (or without a recorded start),
the request is refused without changing the registration.

Withdrawal preserves the row with status `withdrawn` and a `withdrawn_at` timestamp.
Repeated withdrawals before start return the same record. Available capacity is
computed from confirmed registrations; withdrawing a waiting-list entry does not
release a confirmed place. Existing waiting-list entries are not automatically
promoted by this story. The updated capacity and status appear in attendee event
information and immediately after a successful withdrawal.

Attendees may register again while registration is open, subject to capacity.
Re-registration resets the withdrawal timestamp and queues a fresh confirmation.
Withdrawal removes pending confirmation emails; a message already accepted by SMTP
or currently being sent cannot be recalled.

## My registrations

Apply `051_my_registrations.sql` after the withdrawal migration. Attendees can
open `/my-registrations` from the home launcher or Event registration page.
`GET /api/my-registrations` calls `my_event_registrations()` with the verified
session token; it accepts no attendee identity. The database returns only that
attendee's registration records, including past/cancelled events and withdrawals.

The view displays Confirmed, Waitlisted or Withdrawn, the event name, start/end
times in SGT and venue names. Approved booking venues take precedence over an
event's linked venue; unapproved bookings are excluded. Missing venues display
"Venue not assigned yet". An empty list displays "You have no registration records."
It refreshes on focus, every 30 seconds, and using Refresh.

## Managed event registration roster

Apply `052_event_registration_roster.sql` after the withdrawal migration.
Assigned Event Organisers and Event Coordinators open Events, select their event,
and view Attendee registrations. Names, contact email/phone, registration dates
and Confirmed/Waitlisted/Withdrawn statuses appear in the roster. Older records
without personal details show "Not provided". Counts distinguish confirmed places
from waiting-list entries and withdrawals. The roster refreshes every 30 seconds,
on focus, and through Refresh registrations; errors never appear as zero counts.

`GET /api/events/<id>/registrations` passes only the verified token and event ID
to `event_registration_roster()`. The database requires both the appropriate role
and its matching event assignment. Unassigned managers receive 404 without attendee
data; other roles receive 403. The read does not grant broader direct table access.
