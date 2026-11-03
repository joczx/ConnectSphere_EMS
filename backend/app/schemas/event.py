"""Validation rules for editing an event during planning.

Backs the "Update Event Information" user story. Kept free of any Flask or
Supabase imports so the rules can be unit tested on their own.

public.events carries the same column names as public.event_request, because an
event is created from an approved request by copying them across. The field
level rules are therefore reused from event_request rather than restated here,
and what this module adds is the part that is specific to an event: which
fields are critical, and when an edit is allowed at all.
"""

from app.schemas import event_request as request_schema

TABLE_NAME = "events"
ACTIVITY_TABLE = "event_activity"

# "normal or less critical updates ... saved without additional approval".
NON_CRITICAL_FIELDS = (
    "event_name",
    "purpose",
    "description",
    "registration_needs",
)

# "critical fields which may affect existing arrangements". Changing any of
# these may invalidate a venue booking or an equipment reservation already made
# against the event, which is why the user is warned before they are saved.
CRITICAL_FIELDS = (
    "start_datetime",
    "end_datetime",
    "capacity_needed",
    "room_layout",
    "required_facilities",
    "need_wheelchair_accessibility",
    "need_blind_accessibility",
    "equipment_requirements",
)

WRITABLE_FIELDS = NON_CRITICAL_FIELDS + CRITICAL_FIELDS

# Everything else on the table is system controlled. The coordinator has its
# own endpoint and its own story; the organiser, status and timestamps are not
# the user's to set from here.
EDITABLE_STATUSES = frozenset({request_schema.STATUS_PLANNING})

CHANGE_EDIT = "edit"
CHANGE_CRITICAL = "critical_edit"

LABELS = {
    "event_name": "Event name",
    "purpose": "Purpose",
    "description": "Description",
    "registration_needs": "Registration needs",
    "start_datetime": "Proposed start date and time",
    "end_datetime": "Proposed end date and time",
    "capacity_needed": "Expected attendance",
    "room_layout": "Room layout",
    "required_facilities": "Venue requirements",
    "need_wheelchair_accessibility": "Wheelchair accessibility",
    "need_blind_accessibility": "Accessibility for blind attendees",
    "equipment_requirements": "Equipment requirements",
}


def parse_payload(payload):
    """Turn an edit body into a database-ready record.

    Returns (record, errors). Absent fields are left out rather than nulled, so
    a caller may send only what they changed.
    """
    if not isinstance(payload, dict):
        return {}, {"_body": "Expected a JSON object describing the event."}

    # Checked against this module's narrower list, so an attempt to set the
    # status or reassign the organiser through this endpoint is refused rather
    # than quietly accepted by the event_request rules.
    unknown = sorted(set(payload) - set(WRITABLE_FIELDS))
    if unknown:
        return {}, {"_body": f"Unrecognised field(s): {', '.join(unknown)}."}

    return request_schema.parse_payload(payload)


def check_timing(existing, record, now=None):
    """Date and time rules applied to the event as it will be after the edit.

    A partial edit is merged over the stored row first, so moving only the end
    date is still checked against the start date already saved.
    """
    merged = {**existing, **record}
    errors = request_schema.check_timing(merged, now=now)

    # "must start in the future" is a rule about proposing a date, not about
    # editing. An event already under way still needs its description fixed,
    # and that edit must not be blocked by a start date that has passed. The
    # rule applies only when this edit is what moves the start.
    if "start_datetime" not in record:
        errors.pop("start_datetime", None)

    return errors


def diff(existing, record):
    """What this edit actually changes, as {field: {from, to}}."""
    return request_schema.diff(existing, record)


def critical_changes(changes):
    """The critical fields among a diff, in the order they are presented."""
    return tuple(field for field in CRITICAL_FIELDS if field in changes)


def classify(changes):
    """The Activity History entry type an edit earns."""
    return CHANGE_CRITICAL if critical_changes(changes) else CHANGE_EDIT


def describe_critical(changes):
    """Readable field names for the warning the user is shown."""
    return [LABELS.get(field, field) for field in critical_changes(changes)]


def is_editable(event):
    """True while the event is in a phase that accepts edits.

    The customer was explicit that once an event is confirmed the arrangements
    and the coordinator cannot change, so editing stops at the end of planning.
    """
    return event.get("status") in EDITABLE_STATUSES


def why_not_editable(event):
    status = event.get("status")

    if status == request_schema.STATUS_CONFIRMED:
        return (
            "This event is confirmed. Its arrangements can no longer be "
            "changed. Contact the Event Coordinator if something must move."
        )

    if status == request_schema.STATUS_COMPLETED:
        return "This event is over and can no longer be edited."

    if status == request_schema.STATUS_CANCELLED:
        return "This event has been cancelled and can no longer be edited."

    return (
        f"This event is {status or 'in an unknown state'} and can only be "
        "edited during planning."
    )
