# Attendee registration

Apply Supabase migrations 046, 047 and 048 in order. Attendees register on
`/event-registration`, providing full name, contact email and phone number.
The API and database reject missing or malformed details. The database serialises
registrations per event, rechecks the registration window, and prevents confirmed
places exceeding capacity. A full event accepts waiting-list entries only when
the organiser enabled that option; these are explicitly not confirmed places.

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
