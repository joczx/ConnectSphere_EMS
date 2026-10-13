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
    ('patch', '/api/events/1/registration-readiness', {'ready': True}),
    ('post', '/api/events/1/cancel', {}),
    ('post', '/api/event-requests/1/cancel', {}),
])
def test_lifecycle_actions_require_authentication(client, method, path, body):
    with patch('app.services.event_status_service.supabase_request') as query:
        response = getattr(client, method)(path, json=body)
    assert response.status_code == 401
    query.assert_not_called()


@pytest.mark.parametrize('body', [None, {}, {'ready': 'true'}, {'ready': 1}, {'ready': True, 'status': 'confirmed'}])
def test_registration_payload_cannot_set_status_or_coerce_readiness(client, body):
    with patch('app.routes.events.supabase_request', return_value={'id': 'coordinator'}), \
         patch('app.services.event_status_service.supabase_request') as query:
        response = client.patch('/api/events/1/registration-readiness', json=body,
                                headers={'Authorization': 'Bearer user-token'})
    assert response.status_code == 400
    query.assert_not_called()


def test_registration_uses_the_verified_bearer_token_and_returns_current_stage(client):
    result = {'event': {'event_id': 1, 'status': 'confirmed', 'registration_ready': True}, 'blockers': []}
    with patch('app.routes.events.supabase_request', return_value={'id': 'coordinator'}), \
         patch('app.services.event_status_service.supabase_request', return_value=result) as query:
        response = client.patch('/api/events/1/registration-readiness', json={'ready': True},
                                headers={'Authorization': 'Bearer user-token'})
    assert response.status_code == 200
    assert response.json == result
    query.assert_called_once_with('/rest/v1/rpc/set_event_registration_ready', token='user-token',
                                  payload={'p_event_id': 1, 'p_ready': True}, method='POST')


@pytest.mark.parametrize('result,status', [
    ({'error': 'Only the assigned coordinator can update readiness.', 'status': 403}, 403),
    ({'error': 'Event already completed.', 'status': 409}, 409),
])
def test_database_refusals_remain_refusals(client, result, status):
    with patch('app.routes.events.supabase_request', return_value={'id': 'user'}), \
         patch('app.services.event_status_service.supabase_request', return_value=result):
        response = client.patch('/api/events/1/registration-readiness', json={'ready': True},
                                headers={'Authorization': 'Bearer user-token'})
    assert response.status_code == status
    assert 'event' not in response.json


def test_failed_condition_is_a_conflict_not_a_service_outage(client):
    with patch('app.routes.events.supabase_request', return_value={'id': 'user'}), \
         patch('app.services.event_status_service.supabase_request', side_effect=StoreError(503, code='23514')):
        response = client.post('/api/events/1/cancel', headers={'Authorization': 'Bearer user-token'})
    assert response.status_code == 409
