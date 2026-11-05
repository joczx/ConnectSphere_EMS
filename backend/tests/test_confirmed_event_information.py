"""SCRUM-157: confirmed event information API unit tests.

Network calls are mocked. These tests verify returned details, token forwarding,
registration-setting validation and refusals. They do not execute SQL permissions
or render React. AC4 checks filtering of mixed statuses through the explicit
confirmed catalogue query; the unfiltered management list retains every stage.
"""
from unittest.mock import patch

import pytest
import unittest

from app import create_app
from app.services.event_store import StoreError
from app.routes.events import valid_event_id


@pytest.fixture
def client():
    return create_app().test_client()


@pytest.fixture
def confirmed_event():
    return {
        'event_id': 41, 'event_name': 'Community Technology Fair',
        'status': 'confirmed', 'venue_id': '10000000-0000-0000-0000-000000000001',
        'start_datetime': '2027-06-15T11:00:00+08:00',
        'end_datetime': '2027-06-15T17:00:00+08:00',
        'event_organiser_id': 'organiser', 'technical_support_id': 'technical-support',
    }


def settings(**changes):
    return {
        'registration_opens_at': '2027-05-01T09:00:00+08:00',
        'registration_closes_at': '2027-06-14T18:00:00+08:00',
        'waiting_list_enabled': False, **changes,
    }


@pytest.mark.parametrize('actor', ['organiser', 'coordinator'])
def test_tc_scrum157_001_ac1_authorised_user_receives_confirmed_venue_date_and_time(
        client, confirmed_event, actor):
    """AC1: preserve confirmed event times and approved venue information."""
    booking = {'event_id': 41, 'venue_id': confirmed_event['venue_id'],
               'venue_name': 'Confirmed Community Hall', 'status': 'approved'}
    token = f'verified-{actor}'
    with patch('app.routes.events.supabase_request', side_effect=[{'id': actor}, [confirmed_event]]) as query:
        event_response = client.get('/api/events/41', headers={'Authorization': f'Bearer {token}'})
    query.assert_any_call('/rest/v1/events?select=*&event_id=eq.41', token=token)
    with patch('app.routes.venue_bookings.supabase_request', side_effect=[{'id': actor}, {'bookings': [booking]}]) as venue_query:
        venue_response = client.get('/api/venue-bookings/events/41', headers={'Authorization': f'Bearer {token}'})
    assert event_response.status_code == venue_response.status_code == 200
    assert event_response.json == {'event': confirmed_event}
    assert event_response.json['event']['start_datetime'] == '2027-06-15T11:00:00+08:00'
    assert event_response.json['event']['end_datetime'] == '2027-06-15T17:00:00+08:00'
    assert venue_response.json == {'bookings': [booking]}
    assert event_response.headers['Cache-Control'] == venue_response.headers['Cache-Control'] == 'no-store'
    assert venue_query.call_args.args == ('/rest/v1/rpc/event_venue_bookings',)
    assert venue_query.call_args.kwargs == {'token': token, 'payload': {'p_event_id': 41}}


def test_tc_scrum157_002_ac2_returns_arranged_equipment_and_assigned_technical_support(client, confirmed_event):
    """AC2: expose accepted equipment details and assigned technical support."""
    equipment = {'equipment_request_id': 7, 'event_id': 41, 'equipment_type': 'Projector',
                 'quantity': 2, 'technical_requirements': 'HDMI setup and testing', 'status': 'accepted'}
    with patch('app.routes.events.supabase_request', side_effect=[{'id': 'organiser'}, [confirmed_event]]):
        event_response = client.get('/api/events/41', headers={'Authorization': 'Bearer verified'})
    with patch('app.services.equipment_request_service.supabase_request', return_value=[equipment]) as query:
        equipment_response = client.get('/api/events/41/equipment-requests', headers={'Authorization': 'Bearer verified'})
    assert event_response.status_code == equipment_response.status_code == 200
    assert event_response.json['event']['technical_support_id'] == 'technical-support'
    assert equipment_response.json == {'count': 1, 'equipment_requests': [equipment]}
    query.assert_called_once_with('/rest/v1/equipment_request?select=*&event_id=eq.41', token='verified')


def test_tc_scrum157_003_ac3_organiser_can_set_registration_opening_date(client, confirmed_event):
    """AC3: validate and forward opening date using the organiser's token."""
    payload = settings()
    result = {'event': {**confirmed_event, **payload}}
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.routes.events.load_event', return_value=confirmed_event) as load, \
         patch('app.services.registration_service.supabase_request', return_value=result) as rpc:
        response = client.patch('/api/events/41/registration-period', json=payload,
                                headers={'Authorization': 'Bearer verified-organiser'})
    assert response.status_code == 200
    assert response.json == result
    load.assert_called_once_with(41, 'verified-organiser')
    normalized = {'registration_opens_at': '2027-05-01T01:00:00+00:00',
                  'registration_closes_at': '2027-06-14T10:00:00+00:00',
                  'waiting_list_enabled': False}
    rpc.assert_called_once_with('/rest/v1/rpc/set_event_registration_period', token='verified-organiser',
        payload={'p_event_id': 41, **{'p_' + key: value for key, value in normalized.items()}}, method='POST')


@pytest.mark.parametrize('payload,error_field', [
    pytest.param(None, '_body', id='non-object'),
    pytest.param({}, '_body', id='missing-fields'),
    pytest.param(settings(unexpected=True), '_body', id='unexpected-field'),
    pytest.param(settings(registration_opens_at=None), 'registration_opens_at', id='null-opening'),
    pytest.param(settings(registration_opens_at=''), 'registration_opens_at', id='empty-opening'),
    pytest.param(settings(registration_opens_at='invalid'), 'registration_opens_at', id='invalid-opening'),
    pytest.param(settings(registration_opens_at='2027-05-01T09:00:00'), 'registration_opens_at', id='timezone-missing'),
    pytest.param(settings(registration_closes_at='invalid'), 'registration_closes_at', id='invalid-closing'),
    pytest.param(settings(waiting_list_enabled='true'), 'waiting_list_enabled', id='waiting-list-not-boolean'),
    pytest.param(settings(registration_closes_at='2027-05-01T09:00:00+08:00'), 'registration_closes_at', id='closing-equals-opening'),
    pytest.param(settings(registration_closes_at='2027-04-30T09:00:00+08:00'), 'registration_closes_at', id='closing-before-opening'),
])
def test_ac3_invalid_registration_settings_are_rejected(client, payload, error_field):
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.routes.events.load_event') as load, \
         patch('app.services.registration_service.supabase_request') as rpc:
        response = client.patch('/api/events/41/registration-period',
            json=payload, headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 400
    assert error_field in response.json['errors']
    load.assert_not_called()
    rpc.assert_not_called()


def test_ac3_registration_setting_permission_refusal_is_preserved(client, confirmed_event):
    with patch('app.routes.events.supabase_request', return_value={'id': 'coordinator'}), \
         patch('app.routes.events.load_event', return_value=confirmed_event), \
         patch('app.services.registration_service.supabase_request',
               return_value={'error': 'Only the assigned Event Organiser can change registration settings.', 'status': 403}):
        response = client.patch('/api/events/41/registration-period', json=settings(),
                                headers={'Authorization': 'Bearer verified-coordinator'})
    assert response.status_code == 403
    assert 'Event Organiser' in response.json['error']
    assert 'event' not in response.json


@pytest.mark.parametrize('empty', [False, True], ids=['confirmed-events', 'no-confirmed-events'])
def test_tc_scrum157_004_ac4_returns_supplied_confirmed_only_catalogue(client, confirmed_event, empty):
    """AC4: filter mixed input, including when no confirmed events exist."""
    other_rows = [{**confirmed_event, 'event_id': index, 'status': status}
                  for index, status in enumerate(('planning', 'pending_safety_checks', 'completed', 'cancelled'), 50)]
    expected = [] if empty else [confirmed_event]
    rows = other_rows + expected
    with patch('app.routes.events.supabase_request', side_effect=[{'id': 'organiser'}, rows]):
        response = client.get('/api/events?status=confirmed', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == {'events': expected}
    assert all(event['status'] == 'confirmed' for event in response.json['events'])


@pytest.mark.parametrize('status', ['planning', 'pending_safety_checks', 'completed', 'cancelled'])
def test_ac3_registration_settings_refused_for_non_confirmed_event(client, confirmed_event, status):
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.routes.events.load_event', return_value={**confirmed_event, 'status': status}), \
         patch('app.services.registration_service.supabase_request') as rpc:
        response = client.patch('/api/events/41/registration-period', json=settings(),
                                headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 409
    rpc.assert_not_called()


def test_confirmed_event_information_requires_authentication(client):
    with patch('app.routes.events.supabase_request') as query:
        response = client.get('/api/events/41')
    assert response.status_code == 401
    query.assert_not_called()


def test_unauthorised_event_information_is_not_exposed(client):
    with patch('app.routes.events.supabase_request', side_effect=[{'id': 'unauthorised'}, StoreError(403)]):
        response = client.get('/api/events/41', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 403
    assert 'event' not in response.json


@pytest.mark.parametrize('event_id,rows', [('invalid-id', None), ('41', [])])
def test_unavailable_or_invalid_event_returns_not_found(client, event_id, rows):
    results = [{'id': 'organiser'}] if rows is None else [{'id': 'organiser'}, rows]
    with patch('app.routes.events.supabase_request', side_effect=results) as query:
        response = client.get(f'/api/events/{event_id}', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 404
    assert response.json == {'error': 'Event not found or access unavailable.'}
    assert query.call_count == (1 if rows is None else 2)


def test_shared_event_id_validation_accepts_uuid():
    event_id = '10000000-0000-0000-0000-000000000001'
    assert valid_event_id(event_id) == event_id


def test_venue_access_refusal_does_not_return_booking_details(client):
    result = {'error': 'Event not found or access unavailable.', 'status': 404}
    with patch('app.routes.venue_bookings.supabase_request', side_effect=[{'id': 'unassigned'}, result]):
        response = client.get('/api/venue-bookings/events/41', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 404
    assert response.json == {'error': result['error']}


def test_equipment_information_requires_authentication(client):
    with patch('app.services.equipment_request_service.supabase_request') as query:
        response = client.get('/api/events/41/equipment-requests')
    assert response.status_code == 401
    query.assert_not_called()


class EventListWithoutFilterTests(unittest.TestCase):
    # TC-SCRUM157-016 / AC4: without the confirmed filter the event list keeps every stage, so only the
    # confirmed catalogue query narrows it to confirmed events.
    def test_event_list_without_the_confirmed_filter_keeps_every_stage(self):
        rows = [{'event_id': 41, 'status': 'confirmed'}, {'event_id': 50, 'status': 'planning'},
                {'event_id': 51, 'status': 'cancelled'}]
        with patch('app.routes.events.supabase_request', side_effect=[{'id': 'organiser'}, rows]):
            response = create_app().test_client().get('/api/events', headers={'Authorization': 'Bearer verified'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'events': rows})
