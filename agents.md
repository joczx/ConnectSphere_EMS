# ConnectSphere EMS — Implemented User Stories

A map from each completed user story to the files that implement it, so you can
find the relevant code without reading the whole backend.

Most implemented user-story work is currently in the backend. The frontend now
has a small authenticated home-page launcher, documented below, but its app tiles
are not yet wired to feature pages.

---

## Shared foundation

These are used by every story below.

- **[backend/app/__init__.py](backend/app/__init__.py)** — Flask app factory. Loads `backend/.env`, enables CORS for the React dev server, and registers the route blueprints.
- **[backend/app/services/supabase_client.py](backend/app/services/supabase_client.py)** — Builds the shared Supabase client once from `SUPABASE_URL` and `SUPABASE_ANON_KEY`, and fails loudly if either is missing.
- **[backend/app/services/db.py](backend/app/services/db.py)** — Runs Supabase calls and hands database errors to each service's own translator, so error wording stays close to the feature it belongs to.
- **[backend/app/routes/event_requests.py](backend/app/routes/event_requests.py)** — Every `/api/event-requests` endpoint. Kept thin: parses the body, calls a service, shapes the response.
- **[backend/app/schemas/event_request.py](backend/app/schemas/event_request.py)** — All validation for event request fields. Imports no Flask or Supabase, so the rules can be unit tested without a database.
- **[backend/app/services/event_request_service.py](backend/app/services/event_request_service.py)** — The primitives every story builds on: create, fetch, edit, mark submitted, list.

---

## 1. Create and Submit Event Request

> As the Event Organiser, I want to create and submit an event request so that the Event Coordinator can process my event request.

**Endpoints:** `POST /api/event-requests`, `GET /api/event-requests/<id>`

- **[backend/app/schemas/event_request.py](backend/app/schemas/event_request.py)** — `parse_payload()` checks every field's type and range; `find_missing()` enforces the mandatory fields before submission; `check_timing()` rejects an event that ends before it starts or starts in the past.
- **[backend/app/services/event_request_service.py](backend/app/services/event_request_service.py)** — `create_event_request()` writes the row, sets the status, and stamps `submitted_at`.
- **[backend/tests/test_event_request_schema.py](backend/tests/test_event_request_schema.py)** — Unit tests, each labelled with the acceptance criterion it covers.
- **[frontend/src/pages/EventRequest.jsx](frontend/src/pages/EventRequest.jsx)** — Event request form. Its room-layout and required-facility choices match the Venue Search filters; equipment such as microphones is entered separately under equipment requirements.
- **[supabase/002_add_event_request_equipment_and_registration.sql](supabase/002_add_event_request_equipment_and_registration.sql)** — Adds `equipment_requirements` (JSON array) and `registration_needs` (text), which the original table had no columns for.

**Note:** the acceptance criteria say the initial status should be `Pending`, but no such value exists in the `request_status` enum. The code uses `submitted`, matching the Event Status Management story's `Draft → Submitted` transition.

---

## 2. Draft Event Requests

> As an Event Organiser, I want to create and save an incomplete event request so that I can submit an event for processing.

**Endpoints:** `POST /api/event-requests` with `"save_as_draft": true`, `GET /api/event-requests?event_organiser_id=&status=draft`, `PATCH /api/event-requests/<id>`

- **[backend/app/schemas/event_request.py](backend/app/schemas/event_request.py)** — The split between `parse_payload()` (always enforced) and `find_missing()` (only at submission) is what lets a draft be incomplete but never malformed. `_is_cleared()` treats `null` as "empty this field" so an Organiser can undo an earlier entry.
- **[backend/app/services/event_request_service.py](backend/app/services/event_request_service.py)** — `apply_edit()` writes a partial change and returns what actually differed; `list_event_requests()` filters by organiser and status so drafts stay distinguishable from submitted requests.
- **[backend/app/services/event_request_workflow.py](backend/app/services/event_request_workflow.py)** — Decides whether an edit is allowed at all based on the request's current state.
- **[backend/tests/test_event_request_schema.py](backend/tests/test_event_request_schema.py)** — Covers clearing each optional field and confirms a partial edit leaves other fields untouched.

---

## 3. Review and Approve Event Request

> As an Event Coordinator, I want to review submitted event requests so that I can clarify requirements and determine whether the request can proceed.

**Endpoints:** `GET /api/event-requests?status=submitted`, `POST /api/event-requests/<id>/review`, `GET /api/event-requests/<id>/reviews`, `GET /api/notifications?recipient_id=`

- **[backend/app/schemas/event_request_review.py](backend/app/schemas/event_request_review.py)** — Validates the review body, maps each outcome to the resulting status, and writes the notification wording for both parties. A comment is required when rejecting or asking for clarification, optional when approving.
- **[backend/app/services/event_request_review_service.py](backend/app/services/event_request_review_service.py)** — Records the review, updates the request's status, and triggers the notifications. Refuses to review a draft or an already-decided request.
- **[backend/app/services/notification_service.py](backend/app/services/notification_service.py)** — Builds and writes notification rows, one per recipient.
- **[backend/app/routes/notifications.py](backend/app/routes/notifications.py)** — Read-only listing so a user can see what they were notified about.
- **[backend/tests/test_event_request_review_schema.py](backend/tests/test_event_request_review_schema.py)** — Unit tests for the outcome rules and the comment requirement.
- **[supabase/003_create_review_and_notification.sql](supabase/003_create_review_and_notification.sql)** — Creates `event_request_review` (append-only audit trail) and `notification`.

**Note:** requesting clarification does not get its own status. The customer confirmed it "can be a sub-state of under_review", so the request stays `under_review` and the latest review row records what was asked.

---

## 4. Amend Event Request

> As an Event Organiser, I want to amend my event request when clarification or changes are requested by the Event Coordinator so that I can provide the required information and proceed with the event planning process.

**Endpoints:** `PATCH /api/event-requests/<id>` (with optional `note`), `POST /api/event-requests/<id>/submit`, `GET /api/event-requests/<id>/amendments`

- **[backend/app/services/event_request_workflow.py](backend/app/services/event_request_workflow.py)** — The lifecycle rules. `is_awaiting_clarification()` derives that state from the latest review rather than a status column; `edit()` and `send_for_review()` dispatch between draft handling and amendment handling so the client keeps using the same two endpoints.
- **[backend/app/schemas/event_request.py](backend/app/schemas/event_request.py)** — `diff()` records the before and after of each changed field, since the previous value is lost once the row is updated.
- **[backend/app/services/notification_service.py](backend/app/services/notification_service.py)** — Notifies the Coordinator who asked for clarification that a reply has arrived.
- **[backend/tests/test_event_request_amendment.py](backend/tests/test_event_request_amendment.py)** — Unit tests for the change record and for separating the Organiser's note from the request fields.
- **[supabase/004_create_event_request_amendment.sql](supabase/004_create_event_request_amendment.sql)** — Creates `event_request_amendment`, recording who changed what, when, and why.

---

## Known gaps

Carry these into sprint planning; they are not oversights.

- **No authentication.** `event_organiser_id`, `reviewer_id` and `recipient_id` all come from the client, so anyone can act as anyone. Marked `TODO` at each site. Depends on the User Authorisation and Authentication story.
- **Row Level Security is incomplete.** `users`, `roles`, `user_roles`, `events`, `equipment` and `equipment_request` are still reachable with the publishable key, which is public by design. `users` holds names and emails. Fix with `alter table <name> enable row level security;` once the team agrees.
- **No notification on submission.** The Coordinator is not told when a request arrives, because no coordinator is assigned yet. Depends on the Coordinator Assignment story.
- **Database schema is only partly in the repo.** `supabase/` covers `venues` and everything added during these stories, but `users`, `roles`, `user_roles`, `events`, `equipment` and `equipment_request` were created through the Supabase dashboard and have no migration file.
- **Frontend feature integration is incomplete.** The home launcher exists, but
  its tiles intentionally return to the home page until feature pages are ready.

---

## Running it

```bash
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest tests/     # 94 tests, no database needed
.venv\Scripts\python run.py               # http://localhost:5000
```

Requires `backend/.env` with `SUPABASE_URL` and `SUPABASE_ANON_KEY`. See
[backend/.env.example](backend/.env.example).

---

## Frontend Home page

The authenticated home page is an app launcher. It deliberately contains no
feature implementation, so other developers can build their pages independently.
Each tile links to its page when that page is available.

### Files and purpose

- **[frontend/src/pages/Home.jsx](frontend/src/pages/Home.jsx)** — Composes the
  navbar, page heading and application grid. Keep feature-specific logic out of
  this file.
- **[frontend/src/components/Navbar.jsx](frontend/src/components/Navbar.jsx)** —
  Reusable top navigation containing the ConnectSphere home link and account menu.
- **[frontend/src/components/AccountMenu.jsx](frontend/src/components/AccountMenu.jsx)** —
  Reusable account control. It currently shows signed-in state and sign out.
- **[frontend/src/components/AppGrid.jsx](frontend/src/components/AppGrid.jsx)** —
  Reusable grid that converts app configuration entries into tiles.
- **[frontend/src/components/AppTile.jsx](frontend/src/components/AppTile.jsx)** —
  Reusable tile displaying an icon with its app name underneath.
- **[frontend/src/config/apps.js](frontend/src/config/apps.js)** — The single list
  of home-page applications. Tiles should be added here, not hard-coded in
  `Home.jsx` or `AppGrid.jsx`.
- **[frontend/src/index.css](frontend/src/index.css)** — Shared visual tokens and
  home-page styles. Change the `--cs-*` variables to update the common colours,
  typography, borders and corner radii.

### Adding a new tile

Add one object to `HOME_APPS` in `frontend/src/config/apps.js`:

```js
{
  id: 'equipment',
  label: 'Equipment',
  description: 'Open Equipment',
  path: '/home',
  icon: '🖥️',
  roles: [],
}
```

`id` must be unique. `AppGrid` renders the new entry automatically. Keep `path`
as `/home` while the feature is unfinished; change it to the registered route
when the responsible developer completes that page. `roles` is reserved for
future role-based filtering; backend authorization must still enforce access.

---

## Frontend authentication and API requests

Authenticated pages share one session and request implementation. Do not read
tokens from session storage or implement refresh-and-retry logic inside a page.

- **[frontend/src/auth/AuthContext.jsx](frontend/src/auth/AuthContext.jsx)** —
  Owns the current Supabase session, sign-in/sign-out state and authenticated API
  calls. `api()` adds the bearer token, refreshes the session after a `401`, and
  retries the original request once. Concurrent `401` responses share one refresh
  request so pages cannot rotate the same refresh token multiple times.
- **[frontend/src/main.jsx](frontend/src/main.jsx)** — Wraps the application in
  `AuthProvider`.
- **[frontend/src/App.jsx](frontend/src/App.jsx)** — Uses the shared session to
  protect authenticated routes; it does not own token-refresh logic.
- **[frontend/src/components/AccountMenu.jsx](frontend/src/components/AccountMenu.jsx)** —
  Signs out through the shared authentication context.

Pages should call `const { api } = useAuth()` and then use
`api('/api/example', options)`. Pass plain objects as `options.body`; the helper
serialises them as JSON. Login and token refresh are the only unauthenticated
requests and remain inside `Login.jsx` and `AuthContext.jsx` respectively.

---

## Frontend Venue Search

Venue Search supports a simple venue-name search and an advanced filter search.
It does not assess booking conflicts or produce a suitability verdict.

- **[frontend/src/pages/VenueSearch.jsx](frontend/src/pages/VenueSearch.jsx)** —
  The venue catalogue: the event being planned, the filters in force as
  removable chips, and the results. Opened from an event it applies that
  event's requirements once, marked in the URL by `applied=1` so clearing them
  is not immediately undone.
- **[frontend/src/services/venueSearch.js](frontend/src/services/venueSearch.js)** —
  Reads and writes the search URL, which is the single source of truth for a
  search. Add a new filter here, not in a page.
- **[frontend/src/components/VenueResults.jsx](frontend/src/components/VenueResults.jsx)** —
  The results and what may be done with each one, including the disabled request
  action and the unmet requirements behind it.
- **[frontend/src/components/EventVenueContext.jsx](frontend/src/components/EventVenueContext.jsx)** —
  Which event the venue is being searched for: the removable condition when one
  is in context, the picker when none is.
- **[frontend/src/pages/VenueSearchResults.jsx](frontend/src/pages/VenueSearchResults.jsx)** —
  Now a redirect to `/venue-search`, carrying every filter in the URL across.
  Results moved onto the search page itself when the booking flow was reworked,
  so there is one results surface rather than two that could disagree about what
  may be requested. The route is kept so shared and bookmarked links still open.
- **[frontend/src/components/VenueSearchBar.jsx](frontend/src/components/VenueSearchBar.jsx)** —
  Reusable header search bar with a magnifying-glass submit control and query
  clear control. It is shown inside the navbar only on Venue Search pages;
  clearing the input does not navigate or remove active filters.
- **[frontend/src/components/VenueFilterForm.jsx](frontend/src/components/VenueFilterForm.jsx)** —
  Advanced filter-conditions form for available start/end dates, expected attendance, location,
  accessibility, one or more acceptable room layouts and required facilities.
  Every condition is a tickbox or an empty-means-any field, so each one can be
  switched on or off. It blocks incomplete or invalid date ranges and invalid
  attendance, then shows a reusable destructive alert below the action buttons
  before keeping the selected values in the URL. Shown inline on the catalogue
  behind Add filters / Edit filters, and opened showing the filters in force.
- **[frontend/src/pages/VenueSearchFilters.jsx](frontend/src/pages/VenueSearchFilters.jsx)** —
  The same form on a page of its own, kept for links that still point here.
- **[frontend/src/components/DateRangeCalendar.jsx](frontend/src/components/DateRangeCalendar.jsx)** —
  Reusable React Aria `RangeCalendar` wrapper used inside the date picker popup.
- **[frontend/src/components/DateRangePicker.jsx](frontend/src/components/DateRangePicker.jsx)** —
  Editable start and end date fields in `DD-MM-YYYY`. Focusing either field
  opens the range calendar popup; users may type dates or select them there.
- **[frontend/src/components/Alert.jsx](frontend/src/components/Alert.jsx)** —
  Browser port of the React Native Reusables Alert API: `Alert`,
  `AlertTitle` and `AlertDescription`. Use `variant="destructive"` for errors.
- **[backend/app/routes/venues.py](backend/app/routes/venues.py)** — Authenticated,
  read-only venue search endpoints. `GET /api/venues?name=` searches names;
  `GET /api/venues/search` applies advanced filters.
- **[backend/app/schemas/venue_search.py](backend/app/schemas/venue_search.py)** —
  Validates filter values, including `DD-MM-YYYY` dates, and makes the allowed
  layouts and facilities explicit.
- **[backend/app/services/venue_search_service.py](backend/app/services/venue_search_service.py)** —
  Builds the Supabase query, applies capacity/location/accessibility/facility/layout
  filters, and checks that each requested date is an operating day.
  It cannot check bookings until venue booking and unavailability tables exist.
- **[backend/tests/test_search_venues.py](backend/tests/test_search_venues.py)** —
  Tests only normal name-search casing, seeded venues, empty results and validation.
- **[backend/tests/test_filter_search.py](backend/tests/test_filter_search.py)** —
  Tests filter validation, query construction and single/multi-day operating-day
  matching without calling Supabase.
- **[frontend/src/App.jsx](frontend/src/App.jsx)** — Registers `/venue-search`,
  `/venue-search/results` and `/venue-search/filters`; all require an
  authenticated session.

### Searching for the event being planned

Venue Search opens from an event in planning, and the event's own requirements
become its filters. See [docs/venue-bookings.md](docs/venue-bookings.md) for the
flow and for the three places the requirement gate is enforced.

- **[backend/app/services/event_venue_criteria.py](backend/app/services/event_venue_criteria.py)** —
  What an event needs from a venue and whether a venue meets it. No Flask or
  Supabase imports, so the rules are unit tested on their own. The weekly
  operating-hours rule lives here and `venue_search_service` calls into it, so
  the filter search and the event check cannot drift apart.
- **[backend/tests/test_event_venue_criteria.py](backend/tests/test_event_venue_criteria.py)** —
  The requirement rules, the Singapore-time day boundaries, and the two
  event-aware endpoints.

This is a verdict against **one event's recorded requirements**, which is not
the Venue Suitability Checking story: that one compares a venue against an event
and reports on the comparison, including the parts no filter can express.
Keep that reporting out of here, and build it on
`event_venue_criteria.unmet_requirements()` rather than a second copy of these
rules.

### Approve or reject venue booking requests

Venue Staff review on `/review-venue-bookings`; coordinators follow their
requests on `/venue-bookings`. See [docs/venue-bookings.md](docs/venue-bookings.md).

- **[supabase/026_review_venue_bookings.sql](supabase/026_review_venue_bookings.sql)** —
  `review_venue_booking()` holds every rule: Venue Staff only, a reason to
  reject, a once-only decision, and approval rechecked against the event as it
  is now. Also the coordinator's alert rows and the functions that read them.
- **[backend/app/schemas/venue_booking_review.py](backend/app/schemas/venue_booking_review.py)** —
  The same decision rules, checked before the database so errors are per field.
- **[backend/app/routes/venue_bookings.py](backend/app/routes/venue_bookings.py)** —
  Thin: validates, calls a database function, passes its refusal on unchanged.
- **[frontend/src/pages/ReviewVenueBookings.jsx](frontend/src/pages/ReviewVenueBookings.jsx)**,
  **[ReviewVenueBooking.jsx](frontend/src/pages/ReviewVenueBooking.jsx)** — The
  queue and the decision, modelled on Review Event Requests.
- **[frontend/src/pages/VenueBookings.jsx](frontend/src/pages/VenueBookings.jsx)** —
  The coordinator's requests by stage, with the alert banner.
- **[backend/tests/test_venue_booking_review.py](backend/tests/test_venue_booking_review.py)** —
  Tests labelled with the acceptance criterion each covers.

### Conflicting venue bookings

Only an approved booking makes a venue unavailable. See
[docs/venue-bookings.md](docs/venue-bookings.md#conflicting-bookings).

- **[supabase/027_venue_booking_conflicts.sql](supabase/027_venue_booking_conflicts.sql)** —
  The rule: refused requests and approvals, the exclusion constraint that holds
  under concurrency, and `venue_booking_summary()`, which decides how much of
  another coordinator's booking a reader may see.
- **[backend/app/services/venue_availability.py](backend/app/services/venue_availability.py)** —
  The same half-open overlap rule, used to mark search results in one lookup.
- **[frontend/src/components/BookingConflicts.jsx](frontend/src/components/BookingConflicts.jsx)** —
  How a conflicting booking is described, wherever one appears.
- **[backend/tests/test_venue_booking_conflicts.py](backend/tests/test_venue_booking_conflicts.py)** —
  The overlap boundaries and each acceptance criterion.
