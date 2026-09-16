"""Editing and submitting an event request, wherever it is in its lifecycle.

A request can be worked on while it is still a draft, and after an Event
Coordinator sends it back, either by asking for clarification or by rejecting
it (the customer confirmed rejection "is not necessarily final"). Everywhere
else it is read only, because the customer was explicit that an Organiser
"cannot directly edit after submission; must request via Coordinator".

"Awaiting clarification" is deliberately not a status of its own - the
customer said clarification "can be a sub-state of under_review" - so it is
derived from the most recent review.
"""

import logging

from app.schemas import event_request as schema
from app.schemas import event_request_review as review_schema
from app.services import event_request_service as requests
from app.services import event_request_review_service as reviews
from app.services import notification_service
from app.services.event_request_service import EventRequestError
from app.services.supabase_client import get_supabase

logger = logging.getLogger(__name__)

AMENDMENT_TABLE = "event_request_amendment"


def edit(event_request_id, payload):
    """Edit a draft, or amend a request the Coordinator has queried.

    Returns (row, amendment). `amendment` is None for an ordinary draft edit.
    """
    existing = requests.require_event_request(event_request_id)
    payload, note = _split_note(payload)

    if existing.get("status") == schema.STATUS_DRAFT:
        row, _ = requests.apply_edit(existing, payload)
        return row, None

    if not can_amend(existing):
        raise EventRequestError(_why_not_editable(existing), status_code=409)

    row, changes = requests.apply_edit(existing, payload)
    amendment = _record_amendment(existing, changes, note)

    return row, amendment


def send_for_review(event_request_id):
    """Submit a draft, or resubmit a request after amending it."""
    existing = requests.require_event_request(event_request_id)
    status = existing.get("status")

    is_resubmission = status != schema.STATUS_DRAFT

    if is_resubmission and not can_amend(existing):
        raise EventRequestError(_why_not_submittable(existing), status_code=409)

    errors = requests.find_blocking_errors(existing)
    if errors:
        raise EventRequestError(
            "The event request could not be submitted because some details "
            "are missing or invalid.",
            errors=errors,
        )

    row = requests.mark_submitted(event_request_id)

    notified = _notify_resubmission(row) if is_resubmission else []

    return row, is_resubmission, notified


def can_amend(event_request):
    """True when a Coordinator has sent the request back to the Organiser.

    The status stays "rejected" while the Organiser amends it, and only becomes
    "submitted" again on resubmission.
    """
    return event_request.get("status") == schema.STATUS_REJECTED or is_awaiting_clarification(event_request)


def is_awaiting_clarification(event_request):
    """True when the latest review asked the Organiser for clarification."""
    if event_request.get("status") != schema.STATUS_UNDER_REVIEW:
        return False

    latest = reviews.latest_review(event_request["event_request_id"])

    return latest is not None and latest["outcome"] == review_schema.OUTCOME_CLARIFICATION


def list_amendments(event_request_id):
    """Return the amendment history for a request, newest first."""
    requests.require_event_request(event_request_id)

    def query(table):
        return (
            table.select("*")
            .eq("event_request_id", event_request_id)
            .order("created_at", desc=True)
            .execute()
        )

    return reviews.execute_on(AMENDMENT_TABLE, query, action="list the amendments")


def _split_note(payload):
    """Take the Organiser's reply out of the payload; it is not a request field."""
    if not isinstance(payload, dict):
        return payload, None

    remaining = dict(payload)
    note = remaining.pop("note", None)

    if note is not None and not isinstance(note, str):
        raise EventRequestError(
            "The changes could not be saved because some details are invalid.",
            errors={"note": "The note must be text."},
        )

    return remaining, (note.strip() or None) if isinstance(note, str) else None


def _record_amendment(existing, changes, note):
    # The Organiser who owns the request is the one amending it, so this is
    # taken from the record rather than trusted from the request body.
    record = {
        "event_request_id": existing["event_request_id"],
        "amended_by": existing["event_organiser_id"],
        "changes": changes,
        "note": note,
    }

    rows = reviews.execute_on(
        AMENDMENT_TABLE,
        lambda table: table.insert(record).execute(),
        action="record the amendment",
    )

    return rows[0] if rows else None


def _notify_resubmission(event_request):
    """Tell the Coordinator who sent the request back that a reply has arrived.

    Best effort, as elsewhere: the resubmission is already recorded, so a
    failed notification is logged rather than raised.
    """
    name = event_request.get("event_name") or "an event request"
    message = f"The Event Organiser has amended and resubmitted '{name}'."

    recipients = []
    for review in reviews.list_reviews(event_request["event_request_id"]):
        if review["outcome"] in (review_schema.OUTCOME_CLARIFICATION, review_schema.OUTCOME_REJECTED):
            recipients.append(review["reviewer_id"])

    assigned = event_request.get("event_coordinator_id")
    if assigned is not None:
        recipients.append(assigned)

    pending = []
    seen = set()
    for recipient_id in recipients:
        if recipient_id not in seen:
            seen.add(recipient_id)
            pending.append(
                notification_service.build(
                    recipient_id,
                    event_request["event_request_id"],
                    "event_request_resubmitted",
                    message,
                )
            )

    try:
        return notification_service.deliver(get_supabase(), pending)
    except Exception:  # noqa: BLE001 - never undo a recorded resubmission
        logger.exception(
            "Could not notify coordinators about event request %s",
            event_request["event_request_id"],
        )
        return []


def _why_not_editable(existing):
    status = existing.get("status")

    if status == schema.STATUS_UNDER_REVIEW:
        return (
            "This event request is being reviewed. It can only be amended "
            "once the Event Coordinator asks for clarification."
        )

    return (
        f"This event request has been {status} and can no longer be edited. "
        "Changes must go through the Event Coordinator."
    )


def _why_not_submittable(existing):
    status = existing.get("status")

    if status == schema.STATUS_UNDER_REVIEW:
        return (
            "This event request is already with the Event Coordinator. There "
            "is nothing to resubmit until clarification is requested."
        )

    return (
        f"This event request has been {status} and cannot be submitted again."
    )
