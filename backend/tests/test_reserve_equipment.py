"""Reserve Equipment HTTP contracts; overlap/concurrency require PostgreSQL."""
from unittest.mock import patch
import pytest
from app import create_app


@pytest.fixture
def client():
    return create_app().test_client()


# Lists only events supplied by the authenticated Technical Support RPC.
def test_assigned_events_use_authenticated_rpc(client):
    with patch('app.routes.equipment.authenticated_token', return_value='tech-token'), \
         patch('app.routes.equipment.supabase_request', return_value=[{'event_id': '1', 'event_name': 'Conference'}]) as query:
        response = client.get('/api/equipment/reservable-events')
    assert response.status_code == 200
    assert response.json['events'][0]['event_id'] == '1'
    query.assert_called_once_with('/rest/v1/rpc/reservable_equipment_events', token='tech-token', payload={})


# Records a successful reservation against the selected event and equipment item.
def test_reservation_is_recorded_against_selected_event(client):
    saved = {'event_id': '1', 'equipment_id': 10, 'quantity': 2, 'reservation_id': 'saved'}
    with patch('app.routes.equipment.authenticated_token', return_value='tech-token'), \
         patch('app.routes.equipment.supabase_request', return_value={'reservation': saved, 'message': 'Equipment reserved successfully.'}) as query:
        response = client.post('/api/equipment/reservations', json={'event_id': '1', 'equipment_id': '10', 'quantity': 2})
    assert response.status_code == 201
    assert response.json['reservation'] == saved
    query.assert_called_once_with('/rest/v1/rpc/reserve_equipment', token='tech-token', payload={'p_event_id': '1', 'p_equipment_id': 10, 'p_quantity': 2})


# Rejects zero, negative, non-integer, and out-of-range reservation quantities.
@pytest.mark.parametrize('quantity', [0, -1, True, 1.5, '2', None, 2147483648])
def test_invalid_quantity_never_reserves(client, quantity):
    with patch('app.routes.equipment.authenticated_token', return_value='tech-token'), patch('app.routes.equipment.supabase_request') as query:
        response = client.post('/api/equipment/reservations', json={'event_id': '1', 'equipment_id': '10', 'quantity': quantity})
    assert response.status_code == 400
    query.assert_not_called()


# Displays stock and assignment errors returned by the reservation service.
@pytest.mark.parametrize(
    'status,message,available_quantity',
    [
        (409, 'Insufficient equipment: only 1 available for this event.', 1),
        (403, 'Only the assigned Technical Support Staff can reserve equipment for this event.', None),
    ],
)
def test_database_stock_or_assignment_rejection_is_displayed(client, status, message, available_quantity):
    result = {'error': message, 'status': status}
    if available_quantity is not None:
        result['available_quantity'] = available_quantity
    with patch('app.routes.equipment.authenticated_token', return_value='tech-token'), \
         patch('app.routes.equipment.supabase_request', return_value=result):
        response = client.post('/api/equipment/reservations', json={'event_id': '1', 'equipment_id': '10', 'quantity': 2})
    assert response.status_code == status
    assert response.json['error'] == message
    if available_quantity is not None:
        assert response.json['available_quantity'] == available_quantity


# Requires authentication for assigned events and reservation creation.
def test_login_required(client):
    assert client.get('/api/equipment/reservable-events').status_code == 401
    assert client.post('/api/equipment/reservations', json={}).status_code == 401


# Prevents non-Technical Support users from viewing reservable events.
def test_nontechnical_staff_cannot_list_reservable_events(client):
    with patch('app.routes.equipment.authenticated_token', return_value='organiser-token'), \
         patch('app.routes.equipment.supabase_request', return_value={
             'error': 'Only Technical Support Staff can reserve equipment.', 'status': 403}):
        response = client.get('/api/equipment/reservable-events')
    assert response.status_code == 403
    assert 'events' not in response.json
