"""Coordinator operations for reviewing event change requests."""

from app.schemas.event_change_request_review import parse_decision
from app.services.event_change_request_service import (
    EventChangeRequestError,
    call_change_request_rpc,
)


VALID_STATUSES = frozenset({"pending_review", "approved", "rejected"})


def list_for_coordinator(token, *, status=None):
    """List requests for events assigned to the signed-in coordinator."""
    if status is not None and status not in VALID_STATUSES:
        raise EventChangeRequestError("Choose a valid change request status.", errors={"status": "Invalid status."})
    return call_change_request_rpc("event_change_requests_for_coordinator", token, {
        "p_status": status,
    }).get("change_requests", [])


def get_for_review(request_id, token):
    """Fetch one authorized request, its field diff, importance, and impacts."""
    return call_change_request_rpc("event_change_request_for_review", token, {
        "p_request_id": int(request_id),
    })


def decide(request_id, payload, token):
    """Validate and atomically approve or reject a pending important request."""
    decision, errors = parse_decision(payload)
    if errors:
        raise EventChangeRequestError("Check the review decision.", errors=errors)
    return call_change_request_rpc("review_event_change_request", token, {
        "p_request_id": int(request_id),
        "p_decision": decision["decision"],
        "p_reason": decision["reason"],
    })

