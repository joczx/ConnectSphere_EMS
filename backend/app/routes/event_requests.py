"""HTTP routes for the "Create and Submit Event Request" user story."""

from flask import Blueprint, jsonify, request

from app.schemas import event_request_review as review_schema
from app.services.event_request_review_service import (
    list_reviews,
    review_event_request,
)
from app.services.event_request_service import (
    EventRequestError,
    create_event_request,
    get_event_request,
    list_event_requests,
)
from app.services.event_request_workflow import (
    edit as edit_event_request,
    list_amendments,
    send_for_review,
)

event_requests_bp = Blueprint(
    "event_requests", __name__, url_prefix="/api/event-requests"
)

# Confirmation shown to the Event Coordinator once the outcome is recorded.
MESSAGES = {
    review_schema.OUTCOME_APPROVED: "Event request approved. The Event Organiser has been notified.",
    review_schema.OUTCOME_REJECTED: "Event request rejected. The Event Organiser has been notified.",
    review_schema.OUTCOME_CLARIFICATION: "Clarification requested. The Event Organiser has been notified.",
}


@event_requests_bp.errorhandler(EventRequestError)
def handle_event_request_error(error):
    return jsonify(error.to_dict()), error.status_code


@event_requests_bp.post("")
def create():
    """Create an event request.

    Send "save_as_draft": true to keep an incomplete request as a draft;
    otherwise the request is validated in full and submitted for review.
    """
    payload = request.get_json(silent=True)

    if payload is None:
        raise EventRequestError("Send the event request details as JSON.")

    save_as_draft = bool(payload.pop("save_as_draft", False))
    row = create_event_request(payload, submit=not save_as_draft)

    message = (
        "Draft event request saved."
        if save_as_draft
        else "Event request submitted successfully."
    )

    return jsonify({"message": message, "event_request": row}), 201


@event_requests_bp.get("")
def index():
    """List an Organiser's requests so they can return to an unfinished draft.

    Filter with ?status=draft to show only drafts, which is what keeps them
    distinguishable from requests already submitted for review.
    """
    # TODO: take the organiser from the authenticated session once the User
    # Authorisation story lands, rather than trusting a query parameter.
    organiser_id = request.args.get("event_organiser_id", type=int)
    status = request.args.get("status")

    rows = list_event_requests(organiser_id, status)

    return jsonify({"count": len(rows), "event_requests": rows})


@event_requests_bp.patch("/<int:event_request_id>")
def edit(event_request_id):
    """Continue editing a draft, or amend a request after a clarification request.

    Only the fields included in the body are changed. Sending null for a field
    clears it, so an Organiser can undo something they filled in earlier. When
    amending, an optional "note" replies to the Coordinator's question.
    """
    payload = request.get_json(silent=True)

    if payload is None:
        raise EventRequestError("Send the fields you want to change as JSON.")

    row, amendment = edit_event_request(event_request_id, payload)

    body = {
        "message": (
            "Draft event request saved."
            if amendment is None
            else "Amendment saved. Resubmit the request when you are ready."
        ),
        "event_request": row,
    }

    if amendment is not None:
        body["amendment"] = amendment

    return jsonify(body)


@event_requests_bp.get("/<int:event_request_id>")
def read(event_request_id):
    """Return one event request so the Organiser can review it before submitting."""
    row = get_event_request(event_request_id)

    if row is None:
        return jsonify({"error": f"No event request found with id {event_request_id}."}), 404

    return jsonify(row)


@event_requests_bp.post("/<int:event_request_id>/submit")
def submit(event_request_id):
    """Send a request to the Event Coordinator.

    Submits a draft, or resubmits a request that has been amended in response
    to a request for clarification.
    """
    row, was_resubmission, notified = send_for_review(event_request_id)

    return jsonify(
        {
            "message": (
                "Event request resubmitted successfully. The Event "
                "Coordinator has been notified."
                if was_resubmission
                else "Event request submitted successfully."
            ),
            "event_request": row,
            "notified": [n["recipient_id"] for n in notified],
        }
    )


@event_requests_bp.get("/<int:event_request_id>/amendments")
def amendments(event_request_id):
    """Return what the Organiser changed after each clarification request."""
    rows = list_amendments(event_request_id)

    return jsonify({"count": len(rows), "amendments": rows})


@event_requests_bp.post("/<int:event_request_id>/review")
def review(event_request_id):
    """Record an Event Coordinator's decision on a submitted request.

    One endpoint for all three outcomes, because approving, rejecting and
    asking for clarification are the same action with a different result.
    """
    payload = request.get_json(silent=True)

    if payload is None:
        raise EventRequestError("Send the review outcome and comments as JSON.")

    event_request, recorded, notifications = review_event_request(
        event_request_id, payload
    )

    return jsonify(
        {
            "message": MESSAGES[recorded["outcome"]],
            "event_request": event_request,
            "review": recorded,
            "notified": [n["recipient_id"] for n in notifications],
        }
    )


@event_requests_bp.get("/<int:event_request_id>/reviews")
def reviews(event_request_id):
    """Return the review history, so the outcome is visible to those involved."""
    rows = list_reviews(event_request_id)

    return jsonify({"count": len(rows), "reviews": rows})
