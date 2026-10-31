"""Unit tests for withdrawing an attendee's event registration.

Covers authentication, verified identity, returned withdrawal status,
confirmation, available capacity and refusal responses. Real event-start and
capacity rules are verified separately by frontend/tests/registration-db.mjs.
"""
from unittest.mock import patch

import pytest

from app import create_app


def test_withdrawal_requires_authentication():
    client = create_app().test_client()
    with patch('app.services.registration_service.supabase_request') as rpc:
        assert client.post('/api/events/1/registrations/withdraw').status_code == 401
        rpc.assert_not_called()


def test_withdrawal_uses_verified_identity_and_returns_confirmation_and_capacity():
    client = create_app().test_client()
    result = {'registration': {'status': 'withdrawn'}, 'available_capacity': 1,
              'message': 'Your registration has been successfully withdrawn.'}
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value=result) as rpc:
        response = client.post('/api/events/1/registrations/withdraw',
            json={'attendee_id': 'someone-else'}, headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == result
    rpc.assert_called_once_with('/rest/v1/rpc/withdraw_event_registration', token='verified',
                               payload={'p_event_id': 1}, method='POST')



@pytest.mark.parametrize('status,message', [
    (403, 'Only attendees can withdraw registrations.'),
    (404, 'Registration not found.'),
    (409, 'Registration cannot be withdrawn at or after the event start time.'),
])
def test_withdrawal_refusals_are_returned_unchanged(status, message):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value={'error': message, 'status': status}):
        response = client.post('/api/events/1/registrations/withdraw', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == status
    assert response.json['error'] == message

