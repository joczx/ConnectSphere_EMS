"""Supabase query construction and operating-hours checks for Venue Search."""

from datetime import timedelta
from urllib.parse import quote

from app.services.event_store import supabase_request

VENUE_FIELDS = (
    "venue_id,venue_name,capacity,building_name,block_number,street_name,"
    "postal_code,wheelchair_accessible,blind_accessible,facilities,"
    "supported_room_layouts,operating_hours"
)


def search_venues(filters, token):
    """Fetch candidates from Supabase, then check requested operating hours."""
    rows = supabase_request(filter_search_path(filters), token=token)
    return [venue for venue in rows if matches_operating_hours(venue, filters)]


def filter_search_path(filters):
    """Build a safe PostgREST query from already validated filters."""
    query = [f"select={VENUE_FIELDS}"]
    if filters["name"]:
        name = quote(filters["name"], safe="")
        query.append(f"venue_name=ilike.*{name}*")
    if filters["capacity"] is not None:
        query.append(f"capacity=gte.{filters['capacity']}")
    if filters["location"]:
        location = quote(filters["location"], safe="")
        query.append(
            "or=("
            f"venue_name.ilike.*{location}*,building_name.ilike.*{location}*,"
            f"street_name.ilike.*{location}*,postal_code.ilike.*{location}*"
            ")"
        )
    if filters["layouts"]:
        query.append("supported_room_layouts=ov.{" + ",".join(filters["layouts"]) + "}")
    if filters["facilities"]:
        query.append("facilities=cs.{" + ",".join(filters["facilities"]) + "}")
    if filters["wheelchair_accessible"] is True:
        query.append("wheelchair_accessible=eq.true")
    if filters["blind_accessible"] is True:
        query.append("blind_accessible=eq.true")
    query.append("order=venue_name.asc")
    return "/rest/v1/venues?" + "&".join(query)


def matches_operating_hours(venue, filters):
    """Check the catalogue's weekly hours; booking conflicts are not covered."""
    start = filters["start_date"]
    end = filters["end_date"]
    if start is None:
        return True

    hours = venue.get("operating_hours")
    if not isinstance(hours, dict):
        return False

    current_day = start
    while current_day <= end:
        day = hours.get(current_day.strftime("%A").lower())
        if not _is_open_for_day(day):
            return False
        current_day += timedelta(days=1)
    return True


def _is_open_for_day(day):
    return isinstance(day, dict) and day.get("closed") is not True
