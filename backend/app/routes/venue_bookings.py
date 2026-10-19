"""Venue booking requests: submission, review and the coordinator's alerts.

Every endpoint calls a database function, and those functions enforce the
roles: Event Coordinators submit, Venue Staff review, and each caller sees only
what they are allowed to. This module validates and shapes; it never decides
who may do what.
"""
from datetime import datetime
from uuid import UUID
from urllib.parse import quote

from flask import Blueprint, jsonify, request
from app.schemas.venue_booking import parse_booking
from app.schemas.venue_booking_review import parse_review
from app.services.event_store import (
    StoreError,
    authenticated_token,
    supabase_admin_request,
    supabase_request,
)
from app.services.authorization import (
    AuthorizationError,
    current_user,
    has_role,
    load_event,
    require_event_access,
    require_roles,
)

venue_bookings = Blueprint('venue_bookings', __name__, url_prefix='/api/venue-bookings')

NOT_FOUND = 'Booking request not found or access unavailable.'


@venue_bookings.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@venue_bookings.errorhandler(StoreError)
def store_error(error):
    if error.code == '23505':  # venue_booking_one_active_per_event_venue (042)
        return jsonify(error='This event already has a pending or approved booking for this venue. '
                             'It must be rejected, cancelled or expire before the venue can be requested again.'), 409
    message = 'Please sign in again.' if error.status == 401 else 'Venue bookings are temporarily unavailable.'
    return jsonify(error=message), error.status


def rpc(name, token, payload):
    return supabase_request(f'/rest/v1/rpc/{name}', token=token, payload=payload)


def booking_event(booking_id):
    try:
        booking_id = str(UUID(str(booking_id)))
    except (ValueError, TypeError):
        return None
    rows = supabase_admin_request(
        "/rest/v1/venue_booking_requests?select=booking_id,event_id"
        f"&booking_id=eq.{quote(booking_id, safe='')}&limit=1"
    )
    return rows[0] if rows else None


def authorize_booking(booking_id, identity, staff_only=False):
    booking = booking_event(booking_id)
    if booking is None or booking.get("event_id") is None:
        raise AuthorizationError(NOT_FOUND, status=404)
    event = load_event(booking["event_id"])
    if staff_only:
        if str(event.get("venue_staff_id")) != identity.user_id:
            raise AuthorizationError(NOT_FOUND, status=404)
        return event
    elif can_access_booking_event(event, identity):
        return event
    else:
        raise AuthorizationError(NOT_FOUND, status=404)
    return event


def can_access_booking_event(event, identity):
    """Match the event assignment rules used for an individual booking read."""
    return (
        has_role(identity, "Event Coordinator")
        and str(event.get("event_coordinator_id")) == identity.user_id
    ) or (
        has_role(identity, "Venue Staff")
        and str(event.get("venue_staff_id")) == identity.user_id
    )


def filter_assigned_bookings(bookings, identity):
    """Keep only bookings whose event is assigned to this Coordinator or Staff."""
    event_ids = {
        booking["event_id"]
        for booking in bookings
        if isinstance(booking, dict)
        and isinstance(booking.get("event_id"), int)
        and not isinstance(booking.get("event_id"), bool)
    }
    if not event_ids:
        return []

    event_filter = ",".join(str(event_id) for event_id in sorted(event_ids))
    events = supabase_admin_request(
        "/rest/v1/events?select=event_id,event_coordinator_id,venue_staff_id"
        f"&event_id=in.({event_filter})"
    )
    visible_event_ids = {
        event["event_id"]
        for event in events
        if can_access_booking_event(event, identity)
    }
    return [
        booking
        for booking in bookings
        if isinstance(booking, dict) and booking.get("event_id") in visible_event_ids
    ]


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
    identity = require_roles("Event Coordinator")
    data, errors = parse_booking(request.get_json(silent=True))
    if errors:
        return jsonify(error='Check the booking details.', errors=errors), 400
    require_event_access(data["event_id"], identity)
    result = rpc('submit_venue_booking', identity.token, {'p_booking': data})
    if result.get('error'):
        return refused(result)
    return jsonify(message='Booking request submitted. Venue Staff can now review it.', booking=result), 201


@venue_bookings.get('')
def list_bookings():
    identity = require_roles("Event Coordinator", "Venue Staff")
    result = rpc('list_venue_bookings', identity.token, {})
    if result.get('error'):
        return refused(result)
    result["bookings"] = filter_assigned_bookings(
        result.get("bookings", []),
        identity,
    )
    return jsonify(result)


@venue_bookings.get('/alerts')
def alerts():
    """The caller's unread decisions on their own booking requests."""
    identity = require_roles("Event Coordinator")
    result = rpc('venue_booking_alerts', identity.token, {})
    if isinstance(result, dict) and result.get('error'):
        return refused(result)
    allowed_alerts = []
    for alert in result if isinstance(result, list) else []:
        booking = booking_event(alert.get("venue_booking_id"))
        if booking is None or booking.get("event_id") is None:
            continue
        event = load_event(booking["event_id"])
        if event and str(event.get("event_coordinator_id")) == identity.user_id:
            allowed_alerts.append(alert)
    return jsonify(alerts=allowed_alerts)


@venue_bookings.post('/alerts/dismiss')
def dismiss_alerts():
    identity = require_roles("Event Coordinator")
    body = request.get_json(silent=True)
    ids = body.get('notification_ids') if isinstance(body, dict) else None
    if (not isinstance(ids, list) or not ids
            or not all(type(item) is int and item > 0 for item in ids)):
        return jsonify(error='Choose which alerts to dismiss.'), 400
    id_filter = ",".join(str(item) for item in ids)
    alerts_to_dismiss = supabase_admin_request(
        "/rest/v1/notification?select=notification_id,venue_booking_id"
        f"&notification_id=in.({id_filter})&recipient_id=eq.{identity.user_id}"
    )
    for alert in alerts_to_dismiss:
        booking = booking_event(alert.get("venue_booking_id"))
        if booking is None or booking.get("event_id") is None:
            raise AuthorizationError(NOT_FOUND, status=404)
        event = load_event(booking["event_id"])
        if not event or str(event.get("event_coordinator_id")) != identity.user_id:
            raise AuthorizationError(NOT_FOUND, status=404)
    result = rpc('dismiss_venue_booking_alerts', identity.token, {'p_notification_ids': ids})
    if result.get('error'):
        return refused(result)
    return jsonify(result)


@venue_bookings.get('/<booking_id>')
def view(booking_id):
    identity = require_roles("Event Coordinator", "Venue Staff")
    booking_id = valid_booking_id(booking_id)
    if booking_id is None:
        return jsonify(error=NOT_FOUND), 404
    event = authorize_booking(booking_id, identity)
    result = rpc('get_venue_booking', identity.token, {'p_booking_id': booking_id})
    if result.get('error'):
        return refused(result)
    result['can_review'] = (
        str(event.get('venue_staff_id')) == identity.user_id
    )
    return jsonify(result)


@venue_bookings.patch('/<booking_id>')
def modify(booking_id):
    """Change the venue or notes of one booking; the database rechecks it and
    sends it back to Venue Staff."""
    token = authenticated_token(supabase_request)
    body = request.get_json(silent=True) or {}
    venue_id, notes = valid_booking_id(str(body.get('venue_id'))), body.get('venue_requirements')
    if valid_booking_id(booking_id) is None or venue_id is None or not isinstance(notes, str) or not notes.strip():
        return jsonify(error='Choose a venue and enter the venue requirements.'), 400
    result = rpc('modify_venue_booking', token, {
        'p_booking_id': booking_id, 'p_venue_id': venue_id, 'p_venue_requirements': notes})
    if result.get('error'):
        return refused(result)
    return jsonify(message='Booking updated. Venue Staff will review it again.', booking=result['booking'])


@venue_bookings.post('/<booking_id>/cancel')
def cancel(booking_id):
    """Cancel one booking; the event and its other bookings are untouched."""
    token = authenticated_token(supabase_request)
    if valid_booking_id(booking_id) is None:
        return jsonify(error=NOT_FOUND), 404
    result = rpc('cancel_venue_booking', token, {'p_booking_id': booking_id})
    if result.get('error'):
        return refused(result)
    return jsonify(message='Venue booking cancelled.', booking=result['booking'])


@venue_bookings.post('/<booking_id>/hold')
def hold(booking_id):
    """Venue Staff hold a pending request until an expiry; it is confirmed by approving it."""
    token = authenticated_token(supabase_request)
    if valid_booking_id(booking_id) is None:
        return jsonify(error=NOT_FOUND), 404
    try:
        expires = datetime.fromisoformat((request.get_json(silent=True) or {})['expires_at'])
        if expires.tzinfo is None:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify(error='An expiry date and time is required.', errors={'expires_at': 'A valid expiry is required.'}), 400
    result = rpc('hold_venue_booking', token, {'p_booking_id': booking_id, 'p_expires_at': expires.isoformat()})
    if result.get('error'):
        return refused(result)
    return jsonify(message='Tentative hold placed. The Event Coordinator has been told when it expires.', booking=result['booking'])


@venue_bookings.delete('/<booking_id>/hold')
def release_hold(booking_id):
    """Venue Staff release a hold early; the request stays pending."""
    token = authenticated_token(supabase_request)
    if valid_booking_id(booking_id) is None:
        return jsonify(error=NOT_FOUND), 404
    result = rpc('release_venue_hold', token, {'p_booking_id': booking_id})
    if result.get('error'):
        return refused(result)
    return jsonify(message='Tentative hold released. The Event Coordinator has been told.', booking=result['booking'])


@venue_bookings.post('/<booking_id>/review')
def review(booking_id):
    """Approve or reject a request. The reviewer is the signed-in user, never
    a value from the body, so a decision is attributable to whoever made it."""
    identity = current_user()
    booking_id = valid_booking_id(booking_id)
    if booking_id is None:
        return jsonify(error=NOT_FOUND), 404

    data, errors = parse_review(request.get_json(silent=True))
    if errors:
        return jsonify(error='Check the review decision.', errors=errors), 400

    authorize_booking(booking_id, identity, staff_only=True)
    result = supabase_admin_request("/rest/v1/rpc/review_venue_booking_for_backend", {
        "p_actor_id": identity.user_id,
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
