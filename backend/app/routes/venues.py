"""Read-only venue catalogue endpoints."""

from urllib.parse import quote

from flask import Blueprint, jsonify, request

from app.routes.events import authenticated_token
from app.schemas.venue_search import parse_filters
from app.services.event_store import StoreError, supabase_request
from app.services.venue_search_service import search_venues

venues = Blueprint("venues", __name__, url_prefix="/api/venues")

_VENUE_FIELDS = (
    "venue_id,venue_name,capacity,building_name,block_number,street_name,"
    "postal_code,unit_number,wheelchair_accessible,blind_accessible,"
    "accessibility_notes,facilities,supported_room_layouts,operating_hours,"
    "default_setup_minutes,default_turnaround_minutes"
)


def venue_catalogue_path(name=None):
    """Build the ordered catalogue query, optionally filtered by venue name."""
    path = f"/rest/v1/venues?select={_VENUE_FIELDS}"
    if name:
        path += f"&venue_name=ilike.*{quote(name, safe='')}*"
    return path + "&order=venue_name.asc"


def venue_name_search_path(name):
    """Build the case-insensitive Supabase query for a venue-name search."""
    return venue_catalogue_path(name)


@venues.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@venues.errorhandler(StoreError)
def handle_store_error(error):
    message = "Please sign in again." if error.status == 401 else "Venue search is temporarily unavailable."
    return jsonify(error=message), error.status


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
    """Find venues that meet the advanced search conditions."""
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
    return jsonify(count=len(rows), venues=rows)
