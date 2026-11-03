"""Existing unit tests for the attendee event catalogue.

These verify authentication and uncached API responses. They do not establish
that unavailable events are filtered out or venues are supplied; those acceptance
criteria require implementation and database/UI validation beyond these mocks.
"""
from unittest.mock import patch

from app import create_app


def test_upcoming_events_requires_authentication():
    client = create_app().test_client()
    with patch('app.services.registration_service.supabase_request') as rpc:
        assert client.get('/api/registration-events').status_code == 401
        rpc.assert_not_called()


def test_attendee_information_returns_updated_period_and_disables_caching():
    client = create_app().test_client()
    event = {'event_id': 1, 'registration_opens_at': '2027-01-01T10:00:00+08:00',
             'registration_closes_at': '2027-01-02T10:00:00+08:00',
             'waiting_list_enabled': True, 'registration_status': 'not_open'}
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value={'events': [event]}) as rpc:
        response = client.get('/api/registration-events', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == {'events': [event]}
    assert response.headers['Cache-Control'] == 'no-store'
    rpc.assert_called_once_with('/rest/v1/rpc/attendee_registration_events',
                                token='verified', payload={}, method='POST')

