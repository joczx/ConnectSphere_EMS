"""Reading and editing an event during planning.

Backs the "View Event Information" and "Update Event Information" user stories.
Queries go through event_store.supabase_request with the caller's own access
token, so row level security decides what they may see and change.
"""

import logging

from app.schemas import event as schema
from app.services.event_store import StoreError, supabase_request

logger = logging.getLogger(__name__)


class EventError(Exception):
    def __init__(self, message, status=400, errors=None, critical=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.errors = errors
        # The critical fields awaiting confirmation, so the client can name
        # them in the warning rather than saying "something important".
        self.critical = critical

    def to_dict(self):
        body = {"error": self.message}
        if self.errors:
            body["errors"] = self.errors
        if self.critical:
            body["critical_fields"] = self.critical
        return body


def load_event(event_id, token):
    """Return the full event row, or raise 404 if it is not visible."""
    rows = supabase_request(
        f"/rest/v1/{schema.TABLE_NAME}?select=*&event_id=eq.{event_id}",
        token=token,
    )
    if not rows:
        raise EventError("Event not found or access unavailable.", status=404)
    return rows[0]


def update_event(event_id, payload, token, confirm_critical=False):
    """Apply an edit to an event in planning.

    Returns (row, activity). `activity` is the history entry written, or None
    when nothing actually changed.

    A critical change is refused unless `confirm_critical` is set. The warning
    modal is a UI affordance, but the rule it enforces lives here: a client
    that skips the modal, or does not have one, still cannot save a critical
    change without saying it means to.
    """
    existing = load_event(event_id, token)

    if not schema.is_editable(existing):
        raise EventError(schema.why_not_editable(existing), status=409)

    record, errors = schema.parse_payload(payload)
    if errors:
        raise EventError(
            "The changes could not be saved because some details are invalid.",
            errors=errors,
        )

    timing = schema.check_timing(existing, record)
    if timing:
        raise EventError(
            "The changes could not be saved because some details are invalid.",
            errors=timing,
        )

    changes = schema.diff(existing, record)
    if not changes:
        return existing, None

    change_type = schema.classify(changes)

    if change_type == schema.CHANGE_CRITICAL and not confirm_critical:
        raise EventError(
            "These changes may affect arrangements already made for this "
            "event. Please review and confirm them before saving.",
            status=409,
            critical=schema.describe_critical(changes),
        )

    updated = supabase_request(
        f"/rest/v1/{schema.TABLE_NAME}?event_id=eq.{event_id}",
        token=token,
        payload=record,
        method="PATCH",
    )
    if not updated:
        raise EventError(
            "You do not have permission to change this event. Please contact "
            "an administrator.",
            status=403,
        )

    row = updated[0] if isinstance(updated, list) else updated
    activity = _record_activity(event_id, change_type, changes, token)

    return row, activity


def list_activity(event_id, token):
    """Return an event's Activity History, newest first."""
    return supabase_request(
        f"/rest/v1/{schema.ACTIVITY_TABLE}"
        f"?select=*&event_id=eq.{event_id}&order=created_at.desc",
        token=token,
    )


def _record_activity(event_id, change_type, changes, token):
    """Write the history entry. Best effort: the edit is already saved.

    Losing a history row is bad, but undoing a change the user was told had
    been saved is worse, so a failure here is logged rather than raised.
    """
    record = {
        "event_id": event_id,
        "changed_by": _current_user_id(token),
        "change_type": change_type,
        "changes": changes,
    }

    try:
        rows = supabase_request(
            f"/rest/v1/{schema.ACTIVITY_TABLE}",
            token=token,
            payload=record,
            method="POST",
        )
    except StoreError:
        logger.exception("Could not record activity for event %s", event_id)
        return None

    return rows[0] if isinstance(rows, list) and rows else None


def _current_user_id(token):
    try:
        user = supabase_request("/auth/v1/user", token=token)
    except StoreError:
        logger.warning("Could not identify the user making the change")
        return None
    return user.get("id") if isinstance(user, dict) else None
