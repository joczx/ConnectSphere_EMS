"""SCRUM-35: unit tests for withdrawing an attendee's event registration.

Covers authentication, verified identity, returned withdrawal status,
confirmation, available capacity and refusal responses. Real event-start and
capacity rules are verified separately by frontend/tests/registration-db.mjs.
TC-SCRUM35-001 through 005 test the API contract using mocked RPC results;
they do not execute the database clock comparison or capacity calculation.
"""
from unittest.mock import patch

import pytest

from app import create_app


@pytest.fixture
def client():
    return create_app().test_client()


@pytest.fixture
def successful_withdrawal():
    return {
        'registration': {
            'event_id': 41,
            'attendee_id': 'attendee',
            'status': 'withdrawn',
            'withdrawn_at': '2027-06-15T10:00:00+08:00',
        },
        'available_capacity': 174,
        'message': 'Your registration has been successfully withdrawn.',
    }


def withdraw(client, result):
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}) as auth, \
         patch('app.services.registration_service.supabase_request', return_value=result) as rpc:
        response = client.post('/api/events/41/registrations/withdraw',
                               json={'attendee_id': 'someone-else'},
                               headers={'Authorization': 'Bearer verified'})
    auth.assert_called_once_with('/auth/v1/user', token='verified')
    rpc.assert_called_once_with('/rest/v1/rpc/withdraw_event_registration',
                               token='verified', payload={'p_event_id': 41}, method='POST')
    return response


def test_tc_scrum35_001_003_004_success_status_and_confirmation(client, successful_withdrawal):
    """TC-SCRUM35-001/003/004: AC1 success, AC3 status and AC4 confirmation."""
    response = withdraw(client, successful_withdrawal)
    assert response.status_code == 200
    assert response.json == successful_withdrawal
    record = response.json['registration']
    assert record['event_id'] == 41
    assert record['attendee_id'] == 'attendee'
    assert record['status'] == 'withdrawn'
    assert record['withdrawn_at'] == '2027-06-15T10:00:00+08:00'
    assert response.json['message'] == 'Your registration has been successfully withdrawn.'
    assert 'error' not in response.json
    assert response.headers['Cache-Control'] == 'no-store'


def test_tc_scrum35_002_ac2_returns_start_time_refusal(client):
    """AC2: preserve the at-or-after-start refusal; SQL time is not tested."""
    message = 'Registration cannot be withdrawn at or after the event start time.'
    response = withdraw(client, {'error': message, 'status': 409})
    assert response.status_code == 409
    assert response.json == {'error': message}
    assert 'registration' not in response.json
    assert 'available_capacity' not in response.json


@pytest.mark.parametrize('prior_status,before,after', [
    pytest.param('registered', 173, 174, id='confirmed-place-released'),
    pytest.param('registered', 0, 1, id='full-event-place-released'),
    pytest.param('waiting_list', 0, 0, id='waitlisted-withdrawal-releases-no-place'),
])
def test_tc_scrum35_005_ac5_returns_updated_available_capacity(
        client, successful_withdrawal, prior_status, before, after):
    """AC5: propagate capacity before/after; calculation remains in the RPC."""
    catalogue = {'events': [{'event_id': 41, 'my_registration': prior_status,
                             'available_capacity': before}]}
    result = {**successful_withdrawal, 'available_capacity': after}
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', side_effect=[catalogue, result]) as rpc:
        initial = client.get('/api/registration-events', headers={'Authorization': 'Bearer verified'})
        response = client.post('/api/events/41/registrations/withdraw',
                               headers={'Authorization': 'Bearer verified'})
    assert initial.status_code == response.status_code == 200
    assert initial.json['events'][0]['available_capacity'] == before
    assert response.json['available_capacity'] == after
    assert response.json['registration']['status'] == 'withdrawn'
    assert rpc.call_count == 2
    assert rpc.call_args.args == ('/rest/v1/rpc/withdraw_event_registration',)
    assert rpc.call_args.kwargs == {'token': 'verified', 'payload': {'p_event_id': 41}, 'method': 'POST'}


def test_withdrawal_requires_authentication():
    client = create_app().test_client()
    with patch('app.services.registration_service.supabase_request') as rpc:
        assert client.post('/api/events/1/registrations/withdraw').status_code == 401
        rpc.assert_not_called()


@pytest.mark.parametrize('status,message', [
    (403, 'Only attendees can withdraw registrations.'),
    (404, 'Registration not found.'),
])
def test_withdrawal_refusals_are_returned_unchanged(status, message):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value={'error': message, 'status': status}):
        response = client.post('/api/events/1/registrations/withdraw', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == status
    assert response.json['error'] == message
