"""Business logic for Event Coordinator review of event requests."""

import logging

from app.schemas import event_request as request_schema
from app.schemas import event_request_review as review_schema
from app.services import db, notification_service
from app.services.event_request_service import EventRequestError, get_event_request
from app.services.supabase_client import get_supabase

logger = logging.getLogger(__name__)


def review_event_request(event_request_id, payload):
    """Record an Event Coordinator's decision and notify the people involved.

    Returns (event_request, review, notifications).
    """
    record, errors = review_schema.parse_payload(payload)

    if errors:
        raise EventRequestError(
            "The review could not be recorded because some details are "
            "missing or invalid.",
            errors=errors,
        )

    existing = get_event_request(event_request_id)

    if existing is None:
        raise EventRequestError(
            f"No event request found with id {event_request_id}.", status_code=404
        )

    status = existing.get("status")

    if status not in review_schema.REVIEWABLE_STATUSES:
        raise EventRequestError(_why_not_reviewable(status), status_code=409)

    review = _record_review(event_request_id, record)

    updated = _apply_outcome(event_request_id, record["outcome"])

    notifications = _notify(updated or existing, record)

    return updated or existing, review, notifications


def list_reviews(event_request_id):
    """Return the review history for a request, newest first.

    This is what makes the outcome "visible to the relevant users".
    """
    if get_event_request(event_request_id) is None:
        raise EventRequestError(
            f"No event request found with id {event_request_id}.", status_code=404
        )

    def query(table):
        return (
            table.select("*")
            .eq("event_request_id", event_request_id)
            .order("created_at", desc=True)
            .execute()
        )

    return execute_on(review_schema.REVIEW_TABLE, query, action="list the reviews")


def _record_review(event_request_id, record):
    rows = execute_on(
        review_schema.REVIEW_TABLE,
        lambda table: table.insert({**record, "event_request_id": event_request_id}).execute(),
        action="record the review",
    )

    if not rows:
        raise EventRequestError(
            "The review could not be recorded. Please try again.", status_code=502
        )

    return rows[0]


def _apply_outcome(event_request_id, outcome):
    new_status = review_schema.OUTCOME_TO_STATUS[outcome]

    rows = execute_on(
        request_schema.TABLE_NAME,
        lambda table: table.update({"status": new_status, "updated_at": db.utc_now()})
        .eq("event_request_id", event_request_id)
        .execute(),
        action="update the event request status",
    )

    return rows[0] if rows else None


def _notify(event_request, record):
    """Tell the Organiser the outcome, and confirm it back to the Coordinator.

    Best effort: the decision is already recorded, so a notification failure is
    logged rather than raised. Losing a message is better than telling the
    Coordinator their approval failed when it did not.
    """
    organiser_text, reviewer_text = review_schema.describe(
        record["outcome"], event_request.get("event_name")
    )

    notification_type = f"event_request_{record['outcome']}"
    event_request_id = event_request.get("event_request_id")

    pending = []
    seen = set()

    # The Organiser, who is waiting on the outcome.
    organiser_id = event_request.get("event_organiser_id")
    if organiser_id is not None:
        pending.append(
            notification_service.build(
                organiser_id, event_request_id, notification_type, organiser_text
            )
        )
        seen.add(organiser_id)

    # The Coordinator who made the decision, and the one assigned to the event
    # if that is somebody else.
    for coordinator_id in (record["reviewer_id"], event_request.get("event_coordinator_id")):
        if coordinator_id is not None and coordinator_id not in seen:
            pending.append(
                notification_service.build(
                    coordinator_id, event_request_id, notification_type, reviewer_text
                )
            )
            seen.add(coordinator_id)

    try:
        return notification_service.deliver(get_supabase(), pending)
    except Exception:  # noqa: BLE001 - never undo a recorded decision
        logger.exception(
            "Could not notify users about event request %s", event_request_id
        )
        return []


def _why_not_reviewable(status):
    if status == request_schema.STATUS_DRAFT:
        return (
            "This event request is still a draft. It can only be reviewed "
            "once the Event Organiser submits it."
        )

    return (
        f"This event request has already been {status} and cannot be "
        "reviewed again."
    )


def latest_review(event_request_id):
    """The most recent review of a request, or None if it has never been reviewed."""
    def query(table):
        return (
            table.select("*")
            .eq("event_request_id", event_request_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

    rows = execute_on(review_schema.REVIEW_TABLE, query, action="read the latest review")

    return rows[0] if rows else None


def execute_on(table_name, operation, action):
    """Run a Supabase call against a named table, mapping errors to messages."""
    return db.run(table_name, operation, action, _translate_review_error)


def _translate_review_error(exc, action):
    code = getattr(exc, "code", None)
    detail = str(getattr(exc, "message", None) or exc)

    if code == "23503":
        return EventRequestError(
            "The reviewing Event Coordinator does not match a known "
            "ConnectSphere user.",
            errors={"reviewer_id": detail},
        )

    # The database enforces the same rule as the schema layer, in case a
    # review is written by something other than this API.
    if code == "23514" and "reason_required" in detail:
        return EventRequestError(
            "A comment is required when rejecting a request or asking for "
            "clarification.",
            errors={"comments": detail},
        )

    return EventRequestError(
        f"Could not {action} because the database is unavailable. Please try again.",
        status_code=502,
    )
