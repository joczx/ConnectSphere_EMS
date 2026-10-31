"""Unit tests for the attendee's My Registrations API.

Covers personal registration records, status/event data returned by the RPC,
and the empty-list response. UI status labels and the no-records message are
verified separately by frontend/tests/attendee-dashboard.test.mjs.
"""
from unittest.mock import patch

import pytest

from app import create_app


def test_my_registrations_requires_authentication():
    client = create_app().test_client()
    with patch('app.services.registration_service.supabase_request') as rpc:
        assert client.get('/api/my-registrations').status_code == 401
        rpc.assert_not_called()


@pytest.mark.parametrize('records', [[], [
    {'event_id': 1, 'event_name': 'Conference', 'status': 'registered', 'venues': ['Hall']},
    {'event_id': 2, 'event_name': 'Workshop', 'status': 'waiting_list', 'venues': []},
    {'event_id': 3, 'event_name': 'Talk', 'status': 'withdrawn', 'venues': []},
]])
def test_my_registrations_returns_only_the_verified_users_rpc_result(records):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value={'registrations': records}) as rpc:
        response = client.get('/api/my-registrations?attendee_id=someone-else', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == {'registrations': records}
    assert response.headers['Cache-Control'] == 'no-store'
    rpc.assert_called_once_with('/rest/v1/rpc/my_event_registrations', token='verified', payload={}, method='POST')

