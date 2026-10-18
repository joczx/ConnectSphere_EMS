"""HTTP routes for the "Create and Submit Event Request" user story."""

from flask import Blueprint, jsonify, request

from app.schemas.event_request import clean_user_id
from app.schemas import event_request_review as review_schema
from app.services.event_request_review_service import (
    list_reviews,
    review_event_request,
)
from app.services.event_request_service import (
    EventRequestError,
    create_event_request,
    delete_draft,
    list_event_requests,
)
from app.services.event_request_workflow import (
    edit as edit_event_request,
    list_amendments,
    send_for_review,
)
from app.services.event_store import (
    StoreError,
    authenticated_token,
    supabase_request,
)

from app.services.event_status_service import lifecycle_call
from app.services.event_service import EventError
from app.services.authorization import (
    current_user,
    has_role,
    require_event_request_access,
    require_event_request_owner,
    require_roles,
)


event_requests_bp = Blueprint(
    "event_requests", __name__, url_prefix="/api/event-requests"
)


@event_requests_bp.after_request
def prevent_caching(response):
    response.headers["Cache-Control"] = "no-store"
    return response


# Confirmation shown to the Event Coordinator once the outcome is recorded.
MESSAGES = {
    review_schema.OUTCOME_APPROVED: "Event request approved. The Event Organiser has been notified.",
    review_schema.OUTCOME_REJECTED: "Event request rejected. The Event Organiser has been notified.",
    review_schema.OUTCOME_CLARIFICATION: "Clarification requested. The Event Organiser has been notified.",
}

DECISION_MESSAGES = {
    review_schema.OUTCOME_APPROVED: "Event request approved.",
    review_schema.OUTCOME_REJECTED: "Event request rejected.",
    review_schema.OUTCOME_CLARIFICATION: "Clarification requested.",
}


def _review_confirmation(outcome, event_request, notifications):
    """Only claim notification when the Organiser's row was actually stored."""
    organiser_id = event_request.get("event_organiser_id")
    organiser_notified = organiser_id is not None and any(
        item.get("recipient_id") == organiser_id for item in notifications
    )
    if organiser_notified:
        return MESSAGES[outcome]
    return DECISION_MESSAGES[outcome] + " The Event Organiser could not be notified."


@event_requests_bp.errorhandler(EventRequestError)
def handle_event_request_error(error):
    return jsonify(error.to_dict()), error.status_code


@event_requests_bp.errorhandler(StoreError)
def handle_store_error(error):
    if (
        error.code == "PGRST202"
        and request.endpoint in {
            "event_requests.unassigned",
            "event_requests.assign_coordinator",
        }
    ):
        return jsonify(
            error=(
                "Event Coordinator assignment is not available in Supabase yet. "
                "Apply supabase/029_event_coordinator_assignment.sql and reload "
                "the Supabase API schema cache."
            )
        ), 503
    return jsonify(error.to_dict()), error.status


def _assignment_result(result):
    if isinstance(result, dict) and result.get("error"):
        return jsonify(error=result["error"]), result.get("status", 500)
    return jsonify(result)


@event_requests_bp.get("/unassigned")
def unassigned():
    identity = require_roles("Event Coordinator Lead")
    result = supabase_request(
        "/rest/v1/rpc/event_request_assignment_queue",
        token=identity.token,
        payload={},
        method="POST",
    )
    return _assignment_result(result)


@event_requests_bp.post("/<int:event_request_id>/assign-coordinator")
def assign_coordinator(event_request_id):
    identity = require_roles("Event Coordinator Lead")
    payload = request.get_json(silent=True)
    coordinator_id = (
        clean_user_id(payload.get("coordinator_id"))
        if isinstance(payload, dict)
        else None
    )
    if coordinator_id is None:
        return jsonify(error="Choose a valid Event Coordinator."), 400

    result = supabase_request(
        "/rest/v1/rpc/assign_event_request_coordinator",
        token=identity.token,
        payload={
            "p_event_request_id": event_request_id,
            "p_coordinator_id": coordinator_id,
        },
        method="POST",
    )
    return _assignment_result(result)


@event_requests_bp.errorhandler(EventError)
def handle_lifecycle_error(error):
    return jsonify(error.to_dict()), error.status


@event_requests_bp.post('/<int:event_request_id>/cancel')
def cancel(event_request_id):
    identity, _ = require_event_request_owner(event_request_id)
    return jsonify(lifecycle_call('cancel_event_request', identity.token, {'p_request_id': event_request_id}))


@event_requests_bp.post("")
def create():
    """Create an event request.

    Send "save_as_draft": true to keep an incomplete request as a draft;
    otherwise the request is validated in full and submitted for review.
    """
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        raise EventRequestError("Send the event request details as JSON.")

    identity = require_roles("Event Organiser")
    payload = dict(payload)
    payload["event_organiser_id"] = identity.user_id
    save_as_draft = payload.pop("save_as_draft", False)
    if not isinstance(save_as_draft, bool):
        raise EventRequestError("save_as_draft must be true or false.")
    row = create_event_request(payload, submit=not save_as_draft)

    message = (
        "Draft event request saved."
        if save_as_draft
        else "Event request submitted successfully."
    )

    return jsonify({"message": message, "event_request": row}), 201


@event_requests_bp.get("")
def index():
    """List requests owned by the Organiser or assigned to the Coordinator.

    Filter with ?status=draft to show only drafts, which is what keeps them
    distinguishable from requests already submitted for review.
    """
    raw_organiser_id = request.args.get("event_organiser_id")
    identity = current_user()
    status = request.args.get("status")

    if has_role(identity, "Event Organiser"):
        if raw_organiser_id and clean_user_id(raw_organiser_id) != identity.user_id:
            return jsonify(error="You can only view your own event requests."), 403
        rows = list_event_requests(identity.user_id, status)
    elif has_role(identity, "Event Coordinator"):
        rows = list_event_requests(
            status=status or ("submitted", "planning", "rejected"),
            event_coordinator_id=identity.user_id,
        )
    else:
        require_roles("Event Organiser", "Event Coordinator")

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

    require_event_request_owner(event_request_id)
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


@event_requests_bp.delete("/<int:event_request_id>")
def delete(event_request_id):
    """Delete an unsubmitted draft."""
    require_event_request_owner(event_request_id)
    delete_draft(event_request_id)

    return jsonify({"message": "Draft event request deleted."})


@event_requests_bp.get("/<int:event_request_id>")
def read(event_request_id):
    """Return one event request so the Organiser can review it before submitting."""
    _, row = require_event_request_access(event_request_id)
    return jsonify(row)


@event_requests_bp.post("/<int:event_request_id>/submit")
def submit(event_request_id):
    """Send a request to the Event Coordinator.

    Submits a draft, or resubmits a request that has been amended in response
    to a request for clarification.
    """
    require_event_request_owner(event_request_id)
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
    require_event_request_owner(event_request_id)
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

    # Who is reviewing comes from the verified session, never from the body.
    identity = require_roles("Event Coordinator")

    event_request, recorded, notifications = review_event_request(
        event_request_id, payload, identity.user_id
    )

    return jsonify(
        {
            "message": _review_confirmation(
                recorded["outcome"], event_request, notifications
            ),
            "event_request": event_request,
            "review": recorded,
            "notified": [n["recipient_id"] for n in notifications],
        }
    )


@event_requests_bp.get("/<int:event_request_id>/reviews")
def reviews(event_request_id):
    """Return the review history, so the outcome is visible to those involved."""
    require_event_request_access(event_request_id)
    rows = list_reviews(event_request_id)

    return jsonify({"count": len(rows), "reviews": rows})
