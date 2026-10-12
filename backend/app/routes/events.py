from uuid import UUID
from flask import Blueprint, jsonify, request
from app.schemas import event as event_schema
from app.services.event_store import StoreError, supabase_request, authenticated_token
from app.services.event_service import EventError, list_activity, load_event, update_event
from app.services.event_venue_criteria import criteria_from_event, describe, search_filters

events = Blueprint('events', __name__, url_prefix='/api')

# Enough of the event to label the venue search it was opened from, without
# resending details the search has no use for.
EVENT_SUMMARY_FIELDS = (
    'event_id', 'event_name', 'status', 'start_datetime', 'end_datetime',
    'capacity_needed', 'venue_id',
)


@events.after_request
def prevent_caching(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@events.errorhandler(StoreError)
def store_error(error):
    message = 'Please sign in again.' if error.status == 401 else 'Event service is temporarily unavailable.'
    return jsonify(error=message), error.status


@events.errorhandler(EventError)
def event_error(error):
    return jsonify(error.to_dict()), error.status



@events.get('/events')
def list_events():
    token = authenticated_token(supabase_request)
    rows = supabase_request('/rest/v1/events?select=event_id,event_name,status,start_datetime,end_datetime&order=start_datetime.asc.nullslast', token=token)
    return jsonify(events=rows)


def valid_event_id(event_id):
    """Return the id as a string, or None when it is neither an int nor a UUID.

    The column is an integer, but an id reaches here straight from the URL, so
    anything else is refused before it is interpolated into a query.
    """
    event_id_value = str(event_id)
    try:
        int(event_id_value)
    except ValueError:
        try:
            UUID(event_id_value)
        except (TypeError, ValueError):
            return None
    return event_id_value


@events.get('/events/<event_id>')
def view_event(event_id):
    token = authenticated_token(supabase_request)
    event_id_value = valid_event_id(event_id)
    if event_id_value is None:
        return jsonify(error='Event not found or access unavailable.'), 404
    rows = supabase_request(f'/rest/v1/events?select=*&event_id=eq.{event_id_value}', token=token)
    if not rows:
        return jsonify(error='Event not found or access unavailable.'), 404
    return jsonify(event=rows[0])


@events.patch('/events/<event_id>')
def edit_event(event_id):
    """Update an event during planning.

    Send only the fields that changed. A change to a critical field is refused
    with 409 and the field names, so the client can show the warning modal and
    retry with "confirm_critical": true once the user confirms.

    Send "expected_updated_at" with the value the event carried when editing
    began. If someone else has saved since, the write is refused with 409 and
    "stale": true rather than overwriting their work.
    """
    token = authenticated_token(supabase_request)
    event_id_value = valid_event_id(event_id)
    if event_id_value is None:
        return jsonify(error='Event not found or access unavailable.'), 404

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error='Event details must be provided as JSON.'), 400

    # Neither is a field on the event: one is the user answering the warning,
    # the other is the version they were looking at when they started editing.
    payload = dict(payload)
    confirm_critical = payload.pop('confirm_critical', False) is True
    expected_updated_at = payload.pop('expected_updated_at', None)

    row, activity = update_event(
        event_id_value, payload, token, confirm_critical, expected_updated_at
    )

    return jsonify({
        'message': 'No changes to save.' if activity is None else 'Event information updated.',
        'event': row,
        'activity': activity,
    })


@events.get('/events/<event_id>/venue-criteria')
def event_venue_criteria(event_id):
    """What this event needs from a venue, as Venue Search conditions.

    Venue Search is opened from the event being planned, so the requirements
    the event already records become the search filters rather than something
    the coordinator retypes. `filters` is what the search endpoint accepts;
    `requirements` is the same thing worded for the page.
    """
    token = authenticated_token(supabase_request)
    event_id_value = valid_event_id(event_id)
    if event_id_value is None:
        return jsonify(error='Event not found or access unavailable.'), 404

    event = load_event(event_id_value, token)
    criteria = criteria_from_event(event)

    return jsonify({
        'event': {field: event.get(field) for field in EVENT_SUMMARY_FIELDS},
        'filters': search_filters(criteria),
        'requirements': describe(criteria),
        # Searching is reading, so it is not refused outside planning. The page
        # says why a booking cannot follow instead of showing nothing.
        'planning': event_schema.is_editable(event),
        'planning_note': None if event_schema.is_editable(event) else event_schema.why_not_editable(event),
    })


@events.get('/events/<event_id>/activity')
def event_activity(event_id):
    """The event's Activity History, newest first."""
    token = authenticated_token(supabase_request)
    event_id_value = valid_event_id(event_id)
    if event_id_value is None:
        return jsonify(error='Event not found or access unavailable.'), 404

    return jsonify(activity=list_activity(event_id_value, token))


@events.patch('/events/<event_id>/coordinator')
def reassign_event_coordinator(event_id):
    token = authenticated_token(supabase_request)
    event_id_value = valid_event_id(event_id)
    if event_id_value is None:
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
