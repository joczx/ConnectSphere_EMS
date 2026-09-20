"""Validation rules for Venue Search filters."""

from datetime import datetime

ROOM_LAYOUTS = frozenset(
    {"theatre", "classroom", "boardroom", "banquet", "exhibition", "u_shape", "cabaret"}
)
FACILITIES = frozenset(
    {
        "stage",
        "projector",
        "sound_system",
        "video_conferencing",
        "wifi",
        "parking",
        "catering_area",
        "air_conditioning",
    }
)


def parse_filters(payload):
    """Return cleaned filters and field errors for an advanced venue search."""
    filters = {"capacity": None, "location": None, "layouts": [], "facilities": [],
               "wheelchair_accessible": None, "blind_accessible": None,
               "start_date": None, "end_date": None}
    errors = {}

    filters["capacity"] = _positive_integer(payload.get("capacity"), "capacity", errors)
    filters["location"] = _text(payload.get("location"), "location", errors)
    filters["layouts"] = _choices(payload.get("layouts", []), ROOM_LAYOUTS, "layouts", errors)
    filters["facilities"] = _choices(payload.get("facilities", []), FACILITIES, "facilities", errors)
    filters["wheelchair_accessible"] = _required_accessibility(
        payload.get("wheelchair_accessible"), "wheelchair_accessible", errors
    )
    filters["blind_accessible"] = _required_accessibility(
        payload.get("blind_accessible"), "blind_accessible", errors
    )
    _parse_event_period(payload, filters, errors)

    return filters, errors


def _positive_integer(value, field, errors):
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        errors[field] = "Expected attendance must be a positive whole number."
        return None
    if isinstance(value, bool) or str(number) != str(value).strip() or number < 1:
        errors[field] = "Expected attendance must be a positive whole number."
        return None
    return number


def _text(value, field, errors):
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        errors[field] = "Location must be text."
        return None
    value = value.strip()
    if len(value) > 100:
        errors[field] = "Location must be 100 characters or fewer."
        return None
    return value or None


def _choices(values, allowed, field, errors):
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        errors[field] = "Choose one or more valid options."
        return []
    values = list(dict.fromkeys(value for value in values if value))
    unknown = sorted(set(values) - allowed)
    if unknown:
        errors[field] = "Unknown option: " + ", ".join(unknown) + "."
        return []
    return values


def _required_accessibility(value, field, errors):
    if value in (None, ""):
        return None
    if value == "true":
        return True
    errors[field] = "Accessibility must be either required or not specified."
    return None


def _parse_event_period(payload, filters, errors):
    fields = ("start_date", "end_date")
    values = {field: payload.get(field) for field in fields}
    if not any(values.values()):
        return
    if not all(values.values()):
        for field, value in values.items():
            if not value:
                errors[field] = "Enter both event start and end dates."
        return

    start_date = _date(values["start_date"], "start_date", errors)
    end_date = _date(values["end_date"], "end_date", errors)
    if errors:
        return

    filters["start_date"] = start_date
    filters["end_date"] = end_date
    if end_date < start_date:
        errors["end_date"] = "Event end date cannot be before the start date."


def _date(value, field, errors):
    if value in (None, ""):
        return None
    try:
        return datetime.strptime(value, "%d-%m-%Y").date()
    except (TypeError, ValueError):
        errors[field] = "Date must use DD-MM-YYYY."
        return None
