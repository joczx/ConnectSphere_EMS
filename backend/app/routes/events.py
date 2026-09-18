from uuid import UUID
from flask import Blueprint, jsonify, request
from app.services.event_store import StoreError, supabase_request

events = Blueprint('events', __name__, url_prefix='/api')


@events.after_request
def prevent_caching(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@events.errorhandler(StoreError)
def store_error(error):
    message = 'Please sign in again.' if error.status == 401 else 'Event service is temporarily unavailable.'
    return jsonify(error=message), error.status


def authenticated_token():
    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token.strip():
        raise StoreError(401)
    user = supabase_request('/auth/v1/user', token=token)
    if not user.get('id'):
        raise StoreError(401)
    return token


@events.get('/events')
def list_events():
    token = authenticated_token()
    rows = supabase_request('/rest/v1/events?select=event_id,event_name,status,start_datetime,end_datetime&order=start_datetime.asc.nullslast', token=token)
    return jsonify(events=rows)


@events.get('/events/<event_id>')
def view_event(event_id):
    token = authenticated_token()
    try:
        event_id = int(event_id)
    except ValueError:
        return jsonify(error='Event not found or access unavailable.'), 404
    rows = supabase_request(f'/rest/v1/events?select=*&event_id=eq.{event_id}', token=token)
    if not rows:
        return jsonify(error='Event not found or access unavailable.'), 404
    return jsonify(event=rows[0])
