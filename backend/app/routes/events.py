from uuid import UUID
from flask import Blueprint, jsonify, request
from app.services.event_store import StoreError, supabase_request, authenticated_token

events = Blueprint('events', __name__, url_prefix='/api')


@events.after_request
def prevent_caching(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@events.errorhandler(StoreError)
def store_error(error):
    message = 'Please sign in again.' if error.status == 401 else 'Event service is temporarily unavailable.'
    return jsonify(error=message), error.status



@events.get('/events')
def list_events():
    token = authenticated_token(supabase_request)
    rows = supabase_request('/rest/v1/events?select=event_id,event_name,status,start_datetime,end_datetime&order=start_datetime.asc.nullslast', token=token)
    return jsonify(events=rows)


@events.get('/events/<event_id>')
def view_event(event_id):
    token = authenticated_token(supabase_request)
    event_id_value = str(event_id)
    try:
        int(event_id_value)
    except ValueError:
        try:
            UUID(event_id_value)
        except (TypeError, ValueError):
            return jsonify(error='Event not found or access unavailable.'), 404
    rows = supabase_request(f'/rest/v1/events?select=*&event_id=eq.{event_id_value}', token=token)
    if not rows:
        return jsonify(error='Event not found or access unavailable.'), 404
    return jsonify(event=rows[0])


@events.patch('/events/<event_id>/coordinator')
def reassign_event_coordinator(event_id):
    token = authenticated_token(supabase_request)
    event_id_value = str(event_id)
    try:
        int(event_id_value)
    except ValueError:
        try:
            UUID(event_id_value)
        except (TypeError, ValueError):
            return jsonify(error='Event not found or access unavailable.'), 404

    payload = request.get_json(silent=True) or {}
    coordinator_id = payload.get('event_coordinator_id')
    if not isinstance(coordinator_id, str) or not coordinator_id.strip():
        return jsonify(error='Please choose a replacement Event Coordinator.'), 400
    coordinator_id = coordinator_id.strip()

    event_rows = supabase_request(f'/rest/v1/events?select=event_id,event_coordinator_id&event_id=eq.{event_id_value}', token=token)
    if not event_rows:
        return jsonify(error='Event not found or access unavailable.'), 404

    updated = supabase_request(
        f'/rest/v1/events?event_id=eq.{event_id_value}',
        token=token,
        payload={'event_coordinator_id': str(coordinator_id)},
        method='PATCH',
    )
    if not updated:
        return jsonify(error='You do not have permission to reassign this event. Please contact an administrator.'), 403

    return jsonify({
        'message': 'Event coordinator reassigned successfully.',
        'event': updated[0] if isinstance(updated, list) else updated,
    })
