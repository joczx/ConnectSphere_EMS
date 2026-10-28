"""Business logic for Event Coordinator review of event requests."""

from app.schemas import event_request as request_schema
from app.schemas import event_request_review as review_schema
from app.services import db
from app.services.event_request_service import EventRequestError, get_event_request


def review_event_request(event_request_id, payload, reviewer_id=None):
    """Record an Event Coordinator's decision.

    `reviewer_id` is the signed-in user, taken from the verified session by the
    route rather than from the request body.

    Returns (event_request, review).
    """
    record, errors = review_schema.parse_payload(payload, reviewer_id)

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

    # A request is received by one Event Coordinator. Row level security keeps
    # it out of anyone else's listing, but a request id is guessable, so the
    # rule is enforced here too rather than relying on not being found.
    assigned = existing.get("event_coordinator_id")

    # A request with no coordinator is a data fault, not an open invitation.
    # Treating it as one would let the Organiser decide their own request:
    # they can see it, so without this they would pass the check below.
    if assigned is None:
        raise EventRequestError(
            "This event request has no Event Coordinator assigned and cannot "
            "be reviewed yet. Please contact an administrator.",
            status_code=409,
        )

    if assigned != record["reviewer_id"]:
        raise EventRequestError(
            "This event request is assigned to another Event Coordinator and "
            "can only be reviewed by them.",
            status_code=403,
        )

    review = _record_review(event_request_id, record)

    updated = _apply_outcome(event_request_id, record["outcome"])

    return updated or existing, review


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
        .eq("status", request_schema.STATUS_SUBMITTED)
        .execute(),
        action="update the event request status",
    )

    if not rows:
        raise EventRequestError(
            "The request changed or you no longer have permission to review it. Reload it before continuing.",
            status_code=409,
        )
    return rows[0]



def _why_not_reviewable(status):
    if status == request_schema.STATUS_DRAFT:
        return (
            "This event request is still a draft. It can only be reviewed "
            "once the Event Organiser submits it."
        )

    # "has already been planning" does not read as English, and the Coordinator
    # needs to know the decision was already taken, not just that it is late.
    if status == request_schema.STATUS_PLANNING:
        return (
            "This event request has already been approved and is now in "
            "planning. It cannot be reviewed again."
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

    if code == "23514":
        return EventRequestError(
            "The request cannot advance from its current stage. Reload it and check the required conditions.",
            status_code=409,
        )
    if code == "42501":
        return EventRequestError("Only the assigned Event Coordinator can decide this request.", status_code=403)

    return EventRequestError(
        f"Could not {action} because the database is unavailable. Please try again.",
        status_code=502,
    )
