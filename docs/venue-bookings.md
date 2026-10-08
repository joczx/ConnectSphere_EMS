# Venue booking submission

A venue is requested for one event, from the event being planned. The flow is:

**Events → an event in planning → Find venues for this event → Venue Search → Request this venue.**

## Applying the migrations

Apply `supabase/017_venue_bookings.sql` with a trusted database administrator after the venue
catalogue and users/roles/user_roles tables exist, then `supabase/025_event_venue_booking_flow.sql`
after `024_tighten_write_access.sql`. Assign existing accounts the `Event Coordinator` or
`Venue Staff` role through trusted admin tooling (underscore spellings are also supported).

017 revokes client writes to roles and user_roles so clients cannot grant themselves booking
privileges. It creates the booking request table, read policies and authenticated submission/list
RPCs. Submitter identity comes from `auth.uid()`, never the request body. Coordinators see their
own requests; Venue Staff see all requests. No venue-specific staff assignment currently exists.

025 adds `event_id` to the request and replaces `submit_venue_booking`. A new request must name an
event the caller coordinates, which is still in planning, and the period and attendance it carries
must match that event. `event_id` is nullable because requests taken under 017 have no event to
point at.

## Searching from the event

The event records what it needs from a venue — expected attendance, room layout, required
facilities, wheelchair and blind accessibility, and the period it runs over — so Venue Search opens
with those as its filters rather than asking the coordinator to retype them. The event is shown as
a removable search condition, and `GET /api/events/<id>/venue-criteria` is what supplies both the
filters and their wording.

Reaching Venue Search from the home page instead, there is no event and no filter: the whole
catalogue is listed, and an event can be chosen on the page to switch into planning for it.

The filters can be widened, individually removed or cleared entirely, including the event's own,
and the catalogue is then read in full. **Clearing a filter does not make an unsuitable venue
requestable.** While an event is in context, every result carries the verdict for that event:
one that fails a requirement is listed, marked with what it fails, and its request action is
disabled.

That gate is enforced in three places, because a disabled button is not a rule:

- `event_venue_criteria.unmet_requirements()` decides the verdict shown on every result.
- `venue_shortfalls_for_event()` in 025 decides whether the request is accepted at all, including
  one that never went through the page.
- The two are deliberate copies of one rule. Change them together.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/events/<id>/venue-criteria` | The event's venue requirements as search filters (`filters`), as display text (`requirements`), and whether it is still in planning. |
| `GET /api/venues/search?event_id=` | The usual filter search. `event_id` does not narrow the results; it adds `eligible` and `unmet_requirements` to each venue plus an `eligible_count`. |
| `GET /api/venues/<venue_id>?event_id=` | One venue carrying the same verdict, for the page about to request it. |
| `POST /api/venue-bookings` | `event_id`, `venue_id`, `event_name`, timezone-aware ISO `starts_at`/`ends_at`, integer `attendance`, `venue_requirements`. |
| `GET /api/venue-bookings` | The authorized queue and role capabilities. |

All require bearer authentication. An unsuitable venue is refused with 409 and
`unmet_requirements`; a request whose period or attendance disagrees with its event is refused with
409 as well, because the event is where a date is changed — that path warns the coordinator about
arrangements already made against it.

## Reviewing a request (Venue Staff)

Apply `supabase/026_review_venue_bookings.sql` after 025.

**Review Venue Bookings** (`/review-venue-bookings`) lists requests as Received, Approved and
Rejected, modelled on Review Event Requests. Opening one shows the event, venue, period, attendance,
venue requirements and who asked, then Approve or Reject with comments. **Venue Bookings**
(`/venue-bookings`) is the coordinator's side, modelled on My Event Requests: Submitted, Approved and
Rejected, each showing the decision and the staff comments.

The rules live in `review_venue_booking()`:

- Only Venue Staff may decide, and a rejection needs a reason. Both are also checked in
  `schemas/venue_booking_review.py`, so the reviewer is told field by field.
- A decision is final and made once. The write only matches a request still awaiting review, so two
  reviewers deciding together cannot both succeed.
- Approval rechecks the venue against the event **as it is now**, because the event may have had a
  critical edit since the request. A venue that no longer fits, or an event no longer in planning,
  can only be rejected. The review page shows those shortfalls before the reviewer decides.
- The reviewer is the signed-in user, never a value from the request body.

The coordinator is alerted by a `notification` row linked to the request (`venue_booking_id`). It
appears as a "New decisions" banner on Venue Bookings until dismissed. The alert is best effort: if
it cannot be written, the decision still stands, and the outcome and comments are on the request
itself either way.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/venue-bookings/<id>` | One request the caller may see, with `current_shortfalls` while it awaits review. |
| `POST /api/venue-bookings/<id>/review` | `outcome` (`approved` or `rejected`) and `comments`. |
| `GET /api/venue-bookings/alerts` | The caller's unread decisions. |
| `POST /api/venue-bookings/alerts/dismiss` | `notification_ids` to mark as read; only the caller's own are touched. |

An approval does not set `events.venue_id`: an event may need more than one venue, which a single
column cannot hold. The event planning page lists approved venues from the requests instead.

## Conflicting bookings

Apply `supabase/027_venue_booking_conflicts.sql` after 026. Its header has a query to run first:
the constraint it adds refuses to be created if two approved bookings already overlap.

**Only an approved booking makes a venue unavailable.** Pending requests may overlap one another
freely; the first approval settles the slot. Periods are half-open, `[start, end)`, so a booking
ending at 18:00 does not block one starting at 18:00. Setup and turnaround minutes are not added.

Once a booking is approved for a period:

- **Venue Search**, opened from an event, lists the venue but marks it "Booked during this event's
  time" with the booking shown, and offers no request. Search without an event has no exact period
  to check, so it marks nothing.
- **Requesting** it for an overlapping period is refused by `submit_venue_booking()`, naming the
  booking.
- **Approving** an overlapping pending request is refused by `review_venue_booking()`, and the
  review page disables Approve and says why. The queue flags such requests, and those still competing
  for one slot.
- The exclusion constraint `venue_booking_no_double_booking` makes two overlapping approvals
  impossible even when two reviewers approve at the same moment, where the checks alone could not.

A conflicting booking always shows its period. Its event is named only to Venue Staff and to the
coordinator who made that request; anyone else reads "another event". Pending requests are shown
only to Venue Staff and their own requester. That redaction lives in `venue_booking_summary()`.

## Approval matches the event and venue as they are

Apply `supabase/028_approval_matches_event.sql` after 027. Approval is refused, and the request can
only be rejected, when:

- **the event moved after the request** — its period or attendance no longer matches, and approving
  would book the old time (`matches_event` is false on the request);
- **the venue was removed** from the catalogue (`venue_deleted`);
- the event or venue would change *during* the approval — both rows are read `FOR SHARE`, so an edit
  waits until the approval has committed.

A venue with an approved booking still ahead cannot be deleted; the deletion page lists the booking
alongside any scheduled events.

## Scope

Approving a request does not reserve setup or turnaround time either side of the booking.

## Validation

`python -m pytest tests/test_venue_bookings.py tests/test_event_venue_criteria.py tests/test_venue_booking_review.py tests/test_venue_booking_conflicts.py`
from backend;
`npm run build` from frontend. Python tests mock Supabase, so they verify the API's own behaviour
and not the deployed policies. After applying the migrations, verify with separate coordinator,
staff and unrelated accounts that:

- a coordinator reaches Venue Search from their event with its requirements applied, and sees the
  whole catalogue once they clear them;
- a venue that fails a requirement cannot be requested, and `submit_venue_booking` refuses it when
  called directly;
- an `event_id` belonging to another coordinator is not found, by search or by submission;
- a persisted submission appears for staff, unrelated users can neither submit nor read it, and
  direct table writes are denied;
- a coordinator calling `review_venue_booking` directly is refused, a rejection without a reason is
  refused, and a second decision on the same request is refused;
- after a decision the coordinator sees the outcome and comments on Venue Bookings and on the
  event, and the alert banner clears once dismissed and stays cleared after a reload.
