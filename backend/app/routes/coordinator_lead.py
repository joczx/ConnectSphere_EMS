"""Lead-only dashboard and coordinator reassignment routes."""

from flask import Blueprint, jsonify, request

from app.schemas.event_request import clean_user_id
from app.services.event_store import StoreError, supabase_request
from app.services.authorization import require_roles

coordinator_lead = Blueprint(
    "coordinator_lead", __name__, url_prefix="/api/coordinator-lead"
)


@coordinator_lead.after_request
def prevent_caching(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@coordinator_lead.errorhandler(StoreError)
def handle_store_error(error):
    if error.code == "PGRST202":
        return jsonify(
            error=(
                "The Coordinator Lead dashboard is not available in Supabase yet. "
                "Apply supabase/030_coordinator_lead_dashboard.sql and reload "
                "the Supabase API schema cache."
            )
        ), 503
    return jsonify(error=error.message), error.status


def _rpc_result(result):
    if isinstance(result, dict) and result.get("error"):
        return jsonify(error=result["error"]), result.get("status", 500)
    return jsonify(result)


def _coordinator_id(payload):
    if not isinstance(payload, dict):
        return None
    return clean_user_id(payload.get("coordinator_id"))


@coordinator_lead.get("/dashboard")
def dashboard():
    identity = require_roles("Event Coordinator Lead")
    result = supabase_request(
        "/rest/v1/rpc/event_coordinator_lead_dashboard",
        token=identity.token,
        payload={},
        method="POST",
    )
    return _rpc_result(result)


@coordinator_lead.patch("/event-requests/<int:event_request_id>/coordinator")
def reassign_event_request(event_request_id):
    identity = require_roles("Event Coordinator Lead")
    coordinator_id = _coordinator_id(request.get_json(silent=True))
    if coordinator_id is None:
        return jsonify(error="Choose a valid Event Coordinator."), 400

    result = supabase_request(
        "/rest/v1/rpc/reassign_submitted_request_coordinator",
        token=identity.token,
        payload={
            "p_event_request_id": event_request_id,
            "p_coordinator_id": coordinator_id,
        },
        method="POST",
    )
    return _rpc_result(result)


@coordinator_lead.patch("/events/<event_id>/coordinator")
def reassign_event(event_id):
    identity = require_roles("Event Coordinator Lead")
    try:
        event_id_value = int(event_id)
        if event_id_value <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify(error="Event not found or access unavailable."), 404

    coordinator_id = _coordinator_id(request.get_json(silent=True))
    if coordinator_id is None:
        return jsonify(error="Choose a valid Event Coordinator."), 400

    result = supabase_request(
        "/rest/v1/rpc/reassign_event_coordinator_for_lead",
        token=identity.token,
        payload={
            "p_event_id": event_id_value,
            "p_coordinator_id": coordinator_id,
        },
        method="POST",
    )
    return _rpc_result(result)
