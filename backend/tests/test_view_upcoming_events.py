"""Existing unit tests for the attendee event catalogue.

These verify authentication and uncached API responses. They do not establish
that unavailable events are filtered out or venues are supplied; those acceptance
criteria require implementation and database/UI validation beyond these mocks.
"""
from unittest.mock import patch

import pytest

from app import create_app
from app.services.event_store import StoreError


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

