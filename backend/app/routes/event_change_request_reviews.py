"""Coordinator routes attached to the shared event-change blueprint."""

from flask import jsonify, request

from app.routes.event_change_requests import event_change_requests
from app.services.event_change_request_review_service import (
    decide,
    get_for_review,
    list_for_coordinator,
)
from app.services.event_store import authenticated_token, supabase_request


@event_change_requests.get("/event-change-requests")
def change_request_queue():
    token = authenticated_token(supabase_request)
    return jsonify(change_requests=list_for_coordinator(token, status=request.args.get("status")))


@event_change_requests.get("/event-change-requests/<int:request_id>")
def change_request_detail(request_id):
    token = authenticated_token(supabase_request)
    return jsonify(get_for_review(request_id, token))


@event_change_requests.post("/event-change-requests/<int:request_id>/decision")
def change_request_decision(request_id):
    token = authenticated_token(supabase_request)
    result = decide(request_id, request.get_json(silent=True), token)
    return jsonify(result)

