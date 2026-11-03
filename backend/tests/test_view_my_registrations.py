"""SCRUM-34: unit tests for the attendee's My Registrations API.

Covers personal registration records, status/event data returned by the RPC,
and the empty-list response. UI status labels and the no-records message are
verified separately by frontend/tests/attendee-dashboard.test.mjs.
Supabase is mocked; these tests do not execute database ownership rules.
"""
from unittest.mock import patch

import pytest

from app import create_app


@pytest.fixture
def registration():
    return {
        'event_id': 41,
        'event_name': 'Community Technology Fair',
        'status': 'registered',
        'event_status': 'confirmed',
        'start_datetime': '2027-06-15T11:00:00+08:00',
        'end_datetime': '2027-06-15T17:00:00+08:00',
        'venues': ['Community Hall'],
        'registered_at': '2027-05-02T09:00:00+08:00',
        'withdrawn_at': None,
    }


def fetch_registrations(records):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}) as auth, \
         patch('app.services.registration_service.supabase_request', return_value={'registrations': records}) as rpc:
        response = client.get('/api/my-registrations?attendee_id=someone-else', headers={'Authorization': 'Bearer verified'})
    auth.assert_called_once_with('/auth/v1/user', token='verified')
    rpc.assert_called_once_with('/rest/v1/rpc/my_event_registrations', token='verified', payload={}, method='POST')
    return response


def test_tc_scrum34_001_ac1_attendee_can_view_registered_events(registration):
    """TC-SCRUM34-001 / AC1: return the signed-in attendee's supplied list."""
    records = [registration, {**registration, 'event_id': 42, 'event_name': 'Community Workshop'}]
    response = fetch_registrations(records)
    assert response.status_code == 200
    assert response.json == {'registrations': records}
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('status', [
    pytest.param('registered', id='Confirmed'),
    pytest.param('waiting_list', id='Waitlisted'),
    pytest.param('withdrawn', id='Withdrawn'),
])
def test_tc_scrum34_002_ac2_returns_each_current_registration_status(registration, status):
    """TC-SCRUM34-002 / AC2: preserve status codes used by the UI labels."""
    record = {**registration, 'status': status}
    response = fetch_registrations([record])
    assert response.status_code == 200
    assert response.json['registrations'][0]['status'] == status


@pytest.mark.parametrize('venues', [['Community Hall'], ['Community Hall', 'Workshop Room']])
def test_tc_scrum34_003_ac3_returns_event_name_date_time_and_venue(registration, venues):
    """TC-SCRUM34-003 / AC3: retain complete event details and timezone."""
    record = {**registration, 'venues': venues}
    response = fetch_registrations([record])
    assert response.status_code == 200
    returned = response.json['registrations'][0]
    assert returned['event_id'] == 41
    assert returned['event_name'] == 'Community Technology Fair'
    assert returned['start_datetime'] == '2027-06-15T11:00:00+08:00'
    assert returned['end_datetime'] == '2027-06-15T17:00:00+08:00'
    assert returned['venues'] == venues


def test_tc_scrum34_004_ac4_no_records_returns_empty_list():
    """TC-SCRUM34-004 / AC4: supply the empty state consumed by React.

    The visible message is asserted in attendee-dashboard.test.mjs, since
    the API returns JSON rather than rendering the no-records message.
    """
    response = fetch_registrations([])
    assert response.status_code == 200
    assert response.json == {'registrations': []}
    assert response.headers['Cache-Control'] == 'no-store'


def test_ac2_subsequent_read_returns_updated_registration_status(registration):
    """A second API read must not reuse a previously confirmed status."""
    client = create_app().test_client()
    updated = {**registration, 'status': 'withdrawn', 'withdrawn_at': '2027-05-03T10:00:00+08:00'}
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', side_effect=[
             {'registrations': [registration]}, {'registrations': [updated]},
         ]) as rpc:
        first = client.get('/api/my-registrations', headers={'Authorization': 'Bearer verified'})
        second = client.get('/api/my-registrations', headers={'Authorization': 'Bearer verified'})
    assert first.status_code == second.status_code == 200
    assert first.json['registrations'][0]['status'] == 'registered'
    assert second.json['registrations'][0] == updated
    assert first.headers['Cache-Control'] == second.headers['Cache-Control'] == 'no-store'
    assert rpc.call_count == 2


def test_my_registrations_requires_authentication():
    client = create_app().test_client()
    with patch('app.services.registration_service.supabase_request') as rpc:
        assert client.get('/api/my-registrations').status_code == 401
        rpc.assert_not_called()
