"""Venue search and catalogue management endpoints."""

from uuid import UUID
from urllib.parse import quote
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.routes.events import EVENT_SUMMARY_FIELDS, authenticated_token, valid_event_id
from app.schemas.venue_search import parse_filters
from app.schemas.venue import parse_create, parse_update
from app.services.event_service import EventError, load_event
from app.services.event_store import StoreError, supabase_request
from app.services.event_venue_criteria import annotate, criteria_from_event, describe
from app.services.venue_availability import mark_for_event
from app.services.venue_search_service import search_venues

venues = Blueprint("venues", __name__, url_prefix="/api/venues")

_VENUE_FIELDS = (
    "venue_id,venue_name,capacity,building_name,block_number,street_name,"
    "postal_code,unit_number,wheelchair_accessible,blind_accessible,"
    "accessibility_notes,facilities,supported_room_layouts,operating_hours,"
    "default_setup_minutes,default_turnaround_minutes,version,updated_at,deleted_at"
)

_ACTIVE_VENUE_FILTER = "deleted_at=is.null"


def venue_catalogue_path(name=None):
    """Build the ordered catalogue query, optionally filtered by venue name."""
    path = f"/rest/v1/venues?select={_VENUE_FIELDS}"
    if name:
        path += f"&venue_name=ilike.*{quote(name, safe='')}*"
    return path + f"&{_ACTIVE_VENUE_FILTER}&order=venue_name.asc"


def venue_name_search_path(name):
    """Build the case-insensitive Supabase query for a venue-name search."""
    return venue_catalogue_path(name)


def venue_detail_path(venue_id):
    return f"/rest/v1/venues?select={_VENUE_FIELDS}&venue_id=eq.{venue_id}&{_ACTIVE_VENUE_FILTER}&limit=1"


def venue_update_path(venue_id, version):
    """Target exactly the version of a venue the staff member reviewed."""
    return f"/rest/v1/venues?select={_VENUE_FIELDS}&venue_id=eq.{venue_id}&version=eq.{version}&{_ACTIVE_VENUE_FILTER}"


def venue_delete_path(venue_id):
    return f"/rest/v1/venues?select={_VENUE_FIELDS}&venue_id=eq.{venue_id}&{_ACTIVE_VENUE_FILTER}"


def upcoming_event_path(venue_id):
    """Return events that start from this moment onwards for one venue."""
    now = quote(datetime.now(timezone.utc).isoformat(), safe="")
    return (
        "/rest/v1/events?select=event_id,event_name,status,start_datetime,end_datetime"
        f"&venue_id=eq.{venue_id}&start_datetime=gte.{now}&order=start_datetime.asc"
    )


def upcoming_booking_path(venue_id):
    """Approved venue bookings that have not finished yet."""
    now = quote(datetime.now(timezone.utc).isoformat(), safe="")
    return (
        "/rest/v1/venue_booking_requests?select=event_id,event_name,starts_at"
        f"&venue_id=eq.{venue_id}&status=eq.approved&ends_at=gt.{now}&order=starts_at.asc"
    )


def upcoming_approved_bookings(venue_id, token):
    return supabase_request(upcoming_booking_path(venue_id), token=token)


def scheduled_upcoming_events(venue_id, token):
    """Everything ahead that still needs this venue.

    An approved booking commits the venue just as surely as an event linked to
    it, so both block deletion. Bookings are reported in the same shape as
    events, so the deletion page lists them without knowing the difference.
    """
    rows = supabase_request(upcoming_event_path(venue_id), token=token)
    inactive_statuses = {"cancelled", "completed", "rejected"}
    events = [row for row in rows if str(row.get("status", "")).lower() not in inactive_statuses]

    listed = {row.get("event_id") for row in events}
    for booking in upcoming_approved_bookings(venue_id, token):
        # An event can be linked to the venue and booked into it as well; it is
        # one reason to keep the venue, not two.
        if booking.get("event_id") in listed and booking.get("event_id") is not None:
            continue
        listed.add(booking.get("event_id"))
        events.append({
            "event_id": booking.get("event_id"),
            "event_name": booking.get("event_name"),
            "status": "approved booking",
            "start_datetime": booking.get("starts_at"),
        })
    return events


def deletion_conflict_response(conflicts):
    return jsonify(
        error="This venue cannot be deleted because it has upcoming scheduled events.",
        events=conflicts,
    ), 409


@venues.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@venues.errorhandler(StoreError)
def handle_store_error(error):
    if error.code == "23505":
        return jsonify(
            error="A venue with the same name and address already exists.",
            errors={"venue_name": "Use a different venue name or address."},
        ), 409
    if error.code == "42501":
        return jsonify(error="You do not have permission to manage the venue catalogue."), 403
    if error.code == "23503":
        return jsonify(error="This venue cannot be deleted because it is still linked to an event."), 409
    message = "Please sign in again." if error.status == 401 else "Venue search is temporarily unavailable."
    return jsonify(error=message), error.status


@venues.errorhandler(EventError)
def handle_event_error(error):
    """A search carrying an event_id the caller may not read is a 404 here."""
    return jsonify(error.to_dict()), error.status


@venues.get("")
def search_by_name():
    """Find catalogue venues whose names contain the supplied text."""
    token = authenticated_token()
    name = request.args.get("name", "").strip()

    if not name:
        return jsonify(error="Enter a venue name to search."), 400
    if len(name) > 100:
        return jsonify(error="Venue name search must be 100 characters or fewer."), 400

    # PostgREST's `ilike` makes the match case-insensitive. The * wildcard is
    # intentionally added around, not inside, the user's encoded search text.
    rows = supabase_request(venue_name_search_path(name), token=token)

    return jsonify(count=len(rows), venues=rows)


@venues.get("/catalogue")
def list_catalogue():
    """Return every venue for the Venue Management catalogue."""
    token = authenticated_token()
    rows = supabase_request(venue_catalogue_path(), token=token)
    return jsonify(count=len(rows), venues=rows)


@venues.get("/search")
def search_with_filters():
    """Find venues that meet the advanced search conditions.

    An optional `event_id` says which event the coordinator is searching for.
    It does not narrow the results: the filters alone decide what is listed, so
    they can be cleared and the whole catalogue read. What it adds is the
    verdict for each venue, because a venue that cannot meet the event's
    requirements must not be offered for a booking request even when the
    coordinator has cleared the filter that would have hidden it.
    """
    token = authenticated_token()
    payload = {
        "name": request.args.get("name"),
        "start_date": request.args.get("start_date"),
        "end_date": request.args.get("end_date"),
        "capacity": request.args.get("capacity"),
        "location": request.args.get("location"),
        "layouts": request.args.getlist("layouts"),
        "facilities": request.args.getlist("facilities"),
        "wheelchair_accessible": request.args.get("wheelchair_accessible"),
        "blind_accessible": request.args.get("blind_accessible"),
    }
    filters, errors = parse_filters(payload)
    if errors:
        return jsonify(error="Some filter conditions are invalid.", errors=errors), 400

    rows = search_venues(filters, token)

    event_id = (request.args.get("event_id") or "").strip()
    if not event_id:
        return jsonify(count=len(rows), venues=rows)

    event_id_value = valid_event_id(event_id)
    if event_id_value is None:
        return jsonify(error="Event not found or access unavailable."), 404

    # Read with the caller's own token, so an event they are not assigned to is
    # not found rather than searchable.
    event = load_event(event_id_value, token)
    criteria = criteria_from_event(event)
    # Requirements first, then availability: a venue can fail either, and the
    # page shows both reasons rather than just the first one found.
    assessed = mark_for_event(annotate(rows, criteria), event, token)

    return jsonify(
        count=len(assessed),
        venues=assessed,
        event={field: event.get(field) for field in EVENT_SUMMARY_FIELDS},
        requirements=describe(criteria),
        eligible_count=sum(1 for venue in assessed if venue["eligible"]),
    )


@venues.get("/<venue_id>")
def get_venue(venue_id):
    """Return every stored characteristic for one venue.

    With an `event_id`, the venue also carries the verdict for that event, so
    the page that is about to request a booking shows the same requirements the
    database will check rather than discovering them in a refusal.
    """
    token = authenticated_token()
    try:
        venue_id = str(UUID(venue_id))
    except ValueError:
        return jsonify(error="Venue not found or access unavailable."), 404

    rows = supabase_request(venue_detail_path(venue_id), token=token)
    if not rows:
        return jsonify(error="Venue not found or access unavailable."), 404

    event_id = (request.args.get("event_id") or "").strip()
    if not event_id:
        return jsonify(venue=rows[0])

    event_id_value = valid_event_id(event_id)
    if event_id_value is None:
        return jsonify(error="Event not found or access unavailable."), 404

    event = load_event(event_id_value, token)
    criteria = criteria_from_event(event)
    return jsonify(
        venue=mark_for_event(annotate(rows, criteria), event, token)[0],
        event={field: event.get(field) for field in EVENT_SUMMARY_FIELDS},
        requirements=describe(criteria),
    )


@venues.get("/<venue_id>/deletion-check")
def check_venue_deletion(venue_id):
    """Load the confirmation information and any upcoming-event conflicts."""
    token = authenticated_token()
    try:
        venue_id = str(UUID(venue_id))
    except ValueError:
        return jsonify(error="This venue has already been deleted or is unavailable."), 404

    rows = supabase_request(venue_detail_path(venue_id), token=token)
    if not rows:
        return jsonify(error="This venue has already been deleted or is unavailable."), 404
    return jsonify(venue=rows[0], events=scheduled_upcoming_events(venue_id, token))


@venues.post("")
def create_venue():
    """Validate and add one complete venue to the catalogue."""
    token = authenticated_token()
    record, errors = parse_create(request.get_json(silent=True))
    if errors:
        return jsonify(
            error="The venue could not be created because some details are missing or invalid.",
            errors=errors,
        ), 400

    rows = supabase_request(
        f"/rest/v1/venues?select={_VENUE_FIELDS}", token=token, payload=record
    )
    if not rows:
        raise StoreError(503, "The venue could not be created. Please try again.")
    return jsonify(message="Venue created successfully.", venue=rows[0]), 201


@venues.patch("/<venue_id>")
def update_venue(venue_id):
    """Apply only supplied venue fields, refusing a stale edit."""
    token = authenticated_token()
    try:
        venue_id = str(UUID(venue_id))
    except ValueError:
        return jsonify(error="Venue not found or access unavailable."), 404

    changes, version, errors = parse_update(request.get_json(silent=True))
    if errors:
        return jsonify(
            error="The venue could not be updated because some details are invalid.",
            errors=errors,
        ), 400

    rows = supabase_request(
        venue_update_path(venue_id, version), token=token, payload=changes, method="PATCH"
    )
    if rows:
        return jsonify(message="Venue information updated successfully.", venue=rows[0])

    # A zero-row PATCH is either a stale version or a venue that is no longer
    # accessible.  Returning the current row makes the conflict actionable:
    # the UI resets the form so staff redo the update using fresh information.
    current = supabase_request(venue_detail_path(venue_id), token=token)
    if not current:
        return jsonify(error="Venue not found or access unavailable."), 404
    return jsonify(
        error=(
            "This venue was changed by another staff member. Review the current "
            "information and redo your update."
        ),
        venue=current[0],
    ), 409


@venues.delete("/<venue_id>")
def delete_venue(venue_id):
    """Delete a venue only after rechecking for future scheduled events."""
    token = authenticated_token()
    try:
        venue_id = str(UUID(venue_id))
    except ValueError:
        return jsonify(error="This venue has already been deleted or is unavailable."), 404

    rows = supabase_request(venue_detail_path(venue_id), token=token)
    if not rows:
        return jsonify(error="This venue has already been deleted or is unavailable."), 404

    conflicts = scheduled_upcoming_events(venue_id, token)
    if conflicts:
        return deletion_conflict_response(conflicts)

    deleted = supabase_request(
        venue_delete_path(venue_id),
        token=token,
        payload={"deleted_at": datetime.now(timezone.utc).isoformat()},
        method="PATCH",
        return_representation=True,
    )
    if not deleted:
        return jsonify(error="This venue has already been deleted or is unavailable."), 404
    return jsonify(message="Venue removed from the catalogue successfully.", venue=deleted[0])
