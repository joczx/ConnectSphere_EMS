"""SCRUM-32: attendee catalogue API unit tests, mapped to AC1--AC4.

Supabase is mocked. These verify returned event details, fresh reads and cache
headers. AC4 uses an already-filtered empty RPC result, as specified in the test
case; it does not prove SQL filtering. Venue lookup and UI rendering also remain
outside these tests. Passing API tests do not establish full story implementation.
"""
from unittest.mock import patch
import pytest

import pytest

from app import create_app
from app.services.event_store import StoreError


@pytest.fixture
def event():
    return {
        'event_id': 41, 'event_name': 'Community Technology Fair',
        'description': 'Community technology demonstrations and workshops.',
        'status': 'confirmed', 'registration_status': 'open',
        'start_datetime': '2027-06-15T10:00:00+08:00',
        'end_datetime': '2027-06-15T16:00:00+08:00',
        'venue_id': '10000000-0000-0000-0000-000000000001',
        'venue_name': 'Confirmed Community Hall',
        'capacity': 200, 'available_capacity': 173,
        'registration_opens_at': '2027-05-01T09:00:00+08:00',
        'registration_closes_at': '2027-06-14T18:00:00+08:00',
        'waiting_list_enabled': True,
    }


def get_catalogue(rows):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}) as auth, \
         patch('app.services.registration_service.supabase_request', return_value={'events': rows}) as rpc:
        response = client.get('/api/registration-events', headers={'Authorization': 'Bearer verified'})
    auth.assert_called_once_with('/auth/v1/user', token='verified')
    rpc.assert_called_once_with('/rest/v1/rpc/attendee_registration_events',
                                token='verified', payload={}, method='POST')
    return response


def test_tc_scrum32_001_ac1_lists_upcoming_events_open_for_registration(event):
    """AC1: return the supplied upcoming, confirmed, open event list."""
    rows = [event, {**event, 'event_id': 42, 'event_name': 'Community Workshop'}]
    response = get_catalogue(rows)
    assert response.status_code == 200
    assert response.json == {'events': rows}
    assert all(item['status'] == 'confirmed' and item['registration_status'] == 'open'
               for item in response.json['events'])
    assert response.json['events'][0]['available_capacity'] == 173
    assert response.headers['Cache-Control'] == 'no-store'


def test_tc_scrum32_002_ac2_preserves_all_event_and_venue_details(event):
    """AC2: preserve each required field supplied by the RPC."""
    response = get_catalogue([event])
    assert response.status_code == 200
    returned = response.json['events'][0]
    for field in ('event_id', 'event_name', 'description', 'start_datetime', 'end_datetime',
                  'venue_id', 'venue_name', 'capacity', 'available_capacity',
                  'registration_opens_at', 'registration_closes_at', 'waiting_list_enabled'):
        assert returned[field] == event[field], field


@pytest.mark.parametrize('scenario', ['cancelled', 'closed', 'not_open'])
def test_tc_scrum32_004_ac4_preserves_empty_catalogue_for_unavailable_events(scenario):
    """AC4 specified case: an empty result is returned for each label.

    All three labels deliberately mock the same empty list. No unavailable row
    is provided, so this is not a test of the eligibility filtering algorithm.
    """
    response = get_catalogue([])
    assert response.status_code == 200, scenario
    assert response.json == {'events': []}, scenario


def test_upcoming_events_requires_authentication():
    client = create_app().test_client()
    with patch('app.services.registration_service.supabase_request') as rpc:
        assert client.get('/api/registration-events').status_code == 401
        rpc.assert_not_called()


def test_tc_scrum32_003_ac3_fetches_latest_confirmed_details_without_caching(event):
    """AC3: a later read retrieves updated details instead of reusing a row."""
    client = create_app().test_client()
    updated = {**event, 'event_name': 'Updated Technology Fair',
               'description': 'Updated programme', 'venue_name': 'Updated Confirmed Venue',
               'venue_id': '10000000-0000-0000-0000-000000000002',
               'start_datetime': '2027-06-15T11:00:00+08:00',
               'end_datetime': '2027-06-15T17:00:00+08:00',
               'registration_closes_at': '2027-06-14T19:00:00+08:00'}
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', side_effect=[
             {'events': [event]}, {'events': [updated]},
         ]) as rpc:
        before = client.get('/api/registration-events', headers={'Authorization': 'Bearer verified'})
        after = client.get('/api/registration-events', headers={'Authorization': 'Bearer verified'})
    assert before.status_code == after.status_code == 200
    assert before.json == {'events': [event]}
    assert after.json == {'events': [updated]}
    assert before.headers['Cache-Control'] == after.headers['Cache-Control'] == 'no-store'
    assert rpc.call_count == 2
    for call in rpc.call_args_list:
        assert call.args == ('/rest/v1/rpc/attendee_registration_events',)
        assert call.kwargs == {'token': 'verified', 'payload': {}, 'method': 'POST'}


@pytest.mark.parametrize('result,status,message', [
    pytest.param(StoreError(503, code='PGRST202'), 503, 'Registration is not configured yet.', id='TC-SCRUM32-005'),
    pytest.param(StoreError(503), 503, 'Event service is temporarily unavailable.', id='TC-SCRUM32-006'),
    pytest.param({'error': 'Only attendees can browse registration events.', 'status': 403}, 403,
                 'Only attendees can browse registration events.', id='TC-SCRUM32-007'),
])
def test_unavailable_catalogue_is_reported_not_shown_as_empty(result, status, message):
    """TC-SCRUM32-005/006/007 / AC1: registration not set up, the database
    unavailable, or the request refused is reported to the attendee, never
    shown as an empty list of events."""
    client = create_app().test_client()
    rpc = {'side_effect': result} if isinstance(result, StoreError) else {'return_value': result}
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', **rpc):
        response = client.get('/api/registration-events', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == status
    assert response.json['error'].startswith(message)
    assert 'events' not in response.json

