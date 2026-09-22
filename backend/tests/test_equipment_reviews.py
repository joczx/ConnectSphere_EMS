from unittest.mock import patch

import pytest
from app import create_app


@pytest.fixture
def client():
    return create_app().test_client()


@pytest.fixture
def auth():
    with patch('app.routes.equipment.authenticated_token', return_value='user-token'):
        yield


def test_review_requires_auth(client):
    assert client.post('/api/equipment-request-reviews/1', json={}).status_code == 401
    assert client.get('/api/equipment-request-reviews').status_code == 401


@pytest.mark.parametrize('body', [None, {}, {'outcome': 'unknown'},
    {'outcome': 'accepted', 'equipment_id': True},
    {'outcome': 'partially_accepted', 'equipment_id': 1, 'accepted_quantity': 0},
    {'outcome': 'partially_accepted', 'equipment_id': 1, 'accepted_quantity': 1.5},
    {'outcome': 'rejected', 'reason': '   '}])
def test_invalid_decision_does_not_write(client, auth, body):
    with patch('app.services.equipment_review_service.supabase_request') as query:
        response = client.post('/api/equipment-request-reviews/1', json=body)
        assert response.status_code == 400
        query.assert_not_called()


@pytest.mark.parametrize('outcome, amount', [('accepted', None), ('partially_accepted', 3), ('rejected', None)])
def test_review_uses_atomic_rpc(client, auth, outcome, amount):
    row = {'equipment_request_id': 1, 'status': outcome, 'quantity': 5, 'accepted_quantity': amount}
    with patch('app.services.equipment_review_service.supabase_request', return_value={'equipment_request': row}) as query:
        response = client.post('/api/equipment-request-reviews/1', json={
            'outcome': outcome, 'equipment_id': 10, 'accepted_quantity': amount, 'reason': 'Not suitable',
        })
        assert response.status_code == 200
        assert response.json['equipment_request']['quantity'] == 5
        assert query.call_args.args[0] == '/rest/v1/rpc/review_equipment_request'
        assert query.call_args.kwargs['payload']['p_accepted_quantity'] == amount
        assert query.call_args.kwargs['token'] == 'user-token'


@pytest.mark.parametrize('status', [403, 404, 409])
def test_database_rejection_is_preserved(client, auth, status):
    with patch('app.services.equipment_review_service.supabase_request', return_value={'error': 'Cannot review', 'status': status}):
        response = client.post('/api/equipment-request-reviews/1', json={'outcome': 'accepted', 'equipment_id': 10})
        assert response.status_code == status
        assert response.json['error'] == 'Cannot review'


def test_queue_uses_account_scoped_events_including_empty_events(client, auth):
    with patch('app.routes.equipment.supabase_request', side_effect=[[{'event_id': 2, 'event_name': 'Workshop'}], [], [{'event_id': '2', 'event_name': 'Workshop'}, {'event_id': '3', 'event_name': 'Empty event'}]]) as query:
        response = client.get('/api/equipment-request-reviews')
        assert response.status_code == 200
        assert response.json['equipment_requests'][0]['event_name'] == 'Workshop'
        assert len(response.json['events']) == 2
        assert query.call_args_list[2].args[0] == '/rest/v1/rpc/my_equipment_request_events'
        assert query.call_args_list[0].args[0] == '/rest/v1/rpc/equipment_request_review_queue'
        assert query.call_args_list[0].kwargs['token'] == 'user-token'
