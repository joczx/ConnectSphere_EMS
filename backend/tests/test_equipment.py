"""HTTP contract tests; database overlap tests live in equipment_overlap.sql."""
from unittest.mock import patch
import pytest
from app import create_app

EQUIPMENT_ID = '10'


@pytest.fixture
def client():
    return create_app().test_client()


# Rejects malformed reservation payloads before any database call is made.
@pytest.mark.parametrize('payload', [[], None, {}, {'event_id': '1', 'equipment_id': 'bad', 'quantity': 1}])
def test_bad_request(client, payload):
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request') as rpc:
        assert client.post('/api/equipment/reservations', json=payload).status_code == 400
    rpc.assert_not_called()


# Requires authentication before listing events for equipment work.
def test_sign_in_required(client):
    assert client.get('/api/equipment/events').status_code == 401


# Requires an event selection before checking event-specific availability.
def test_availability_requires_event(client):
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request') as rpc:
        assert client.get('/api/equipment/availability').status_code == 400
    rpc.assert_not_called()


# Returns availability results and forwards invalid event-date errors from the database.
def test_availability_and_invalid_dates(client):
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request', side_effect=[{'equipment': []}, {'error': 'Set a valid event start and end time before reserving equipment.'}]):
        response = client.get('/api/equipment/availability?event_id=1')
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store'
        assert client.get('/api/equipment/availability?event_id=2').status_code == 400


# Lists events from the existing events source for the equipment event picker.
def test_event_picker_uses_existing_events_table(client):
    rows = [{'event_id': 1, 'event_name': 'Workshop'}]
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request', return_value=rows) as rpc:
        response = client.get('/api/equipment/events')
    assert response.status_code == 200
    assert response.json == {'events': rows}
    assert rpc.call_args.args[0].startswith('/rest/v1/events?')


# Explains that equipment database configuration is missing when the RPC cannot be found.
def test_missing_migration_returns_actionable_json(client):
    from app.services.event_store import StoreError
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request', side_effect=StoreError(503, code='PGRST202')):
        response = client.get('/api/equipment/availability?event_id=1')
    assert response.status_code == 503
    assert 'not configured' in response.json['error']


# Requires a bearer token and returns distinct equipment types in alphabetical order.
def test_equipment_types_require_bearer_token_and_return_sorted_unique_values(client):
    assert client.get('/api/equipment-types').status_code == 401
    rows = [
        {'equipment_type': 'Projector'}, {'equipment_type': 'Microphone'},
        {'equipment_type': 'Projector'}, {'equipment_type': ''},
    ]
    with patch('app.routes.equipment.supabase_request', return_value=rows) as rpc:
        response = client.get('/api/equipment-types', headers={'Authorization': 'Bearer catalogue-token'})
    assert response.status_code == 200
    assert response.json == {'equipment_types': ['Microphone', 'Projector']}
    rpc.assert_called_once_with('/rest/v1/equipment?select=equipment_type', token='catalogue-token')


# Identifies the availability migration needed for an incompatible database function.
def test_availability_schema_error_identifies_availability_repair(client):
    from app.services.event_store import StoreError
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request', side_effect=StoreError(503, code='42883')):
        response = client.get('/api/equipment/availability?event_id=7')
    assert response.status_code == 503
    assert '034_equipment_availability_event_ids.sql' in response.json['error']


# Identifies the reservation migration needed for an incompatible database function.
def test_reservation_schema_error_identifies_write_repair(client):
    from app.services.event_store import StoreError
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request', side_effect=StoreError(503, code='42883')):
        response = client.post('/api/equipment/reservations', json={'event_id': '7', 'equipment_id': '1', 'quantity': 1})
    assert response.status_code == 503
    assert '035_reserve_equipment_event_ids.sql' in response.json['error']
