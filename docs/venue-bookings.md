# Venue booking submission

Apply `supabase/017_venue_bookings.sql` with a trusted database administrator after the venue catalogue and users/roles/user_roles tables exist. Assign existing accounts the `Event Coordinator` or `Venue Staff` role through trusted admin tooling (underscore spellings are also supported).

The migration revokes client writes to roles and user_roles so clients cannot grant themselves booking privileges. Coordinate this with any existing role-management work. It creates a booking request table, read policies and authenticated submission/list RPCs. Submitter identity comes from `auth.uid()`, never the request body. Coordinators see their own requests; Venue Staff see all requests. No venue-specific staff assignment currently exists.

Open **Venue Bookings** from Home, or **Request booking** on a venue search result. Coordinators select a venue and enter an event name, future start/end, positive attendance and requirements (enter None if there are no special requirements). Times are explicitly Singapore time. Success shows the saved reference and adds the request to the list. Venue Staff use the same tile to read the review queue, including every submitted detail.

API: `POST /api/venue-bookings` accepts `venue_id` (UUID), `event_name`, timezone-aware ISO `starts_at`/`ends_at`, integer `attendance`, and `venue_requirements`. `GET /api/venue-bookings` returns the authorized queue and role capabilities. Both require bearer authentication.

This story submits requests for review; it does not approve bookings or reserve capacity. Event information is captured on the request rather than linked to the inconsistent legacy events schemas. Requests do not change venue search availability or suitability.

Validation: `python -m pytest tests/test_venue_bookings.py` from backend; `npm run build` from frontend. Python tests mock Supabase; after applying the migration, verify with separate coordinator, staff and unrelated accounts that a persisted submission appears for staff, that unrelated users cannot submit/read it, and that direct table writes are denied.
