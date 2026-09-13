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


@events.post('/login')
def login():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or not isinstance(body.get('email'), str) or not isinstance(body.get('password'), str):
        return jsonify(error='Email and password are required.'), 400
    result = supabase_request('/auth/v1/token?grant_type=password', payload={
        'email': body['email'], 'password': body['password'],
    })
    return jsonify(access_token=result['access_token'])


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
    rows = supabase_request('/rest/v1/events?select=event_id,event_name,starts_at,updated_at,version&order=starts_at.asc.nullslast', token=token)
    return jsonify(events=rows)


@events.get('/events/<event_id>')
def view_event(event_id):
    token = authenticated_token()
    try:
        event_id = str(UUID(event_id))
    except ValueError:
        return jsonify(error='Event not found or access unavailable.'), 404
    rows = supabase_request(f'/rest/v1/events?select=*&event_id=eq.{event_id}', token=token)
    if not rows:
        return jsonify(error='Event not found or access unavailable.'), 404
    return jsonify(event=rows[0])
