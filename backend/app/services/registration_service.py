from datetime import datetime, timezone

from app.services.event_store import StoreError, supabase_request
from app.services.event_service import EventError


def registration_call(name, token, payload):
    try:
        result = supabase_request('/rest/v1/rpc/' + name, token=token,
                                  payload=payload, method='POST')
    except StoreError as error:
        if error.code == 'PGRST202':
            raise EventError('Registration is not configured yet. Apply supabase/046_event_registration.sql through 052_event_registration_roster.sql in order.', 503) from error
        raise
    if isinstance(result, dict) and result.get('error'):
        raise EventError(result['error'], result.get('status', 400), errors=result.get('errors'))
    return result


CATALOGUE_FIELDS = (
    'event_id', 'event_name', 'description', 'status', 'start_datetime', 'end_datetime',
    'registration_opens_at', 'registration_closes_at', 'waiting_list_enabled',
    'capacity', 'available_capacity', 'my_registration', 'venues', 'venue_id', 'venue_name',
)


def _catalogue_now():
    return datetime.now(timezone.utc)


def _visible_event(event, now):
    if event.get('status') != 'confirmed':
        return False
    try:
        starts, ends, opens, closes = (
            datetime.fromisoformat(event[field].replace('Z', '+00:00'))
            for field in ('start_datetime', 'end_datetime', 'registration_opens_at', 'registration_closes_at')
        )
    except (KeyError, AttributeError, TypeError, ValueError):
        return False
    if any(value.tzinfo is None for value in (starts, ends, opens, closes)):
        return False
    return opens <= now < closes and now < starts and now < ends


def attendee_catalogue(token):
    """Return confirmed upcoming events using dates, including with an older RPC."""
    result = registration_call('attendee_registration_events', token, {})
    now = _catalogue_now()
    return {**result, 'events': [
        {field: event[field] for field in CATALOGUE_FIELDS if field in event}
        for event in result['events'] if _visible_event(event, now)
    ]}
