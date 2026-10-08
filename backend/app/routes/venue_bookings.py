"""Venue booking requests: submission, review and the coordinator's alerts.

Every endpoint calls a database function, and those functions enforce the
roles: Event Coordinators submit, Venue Staff review, and each caller sees only
what they are allowed to. This module validates and shapes; it never decides
who may do what.
"""
from uuid import UUID

from flask import Blueprint, jsonify, request
from app.schemas.venue_booking import parse_booking
from app.schemas.venue_booking_review import parse_review
from app.services.event_store import StoreError, authenticated_token, supabase_request

venue_bookings = Blueprint('venue_bookings', __name__, url_prefix='/api/venue-bookings')

NOT_FOUND = 'Booking request not found or access unavailable.'


@venue_bookings.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@venue_bookings.errorhandler(StoreError)
def store_error(error):
    message = 'Please sign in again.' if error.status == 401 else 'Venue bookings are temporarily unavailable.'
    return jsonify(error=message), error.status


def rpc(name, token, payload):
    return supabase_request(f'/rest/v1/rpc/{name}', token=token, payload=payload)


def refused(result):
    """The database's own refusal, passed on with its status.

    Functions report a refusal as {"error": ..., "status": ...} rather than
    raising, so the wording and the status they chose reach the user intact.
    """
    body = {key: value for key, value in result.items() if key != 'status'}
    return jsonify(body), result.get('status', 400)


def valid_booking_id(booking_id):
    try:
        return str(UUID(booking_id))
    except ValueError:
        return None


@venue_bookings.post('')
def submit():
    token = authenticated_token(supabase_request)
    data, errors = parse_booking(request.get_json(silent=True))
    if errors:
        return jsonify(error='Check the booking details.', errors=errors), 400
    result = rpc('submit_venue_booking', token, {'p_booking': data})
    if result.get('error'):
        return refused(result)
    return jsonify(message='Booking request submitted. Venue Staff can now review it.', booking=result), 201


@venue_bookings.get('')
def list_bookings():
    token = authenticated_token(supabase_request)
    result = rpc('list_venue_bookings', token, {})
    if result.get('error'):
        return refused(result)
    return jsonify(result)


@venue_bookings.get('/alerts')
def alerts():
    """The caller's unread decisions on their own booking requests."""
    token = authenticated_token(supabase_request)
    result = rpc('venue_booking_alerts', token, {})
    if isinstance(result, dict) and result.get('error'):
        return refused(result)
    return jsonify(alerts=result if isinstance(result, list) else [])


@venue_bookings.post('/alerts/dismiss')
def dismiss_alerts():
    token = authenticated_token(supabase_request)
    body = request.get_json(silent=True)
    ids = body.get('notification_ids') if isinstance(body, dict) else None
    if (not isinstance(ids, list) or not ids
            or not all(type(item) is int and item > 0 for item in ids)):
        return jsonify(error='Choose which alerts to dismiss.'), 400
    result = rpc('dismiss_venue_booking_alerts', token, {'p_notification_ids': ids})
    if result.get('error'):
        return refused(result)
    return jsonify(result)


@venue_bookings.get('/<booking_id>')
def view(booking_id):
    token = authenticated_token(supabase_request)
    booking_id = valid_booking_id(booking_id)
    if booking_id is None:
        return jsonify(error=NOT_FOUND), 404
    result = rpc('get_venue_booking', token, {'p_booking_id': booking_id})
    if result.get('error'):
        return refused(result)
    return jsonify(result)


@venue_bookings.post('/<booking_id>/review')
def review(booking_id):
    """Approve or reject a request. The reviewer is the signed-in user, never
    a value from the body, so a decision is attributable to whoever made it."""
    token = authenticated_token(supabase_request)
    booking_id = valid_booking_id(booking_id)
    if booking_id is None:
        return jsonify(error=NOT_FOUND), 404

    data, errors = parse_review(request.get_json(silent=True))
    if errors:
        return jsonify(error='Check the review decision.', errors=errors), 400

    result = rpc('review_venue_booking', token, {
        'p_booking_id': booking_id,
        'p_outcome': data['outcome'],
        'p_comments': data['comments'],
    })
    if result.get('error'):
        return refused(result)

    # Worded around what is certain. The alert itself is best effort, but the
    # outcome and comments are on the coordinator's request either way.
    return jsonify(
        message=f"Booking request {data['outcome']}. The Event Coordinator will see the outcome and your comments.",
        booking=result.get('booking'),
    )
