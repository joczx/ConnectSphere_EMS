"""HTTP validation and credential propagation for database lifecycle rules."""
from unittest.mock import patch

import pytest

from app import create_app
from app.services.event_store import StoreError


@pytest.fixture
def client():
    return create_app().test_client()


@pytest.mark.parametrize('method,path,body', [
    ('post', '/api/events/status-refresh', {}),
    ('post', '/api/events/1/cancel', {}),
    ('post', '/api/events/1/safety-checks', {}),
    ('post', '/api/event-requests/1/cancel', {}),
])
def test_lifecycle_actions_require_authentication(client, method, path, body):
    with patch('app.services.event_status_service.supabase_request') as query:
        response = getattr(client, method)(path, json=body)
    assert response.status_code == 401
    query.assert_not_called()


def test_registration_readiness_endpoint_no_longer_exists(client):
    response = client.patch('/api/events/1/registration-readiness', json={'ready': True},
                            headers={'Authorization': 'Bearer user-token'})
    assert response.status_code == 404


def test_coordinator_submits_event_for_safety_checks_with_their_token(client):
    result = {'event': {'event_id': 1, 'status': 'pending_safety_checks'},
              'message': 'Event submitted for safety checks. The assigned Safety Officer has been notified.'}
    with patch('app.routes.events.supabase_request', return_value={'id': 'coordinator'}), \
         patch('app.services.event_status_service.supabase_request', return_value=result) as query:
        response = client.post('/api/events/1/safety-checks', headers={'Authorization': 'Bearer user-token'})
    assert response.status_code == 200
    assert response.json == result
    query.assert_called_once_with('/rest/v1/rpc/submit_event_for_safety_checks', token='user-token',
                                  payload={'p_event_id': 1}, method='POST')


def test_incomplete_arrangements_keep_the_event_in_planning(client):
    result = {'error': 'Complete the planning arrangements first: An approved venue booking matching the event is required.',
              'blockers': ['An approved venue booking matching the event is required.'], 'status': 409}
    with patch('app.routes.events.supabase_request', return_value={'id': 'coordinator'}), \
         patch('app.services.event_status_service.supabase_request', return_value=result):
        response = client.post('/api/events/1/safety-checks', headers={'Authorization': 'Bearer user-token'})
    assert response.status_code == 409
    assert 'approved venue booking' in response.json['error']


def test_failed_condition_is_a_conflict_not_a_service_outage(client):
    with patch('app.routes.events.supabase_request', return_value={'id': 'user'}), \
         patch('app.services.event_status_service.supabase_request', side_effect=StoreError(503, code='23514')):
        response = client.post('/api/events/1/cancel', headers={'Authorization': 'Bearer user-token'})
    assert response.status_code == 409


def test_missing_status_rpc_identifies_required_migration(client):
    with patch('app.routes.events.supabase_request', return_value={'id': 'user'}), \
         patch('app.services.event_status_service.supabase_request', side_effect=StoreError(503, code='PGRST202')):
        response = client.post('/api/events/status-refresh', headers={'Authorization': 'Bearer user-token'})
    assert response.status_code == 503
    assert '030_event_status_automation.sql' in response.json['error']
