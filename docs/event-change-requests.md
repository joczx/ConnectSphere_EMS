# Event change requests

Event Organisers use **Request Event Changes** to propose changes to an event
they originally submitted. They may propose only its date/time, expected
attendance, venue and accessibility requirements, or equipment requirements.
The event row and its lifecycle status are not changed when the request is
submitted.

Each request has its own `pending_review`, `approved`, or `rejected` status.
This is separate from the event's operational status and from the Safety
Officer workflow. This story implements submission as `pending_review`; the
coordinator decision flow can use the other two values in its own story.

For a confirmed event, submission first returns the critical fields so the UI
can show its warning. Confirming writes the pending request and a linked
`Critical Edit` Activity History entry atomically. Cancelling the warning makes
no API call and restores the form from the current event.

## API

- `GET /api/event-change-requests/eligible-events`
- `GET /api/events/<event_id>/change-requests`
- `POST /api/events/<event_id>/change-requests`

Apply `supabase/037_event_change_requests.sql` before deploying the backend.
