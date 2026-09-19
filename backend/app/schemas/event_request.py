"""Validation rules for event requests.

Backs the "Create and Submit Event Request" user story. Kept free of any
Flask or Supabase imports so the rules can be unit tested on their own.

Column names and enum values mirror the public.event_request table in
Supabase.
"""

import uuid
from datetime import datetime, timezone

TABLE_NAME = "event_request"

# public.request_status
STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_UNDER_REVIEW = "under_review"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
ALL_STATUSES = frozenset(
    {"draft", "submitted", "under_review", "approved", "rejected"}
)

# public.room_layout
ROOM_LAYOUTS = frozenset(
    {"theatre", "classroom", "boardroom", "u_shape", "banquet", "standing"}
)

# Fields an Event Organiser is allowed to set. Everything else on the table
# (the id, status, coordinator, and timestamps) is controlled by the system so
# that a client cannot, for example, submit a request as already approved.
WRITABLE_FIELDS = (
    "event_name",
    "purpose",
    "description",
    "event_organiser_id",
    "start_datetime",
    "end_datetime",
    "capacity_needed",
    "room_layout",
    "required_facilities",
    "need_wheelchair_accessibility",
    "need_blind_accessibility",
    "equipment_requirements",
    "registration_needs",
)

# Fields an equipment requirement may carry. "notes" holds the per-item
# technical requirements.
EQUIPMENT_ITEM_FIELDS = frozenset({"equipment_type", "quantity", "notes"})

# Must be filled in before a request may leave draft. For facilities and
# equipment, null means "not answered yet" and [] means "none needed", so an
# Organiser must answer but may answer none. The accessibility flags are not
# listed: they are NOT NULL booleans and always hold an answer.
MANDATORY_FOR_SUBMISSION = (
    "event_name",
    "purpose",
    "description",
    "start_datetime",
    "end_datetime",
    "capacity_needed",
    "room_layout",
    "required_facilities",
    "equipment_requirements",
    "registration_needs",
)

_LABELS = {
    "event_name": "Event name",
    "purpose": "Purpose",
    "description": "Description",
    "event_organiser_id": "Event organiser",
    "start_datetime": "Proposed start date and time",
    "end_datetime": "Proposed end date and time",
    "capacity_needed": "Expected attendance",
    "room_layout": "Room layout",
    "required_facilities": "Required facilities",
    "equipment_requirements": "Equipment requirements",
    "registration_needs": "Registration needs",
}


def parse_payload(payload):
    """Turn a JSON body into a database-ready record.

    Returns (record, errors). `errors` maps a field name to a message meant to
    be shown to the user; when it is non-empty the record must not be saved.
    Absent fields are simply left out of the record rather than nulled, so this
    is safe for saving a partially filled draft.
    """
    errors = {}

    if not isinstance(payload, dict):
        return {}, {"_body": "Expected a JSON object describing the event request."}

    unknown = sorted(set(payload) - set(WRITABLE_FIELDS))
    if unknown:
        errors["_body"] = f"Unrecognised field(s): {', '.join(unknown)}."

    record = {}

    for field in ("event_name", "purpose", "description"):
        if field in payload:
            if _is_cleared(payload[field]):
                record[field] = None
            elif isinstance(payload[field], str):
                record[field] = payload[field].strip()
            else:
                errors[field] = f"{_LABELS[field]} must be text."

    if "event_organiser_id" in payload:
        organiser_id = clean_user_id(payload["event_organiser_id"])
        if organiser_id is None:
            errors["event_organiser_id"] = (
                "Event organiser must be a user id (a UUID)."
            )
        else:
            record["event_organiser_id"] = organiser_id

    for field in ("start_datetime", "end_datetime"):
        if field in payload:
            moment, problem = _clean_datetime(payload[field])
            if problem:
                errors[field] = f"{_LABELS[field]}: {problem}"
            else:
                record[field] = moment

    if "capacity_needed" in payload:
        if _is_cleared(payload["capacity_needed"]):
            record["capacity_needed"] = None
        else:
            capacity = _clean_int(payload["capacity_needed"])
            if capacity is None:
                errors["capacity_needed"] = "Expected attendance must be a whole number."
            elif capacity < 1:
                errors["capacity_needed"] = "Expected attendance must be at least 1."
            else:
                record["capacity_needed"] = capacity

    if "room_layout" in payload:
        # Cleared means null, never "": room_layout is a PostgreSQL enum and an
        # empty string is not one of its values.
        if _is_cleared(payload["room_layout"]):
            record["room_layout"] = None
        elif not isinstance(payload["room_layout"], str):
            errors["room_layout"] = "Room layout must be text."
        elif payload["room_layout"].strip() not in ROOM_LAYOUTS:
            errors["room_layout"] = (
                "Room layout must be one of: " + ", ".join(sorted(ROOM_LAYOUTS)) + "."
            )
        else:
            record["room_layout"] = payload["room_layout"].strip()

    if "required_facilities" in payload:
        facilities, problem = _clean_facilities(payload["required_facilities"])
        if problem:
            errors["required_facilities"] = problem
        else:
            record["required_facilities"] = facilities

    for field in ("need_wheelchair_accessibility", "need_blind_accessibility"):
        if field in payload:
            if isinstance(payload[field], bool):
                record[field] = payload[field]
            else:
                errors[field] = "Must be true or false."

    if "equipment_requirements" in payload:
        equipment, problem = _clean_equipment(payload["equipment_requirements"])
        if problem:
            errors["equipment_requirements"] = problem
        else:
            record["equipment_requirements"] = equipment

    if "registration_needs" in payload:
        needs = payload["registration_needs"]
        if needs is None:
            record["registration_needs"] = None
        elif isinstance(needs, str):
            # Blank is stored as null: the event simply needs no registration.
            record["registration_needs"] = needs.strip() or None
        else:
            errors["registration_needs"] = "Registration needs must be text."

    if not errors:
        errors.update(check_timing(record))

    return record, errors


def diff(existing, record):
    """What an edit actually changes, as {field: {from, to}}.

    Recorded before the update is written, because the previous value is lost
    the moment the row changes. Fields that are set to the value they already
    hold are not a change.
    """
    return {
        field: {"from": existing.get(field), "to": value}
        for field, value in record.items()
        if existing.get(field) != value
    }


def find_missing(record):
    """Return errors for mandatory fields that are still blank."""
    errors = {}

    for field in MANDATORY_FOR_SUBMISSION:
        value = record.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors[field] = f"{_LABELS[field]} is required before submitting."

    if record.get("event_organiser_id") is None:
        errors["event_organiser_id"] = "Event organiser is required before submitting."

    return errors


def check_timing(record, now=None):
    """Return errors for date and time rules that span more than one field.

    Accepts either a freshly parsed record or a row read back from Supabase,
    where the timestamps arrive as ISO 8601 strings.
    """
    errors = {}

    start, start_problem = _clean_datetime(record.get("start_datetime"))
    end, end_problem = _clean_datetime(record.get("end_datetime"))

    # A malformed value is reported by parse_payload; nothing to compare here.
    if start_problem or end_problem or start is None or end is None:
        return errors

    if end <= start:
        errors["end_datetime"] = (
            "The event must end after it starts."
        )

    if _to_datetime(start) <= (now or datetime.now(timezone.utc)):
        errors["start_datetime"] = (
            "The event must start in the future."
        )

    return errors


def clean_user_id(value):
    """Return a canonical user id string, or None if it is not a valid one.

    Users are managed by Supabase Auth, so a user id is a UUID rather than a
    number. Normalising here means a caller may send any accepted UUID spelling
    (upper case, or wrapped in braces) and the stored value is still canonical.
    """
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return str(uuid.UUID(value.strip()))
    except ValueError:
        return None


def _is_cleared(value):
    """True when the caller is emptying a field rather than setting one.

    An Organiser editing a draft may remove something they filled in earlier,
    so null and an all-whitespace string both mean "leave this blank".
    """
    return value is None or (isinstance(value, str) and not value.strip())


def _clean_int(value):
    # bool is a subclass of int; True should not pass as an id or a headcount.
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def _clean_datetime(value):
    """Return (ISO 8601 UTC string, problem). Exactly one is ever set."""
    if value is None:
        return None, None

    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        if not value.strip():
            return None, None
        try:
            moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None, (
                "must be an ISO 8601 date and time, "
                "for example 2026-10-01T09:00:00+08:00."
            )
    else:
        return None, "must be an ISO 8601 date and time."

    if moment.tzinfo is None:
        return None, (
            "must include a timezone offset, for example +08:00, so the time "
            "is not ambiguous."
        )

    return moment.astimezone(timezone.utc).isoformat(), None


def _to_datetime(iso_string):
    return datetime.fromisoformat(iso_string)


def _clean_facilities(value):
    if value is None:
        return None, None
    if not isinstance(value, list):
        return None, "Required facilities must be a list."

    facilities = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None, "Each required facility must be a non-empty name."
        facilities.append(item.strip())

    duplicates = len(facilities) != len(set(facilities))
    if duplicates:
        return None, "Required facilities must not repeat the same facility."

    return facilities, None


def _clean_equipment(value):
    """Return (list of equipment items, problem). Exactly one is ever set.

    An empty list is valid and means the event needs no equipment; None means
    the question has not been answered yet.
    """
    if value is None:
        return None, None
    if not isinstance(value, list):
        return None, (
            "Equipment requirements must be a list, for example "
            '[{"equipment_type": "projector", "quantity": 2}].'
        )

    items = []
    seen = set()

    for position, raw in enumerate(value, start=1):
        if not isinstance(raw, dict):
            return None, (
                f"Item {position}: each equipment requirement must be an "
                "object with an equipment_type and a quantity."
            )

        unknown = sorted(set(raw) - EQUIPMENT_ITEM_FIELDS)
        if unknown:
            return None, f"Item {position}: unrecognised field(s): {', '.join(unknown)}."

        equipment_type = raw.get("equipment_type")
        if not isinstance(equipment_type, str) or not equipment_type.strip():
            return None, f"Item {position}: equipment type is required."
        equipment_type = equipment_type.strip()

        # Two lines for the same thing should be one line with a larger
        # quantity, otherwise the totals are ambiguous downstream.
        if equipment_type.casefold() in seen:
            return None, (
                f"Item {position}: {equipment_type} is listed more than once. "
                "Combine them into a single quantity."
            )
        seen.add(equipment_type.casefold())

        quantity = _clean_int(raw.get("quantity"))
        if quantity is None:
            return None, f"Item {position}: quantity must be a whole number."
        if quantity < 1:
            return None, f"Item {position}: quantity must be at least 1."

        notes = raw.get("notes")
        if notes is not None and not isinstance(notes, str):
            return None, f"Item {position}: notes must be text."

        items.append(
            {
                "equipment_type": equipment_type,
                "quantity": quantity,
                "notes": notes.strip() or None if isinstance(notes, str) else None,
            }
        )

    return items, None
