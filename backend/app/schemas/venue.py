"""Validation rules for creating venue catalogue records."""

from datetime import datetime

from app.schemas.venue_search import FACILITIES, ROOM_LAYOUTS

DAYS = (
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
)

CREATE_FIELDS = frozenset(
    {
        "venue_name", "capacity", "postal_code", "block_number", "street_name",
        "building_name", "unit_number", "wheelchair_accessible", "blind_accessible",
        "accessibility_notes", "facilities", "supported_room_layouts",
        "operating_hours", "default_setup_minutes", "default_turnaround_minutes",
    }
)


def parse_create(payload):
    """Return a clean venue record and field errors."""
    if not isinstance(payload, dict):
        return {}, {"form": "Send the venue details as a JSON object."}

    errors = {}
    unknown = sorted(set(payload) - CREATE_FIELDS)
    if unknown:
        errors[unknown[0]] = "This field cannot be set when creating a venue."

    record = {
        "venue_name": _text(payload.get("venue_name"), "venue_name", errors, required=True, maximum=150),
        "capacity": _integer(payload.get("capacity"), "capacity", errors, minimum=1),
        "postal_code": _postal_code(payload.get("postal_code"), errors),
        "block_number": _text(payload.get("block_number"), "block_number", errors, required=True, maximum=50),
        "street_name": _text(payload.get("street_name"), "street_name", errors, required=True, maximum=150),
        "building_name": _text(payload.get("building_name"), "building_name", errors, maximum=150),
        "unit_number": _text(payload.get("unit_number"), "unit_number", errors, maximum=50),
        "wheelchair_accessible": _boolean(payload.get("wheelchair_accessible"), "wheelchair_accessible", errors),
        "blind_accessible": _boolean(payload.get("blind_accessible"), "blind_accessible", errors),
        "accessibility_notes": _text(payload.get("accessibility_notes"), "accessibility_notes", errors, maximum=1000),
        "facilities": _choices(payload.get("facilities"), FACILITIES, "facilities", errors),
        "supported_room_layouts": _choices(
            payload.get("supported_room_layouts"), ROOM_LAYOUTS, "supported_room_layouts", errors
        ),
        "operating_hours": _operating_hours(payload.get("operating_hours"), errors),
        "default_setup_minutes": _integer(
            payload.get("default_setup_minutes"), "default_setup_minutes", errors, minimum=0
        ),
        "default_turnaround_minutes": _integer(
            payload.get("default_turnaround_minutes"), "default_turnaround_minutes", errors, minimum=0
        ),
    }

    return record, errors


def _text(value, field, errors, *, required=False, maximum=100):
    if value is None or value == "":
        if required:
            errors[field] = "This field is required."
        return None
    if not isinstance(value, str):
        errors[field] = "This field must be text."
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        if required:
            errors[field] = "This field is required."
        return None
    if len(cleaned) > maximum:
        errors[field] = f"This field must be {maximum} characters or fewer."
        return None
    return cleaned


def _integer(value, field, errors, *, minimum):
    if type(value) is not int or value < minimum:
        qualifier = "positive" if minimum == 1 else "zero or greater"
        errors[field] = f"This field must be a whole number that is {qualifier}."
        return None
    return value


def _postal_code(value, errors):
    cleaned = _text(value, "postal_code", errors, required=True, maximum=6)
    if cleaned is not None and (len(cleaned) != 6 or not cleaned.isdecimal()):
        errors["postal_code"] = "Postal code must contain exactly 6 digits."
        return None
    return cleaned


def _boolean(value, field, errors):
    if type(value) is not bool:
        errors[field] = "Choose whether this accessibility feature is available."
        return None
    return value


def _choices(value, allowed, field, errors):
    if not isinstance(value, list) or not value:
        errors[field] = "Choose at least one option."
        return []
    if not all(isinstance(item, str) for item in value):
        errors[field] = "Choose valid options."
        return []
    cleaned = list(dict.fromkeys(item.strip() for item in value if item.strip()))
    unknown = sorted(set(cleaned) - allowed)
    if unknown:
        errors[field] = "Unknown option: " + ", ".join(unknown) + "."
        return []
    if not cleaned:
        errors[field] = "Choose at least one option."
    return cleaned


def _operating_hours(value, errors):
    if not isinstance(value, dict):
        errors["operating_hours"] = "Enter operating hours for every day."
        return {}
    if set(value) != set(DAYS):
        errors["operating_hours"] = "Enter operating hours for all seven days."
        return {}

    cleaned = {}
    for day in DAYS:
        schedule = value.get(day)
        if not isinstance(schedule, dict):
            errors["operating_hours"] = f"Enter valid operating hours for {day.title()}."
            continue
        if schedule.get("closed") is True:
            cleaned[day] = {"closed": True}
            continue
        opening = _time(schedule.get("open"))
        closing = _time(schedule.get("close"))
        if opening is None or closing is None:
            errors["operating_hours"] = f"Enter opening and closing times for {day.title()}."
            continue
        if closing <= opening:
            errors["operating_hours"] = f"Closing time must be after opening time for {day.title()}."
            continue
        cleaned[day] = {"open": opening, "close": closing}

    return cleaned


def _time(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%H:%M").strftime("%H:%M")
    except ValueError:
        return None
