"""What an event needs from a venue, and whether a venue meets it.

Backs the planning-first half of the venue booking story: a coordinator reaches
Venue Search from the event they are planning, so the requirements the event
already records should become the search conditions rather than being retyped,
and a venue that cannot meet them should not be offered for a booking request.

Deliberately free of Flask and Supabase imports, like the schema modules, so
the rules can be unit tested on their own. The field names are the ones
public.events uses on one side and the Venue Search filters use on the other;
translating between the two is the whole job of this module.
"""

from datetime import date, datetime, timedelta, timezone

from app.schemas import event as event_schema
from app.schemas.venue_search import FACILITIES as CATALOGUE_FACILITIES

# Every date the user sees in ConnectSphere is Singapore time, and an event
# spanning midnight UTC must still be checked against the local day it runs on.
SGT = timezone(timedelta(hours=8))

DATE_FORMAT = "%d-%m-%Y"

# The event fields that constrain which venue can be used, in the order they
# are presented to the coordinator.
CONSTRAINING_FIELDS = (
    "capacity_needed",
    "room_layout",
    "required_facilities",
    "need_wheelchair_accessibility",
    "need_blind_accessibility",
    "start_datetime",
    "end_datetime",
)


def criteria_from_event(event):
    """The venue requirements this event carries.

    A value of None always means "the event does not constrain this", which is
    not the same as "the event needs nothing": required_facilities is null while
    the organiser has not answered and [] once they answer none.
    """
    return {
        "capacity": _positive_int(event.get("capacity_needed")),
        "layout": _text(event.get("room_layout")),
        "facilities": sorted({
            facility for facility in (event.get("required_facilities") or [])
            if isinstance(facility, str) and facility.strip()
        }),
        # Only a True flag is a requirement. "No wheelchair access needed" does
        # not make a venue that has it unsuitable.
        "wheelchair_accessible": True if event.get("need_wheelchair_accessibility") else None,
        "blind_accessible": True if event.get("need_blind_accessibility") else None,
        "start_date": local_date(event.get("start_datetime")),
        "end_date": local_date(event.get("end_datetime")),
    }


def search_filters(criteria):
    """The same requirements as Venue Search query parameters.

    Returned as the strings and lists the search endpoint parses, so the client
    can prefill the filter form and the server can apply them without either
    side restating how a filter is spelled.
    """
    filters = {}
    if criteria["capacity"] is not None:
        filters["capacity"] = str(criteria["capacity"])
    if criteria["layout"]:
        filters["layouts"] = [criteria["layout"]]
    # An event can record a facility the venue catalogue has no word for, such
    # as a whiteboard. The search refuses a filter it cannot express, which
    # would turn "no venue has this" into an error, so such a facility is left
    # out of the filters. It still counts in unmet_requirements(), so every
    # venue is marked as missing it rather than quietly offered.
    facilities = [f for f in criteria["facilities"] if f in CATALOGUE_FACILITIES]
    if facilities:
        filters["facilities"] = facilities
    if criteria["wheelchair_accessible"]:
        filters["wheelchair_accessible"] = "true"
    if criteria["blind_accessible"]:
        filters["blind_accessible"] = "true"
    # Both or neither: the date filter is a range and the search refuses half of
    # one.
    if criteria["start_date"] and criteria["end_date"]:
        filters["start_date"] = criteria["start_date"].strftime(DATE_FORMAT)
        filters["end_date"] = criteria["end_date"].strftime(DATE_FORMAT)
    return filters


def describe(criteria):
    """The requirements as the coordinator reads them on the page.

    Built here so the search page, the filter form and the refusal to book an
    unsuitable venue all name a requirement the same way.
    """
    described = []

    def add(field, value):
        described.append({
            "field": field,
            "label": event_schema.LABELS.get(field, field),
            "value": value,
        })

    if criteria["capacity"] is not None:
        add("capacity_needed", "At least " + str(criteria["capacity"]))
    if criteria["layout"]:
        add("room_layout", _readable(criteria["layout"]))
    if criteria["facilities"]:
        add("required_facilities", ", ".join(_readable(f) for f in criteria["facilities"]))
    if criteria["wheelchair_accessible"]:
        add("need_wheelchair_accessibility", "Required")
    if criteria["blind_accessible"]:
        add("need_blind_accessibility", "Required")
    if criteria["start_date"] and criteria["end_date"]:
        add("start_datetime", _readable_period(criteria["start_date"], criteria["end_date"]))

    return described


def unmet_requirements(venue, criteria):
    """Which of the event's requirements this venue fails, if any.

    The coordinator is allowed to clear the search filters and look at the whole
    catalogue, so an unsuitable venue does reach the page. What it must not do
    is reach a booking request, and this is the list that stops it: it marks the
    venue on screen and it explains the refusal.
    """
    unmet = []

    def fail(field, detail):
        unmet.append({
            "field": field,
            "label": event_schema.LABELS.get(field, field),
            "detail": detail,
        })

    capacity = _positive_int(venue.get("capacity"))
    if criteria["capacity"] is not None:
        if capacity is None:
            fail("capacity_needed", "This venue does not record a capacity.")
        elif capacity < criteria["capacity"]:
            fail(
                "capacity_needed",
                "Holds " + str(capacity) + ", but " + str(criteria["capacity"])
                + " are expected.",
            )

    layouts = _names(venue.get("supported_room_layouts"))
    if criteria["layout"] and criteria["layout"] not in layouts:
        fail(
            "room_layout",
            "Does not support a " + _readable(criteria["layout"]).lower() + " layout.",
        )

    facilities = _names(venue.get("facilities"))
    missing = [f for f in criteria["facilities"] if f not in facilities]
    if missing:
        fail(
            "required_facilities",
            "Missing " + ", ".join(_readable(f).lower() for f in missing) + ".",
        )

    if criteria["wheelchair_accessible"] and not venue.get("wheelchair_accessible"):
        fail("need_wheelchair_accessibility", "This venue is not wheelchair accessible.")

    if criteria["blind_accessible"] and not venue.get("blind_accessible"):
        fail("need_blind_accessibility", "This venue is not accessible for blind attendees.")

    closed = closed_days(venue, criteria["start_date"], criteria["end_date"])
    if closed:
        fail(
            "start_datetime",
            "Closed on " + ", ".join(day.capitalize() for day in closed) + ".",
        )

    return unmet


def meets(venue, criteria):
    """True when a booking request for this venue may be made for the event."""
    return not unmet_requirements(venue, criteria)


def annotate(venues, criteria):
    """Copy each venue with the event verdict attached.

    Copied rather than changed in place, so a row held elsewhere is never
    altered by being looked at through one event's requirements.
    """
    annotated = []
    for venue in venues:
        unmet = unmet_requirements(venue, criteria)
        annotated.append({**venue, "unmet_requirements": unmet, "eligible": not unmet})
    return annotated


def closed_days(venue, start_date, end_date):
    """Weekdays in the period on which the catalogue says the venue is shut.

    An empty list when no period is given: a venue cannot be ruled out by hours
    nobody asked about. A venue with no recorded hours is treated as closed
    throughout, because booking it would be guesswork.
    """
    if start_date is None or end_date is None or end_date < start_date:
        return []

    hours = venue.get("operating_hours")
    days, current = [], start_date
    while current <= end_date:
        name = current.strftime("%A").lower()
        if name not in days and not _open_on(hours, name):
            days.append(name)
        # A period longer than a week can only repeat the same seven days.
        if len(days) == 7:
            break
        current += timedelta(days=1)
    return days


def local_date(value):
    """The Singapore-time calendar date of a stored timestamp."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, date):
        return value
    elif isinstance(value, str) and value.strip():
        try:
            moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(SGT).date()


def _open_on(hours, day_name):
    if not isinstance(hours, dict):
        return False
    day = hours.get(day_name)
    return isinstance(day, dict) and day.get("closed") is not True


def _names(values):
    if not isinstance(values, list):
        return set()
    return {value for value in values if isinstance(value, str)}


def _positive_int(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _readable(value):
    text = str(value).replace("_", " ")
    return text[:1].upper() + text[1:]


def _readable_period(start_date, end_date):
    start = start_date.strftime(DATE_FORMAT)
    return start if start_date == end_date else start + " to " + end_date.strftime(DATE_FORMAT)
