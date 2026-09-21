"""HTTP contract tests; database overlap tests live in equipment_overlap.sql."""
from unittest.mock import patch
import pytest
from app import create_app

EQUIPMENT_ID = '10'


@pytest.fixture
def client():
    return create_app().test_client()


@pytest.mark.parametrize('quantity', [0, -1, 1.5, True, '2', None, 2147483648])
def test_invalid_quantity_never_reserves(client, quantity):
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request') as rpc:
        response = client.post('/api/equipment/reservations', json={
            'event_id': '1', 'equipment_id': EQUIPMENT_ID, 'quantity': quantity,
        })
    assert response.status_code == 400
    rpc.assert_not_called()


@pytest.mark.parametrize('payload', [[], None, {}, {'event_id': '1', 'equipment_id': 'bad', 'quantity': 1}])
def test_bad_request(client, payload):
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request') as rpc:
        assert client.post('/api/equipment/reservations', json=payload).status_code == 400
    rpc.assert_not_called()


def test_success_passes_user_token_without_role_check(client):
    with patch('app.routes.equipment.authenticated_token', return_value='ordinary-user-token'), patch('app.routes.equipment.supabase_request', return_value={'reservation': {'quantity': 2}}) as rpc:
        result = client.post('/api/equipment/reservations', json={'event_id': '1', 'equipment_id': EQUIPMENT_ID, 'quantity': 2})
    assert result.status_code == 201
    assert result.json['reservation']['quantity'] == 2
    assert rpc.call_args.kwargs == {'token': 'ordinary-user-token', 'payload': {
        'p_event_id': '1', 'p_equipment_id': int(EQUIPMENT_ID), 'p_quantity': 2,
    }}


def test_conflict_displays_database_availability(client):
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request', return_value={'error': 'Insufficient equipment: only 1 available for this event.', 'available_quantity': 1}):
        result = client.post('/api/equipment/reservations', json={'event_id': '1', 'equipment_id': EQUIPMENT_ID, 'quantity': 2})
    assert result.status_code == 409
    assert result.json['available_quantity'] == 1
    assert 'only 1' in result.json['error']


def test_sign_in_required(client):
    assert client.get('/api/equipment/events').status_code == 401
    assert client.post('/api/equipment/reservations', json={}).status_code == 401


def test_availability_requires_event(client):
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request') as rpc:
        assert client.get('/api/equipment/availability').status_code == 400
    rpc.assert_not_called()


def test_availability_and_invalid_dates(client):
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request', side_effect=[{'equipment': []}, {'error': 'Set a valid event start and end time before reserving equipment.'}]):
        response = client.get('/api/equipment/availability?event_id=1')
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store'
        assert client.get('/api/equipment/availability?event_id=2').status_code == 400


def test_event_picker_uses_existing_events_table(client):
    rows = [{'event_id': 1, 'event_name': 'Workshop'}]
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request', return_value=rows) as rpc:
        response = client.get('/api/equipment/events')
    assert response.status_code == 200
    assert response.json == {'events': rows}
    assert rpc.call_args.args[0].startswith('/rest/v1/events?')


def test_missing_migration_returns_actionable_json(client):
    from app.services.event_store import StoreError
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request', side_effect=StoreError(503, code='PGRST202')):
        response = client.get('/api/equipment/availability?event_id=1')
    assert response.status_code == 503
    assert 'not configured' in response.json['error']
