"""Reserve Equipment HTTP contracts; overlap/concurrency require PostgreSQL."""
from unittest.mock import patch
import pytest
from app import create_app


@pytest.fixture
def client():
    return create_app().test_client()


def test_assigned_events_use_authenticated_rpc(client):
    with patch('app.routes.equipment.authenticated_token', return_value='tech-token'), \
         patch('app.routes.equipment.supabase_request', return_value=[{'event_id': '1', 'event_name': 'Conference'}]) as query:
        response = client.get('/api/equipment/reservable-events')
    assert response.status_code == 200
    assert response.json['events'][0]['event_id'] == '1'
    query.assert_called_once_with('/rest/v1/rpc/reservable_equipment_events', token='tech-token', payload={})


def test_reservation_is_recorded_against_selected_event(client):
    saved = {'event_id': '1', 'equipment_id': 10, 'quantity': 2, 'reservation_id': 'saved'}
    with patch('app.routes.equipment.authenticated_token', return_value='tech-token'), \
         patch('app.routes.equipment.supabase_request', return_value={'reservation': saved, 'message': 'Equipment reserved successfully.'}) as query:
        response = client.post('/api/equipment/reservations', json={'event_id': '1', 'equipment_id': '10', 'quantity': 2})
    assert response.status_code == 201
    assert response.json['reservation'] == saved
    query.assert_called_once_with('/rest/v1/rpc/reserve_equipment', token='tech-token', payload={'p_event_id': '1', 'p_equipment_id': 10, 'p_quantity': 2})


@pytest.mark.parametrize('quantity', [0, -1, True, 1.5, '2', None])
def test_invalid_quantity_never_reserves(client, quantity):
    with patch('app.routes.equipment.authenticated_token', return_value='tech-token'), patch('app.routes.equipment.supabase_request') as query:
        response = client.post('/api/equipment/reservations', json={'event_id': '1', 'equipment_id': '10', 'quantity': quantity})
    assert response.status_code == 400
    query.assert_not_called()


@pytest.mark.parametrize('status,message', [(409, 'Insufficient equipment: only 1 available for this event.'), (403, 'Only the assigned Technical Support Staff can reserve equipment for this event.')])
def test_database_stock_or_assignment_rejection_is_displayed(client, status, message):
    with patch('app.routes.equipment.authenticated_token', return_value='tech-token'), \
         patch('app.routes.equipment.supabase_request', return_value={'error': message, 'status': status}):
        response = client.post('/api/equipment/reservations', json={'event_id': '1', 'equipment_id': '10', 'quantity': 2})
    assert response.status_code == status
    assert response.json['error'] == message


def test_login_required(client):
    assert client.get('/api/equipment/reservable-events').status_code == 401
    assert client.post('/api/equipment/reservations', json={}).status_code == 401
