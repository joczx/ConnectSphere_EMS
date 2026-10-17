"""HTTP endpoints for Event Organiser change requests."""

from flask import Blueprint, jsonify, request

from app.services.event_change_request_service import (
    EventChangeRequestError,
    list_change_requests,
    list_eligible_events,
    submit_change_request,
)
from app.services.event_store import StoreError, authenticated_token, supabase_request


event_change_requests = Blueprint(
    "event_change_requests", __name__, url_prefix="/api"
)


@event_change_requests.after_request
def prevent_caching(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@event_change_requests.errorhandler(StoreError)
def store_error(error):
    message = "Please sign in again." if error.status == 401 else "Event change requests are temporarily unavailable."
    return jsonify(error=message), error.status


@event_change_requests.errorhandler(EventChangeRequestError)
def change_request_error(error):
    return jsonify(error.to_dict()), error.status


@event_change_requests.get("/event-change-requests/eligible-events")
def eligible_events():
    token = authenticated_token(supabase_request)
    return jsonify(events=list_eligible_events(token))


@event_change_requests.get("/events/<int:event_id>/change-requests")
def event_change_request_history(event_id):
    token = authenticated_token(supabase_request)
    return jsonify(change_requests=list_change_requests(event_id, token))


@event_change_requests.post("/events/<int:event_id>/change-requests")
def create_event_change_request(event_id):
    token = authenticated_token(supabase_request)
    result = submit_change_request(event_id, request.get_json(silent=True), token)
    return jsonify(result), 201

