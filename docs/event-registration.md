# Event registration periods

Apply `supabase/046_event_registration.sql` after migrations through 045, followed
by `supabase/047_attendee_registration_access.sql`, then
restart the backend and rebuild the frontend. This migration targets the deployed
integer `events.event_id` schema, as do the venue and change-request migrations.

The assigned Event Organiser sets opening and closing times and the waiting-list
preference in the Registration period section of their event. Inputs explicitly
use Singapore time; storage uses timezone-aware timestamps. Closing must be strictly
after opening. Settings may change before or during the existing period, while the
event is planning, pending safety checks or confirmed, and before the event ends.
Once the existing period has closed it cannot be reopened through this feature.
Changes apply immediately, including moving the opening time back into the future.
Existing registrations remain valid when settings change.

Only users with the Attendee role can open the Event Registration home tile or
page. Both the listing and submission database functions also enforce this role,
so direct API calls by organisers, coordinators and other staff return 403.
Users holding multiple roles can access it when one is Attendee. Only confirmed
events accept registration, and only within `[opening, closing)`. The attendee
projection exposes event name, description, schedule, period and capacity without
internal planning details or staff identities. It refreshes every 30 seconds and
on focus, with a manual refresh action. The database checks the current period on
every submission, even if the page is stale.

Capacity uses the event's existing `capacity_needed`. At capacity, new attendees
join the waiting list only when enabled. Event row locks serialize submissions
and period updates; duplicate registrations return the existing record. Disabling
the waiting list preserves existing waiting entries. Promotion, cancellation and
waiting-list administration are outside this story.

API (shared authenticated request helper):

- `PATCH /api/events/<id>/registration-period`: all three fields,
  `registration_opens_at`, `registration_closes_at`, `waiting_list_enabled`.
- `GET /api/registration-events`: attendee-safe information and own registration.
- `POST /api/events/<id>/registrations`: register the authenticated user; no client identity accepted.

The migration preserves the latest lifecycle guard from 038, excluding registration
settings from arrangement comparisons. A separate trigger restricts those fields
to the assigned organiser. Direct attendee writes to registration rows are revoked;
the controlled function enforces period, capacity, identity and event state.
