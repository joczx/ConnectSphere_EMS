"""Validation for an Event Organiser's proposed event changes."""

from datetime import datetime

from app.schemas import event as event_schema

PERMITTED_FIELDS = (
    "event_name",
    "description",
    "start_datetime",
    "end_datetime",
    "capacity_needed",
    "room_layout",
    "required_facilities",
    "need_wheelchair_accessibility",
    "need_blind_accessibility",
    "equipment_requirements",
)

REASON_REQUIRED_MESSAGE = "Please provide a reason for this change request"
BODY_FIELDS = frozenset({
    "reason", "proposed_values", "expected_event_updated_at",
    "confirm_critical",
})


def parse_submission(payload):
    """Return a database-ready submission and field-level errors."""
    if not isinstance(payload, dict):
        return {}, {"_body": "Expected a JSON object describing the change request."}

    errors = {}
    unknown = sorted(set(payload) - BODY_FIELDS)
    if unknown:
        errors["_body"] = f"Unrecognised field(s): {', '.join(unknown)}."

    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        errors["reason"] = REASON_REQUIRED_MESSAGE
    elif len(reason.strip()) > 2000:
        errors["reason"] = "The reason must be 2000 characters or fewer."

    proposed = payload.get("proposed_values")
    if not isinstance(proposed, dict):
        errors["proposed_values"] = "Proposed changes must be a JSON object."
        proposed = {}
    else:
        unexpected = sorted(set(proposed) - set(PERMITTED_FIELDS))
        if unexpected:
            errors["proposed_values"] = (
                "Only the event name, description, date, time, expected attendance, "
                "venue requirements, accessibility needs, and equipment requirements "
                "can be changed."
            )
        permitted = {key: value for key, value in proposed.items()
                     if key in PERMITTED_FIELDS}
        cleaned, field_errors = event_schema.parse_payload(permitted)
        errors.update(field_errors)
        proposed = cleaned

    expected = payload.get("expected_event_updated_at")
    if not isinstance(expected, str) or not expected.strip():
        errors["expected_event_updated_at"] = "Reload the event before submitting changes."
    else:
        try:
            parsed = datetime.fromisoformat(expected.strip().replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError
        except ValueError:
            errors["expected_event_updated_at"] = "Reload the event before submitting changes."

    confirm = payload.get("confirm_critical", False)
    if type(confirm) is not bool:
        errors["confirm_critical"] = "Confirmation must be true or false."

    if errors:
        return {}, errors

    return {
        "reason": reason.strip(),
        "proposed_values": proposed,
        "expected_event_updated_at": expected.strip(),
        "confirm_critical": confirm,
    }, {}

