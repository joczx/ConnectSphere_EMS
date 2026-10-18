"""Read-only Safety Officer views for events awaiting operational checks."""

from flask import Blueprint, jsonify, request

from app.services.event_status_service import lifecycle_call
from app.services.event_store import StoreError, authenticated_token
from app.services.event_service import EventError


operational_safety = Blueprint('operational_safety', __name__, url_prefix='/api')


@operational_safety.after_request
def prevent_caching(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@operational_safety.errorhandler(StoreError)
def store_error(error):
    message = 'Please sign in again.' if error.status == 401 else 'Operational safety information is temporarily unavailable.'
    return jsonify(error=message), error.status


@operational_safety.errorhandler(EventError)
def event_error(error):
    return jsonify(error.to_dict()), error.status


@operational_safety.get('/operational-safety-reviews')
def safety_review_queue():
    """Events eligible for review, visible only to Safety Officers in the RPC."""
    token = authenticated_token()
    return jsonify(lifecycle_call('safety_review_queue', token, {}))


@operational_safety.get('/operational-safety-reviews/<int:event_id>')
def safety_review_event(event_id):
    """One pending safety review with the arrangements the officer needs."""
    token = authenticated_token()
    return jsonify(lifecycle_call('safety_review_event', token, {'p_event_id': event_id}))


@operational_safety.post('/operational-safety-reviews/<int:event_id>/decision')
def record_safety_decision(event_id):
    """Record an approve/reject/request-changes decision for one pending event."""
    token = authenticated_token()
    body = request.get_json(silent=True)
    body = body if isinstance(body, dict) else {}
    return jsonify(lifecycle_call('record_safety_decision', token, {
        'p_event_id': event_id,
        'p_outcome': body.get('outcome'),
        'p_remarks': body.get('remarks'),
        'p_affected_arrangements': body.get('affected_arrangements'),
    }))
