"""Booking submission and the Venue Staff inbox; RPCs enforce roles."""
from flask import Blueprint, jsonify, request
from app.schemas.venue_booking import parse_booking
from app.services.event_store import StoreError, authenticated_token, supabase_request

venue_bookings = Blueprint('venue_bookings', __name__, url_prefix='/api/venue-bookings')


@venue_bookings.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@venue_bookings.errorhandler(StoreError)
def store_error(error):
    message = 'Please sign in again.' if error.status == 401 else 'Venue bookings are temporarily unavailable.'
    return jsonify(error=message), error.status


@venue_bookings.post('')
def submit():
    token = authenticated_token(supabase_request)
    data, errors = parse_booking(request.get_json(silent=True))
    if errors:
        return jsonify(error='Check the booking details.', errors=errors), 400
    result = supabase_request('/rest/v1/rpc/submit_venue_booking', token=token, payload={'p_booking': data})
    if result.get('error'):
        return jsonify(result), result.get('status', 400)
    return jsonify(message='Booking request submitted. Venue Staff can now review it.', booking=result), 201


@venue_bookings.get('')
def list_bookings():
    token = authenticated_token(supabase_request)
    result = supabase_request('/rest/v1/rpc/list_venue_bookings', token=token, payload={})
    return jsonify(result), result.get('status', 200)
