from unittest.mock import patch

import pytest

from app import create_app

RESERVATION_ID = '00000000-0000-0000-0000-000000000010'
PATH = '/api/equipment/reservations/' + RESERVATION_ID


@pytest.fixture
def client():
    return create_app().test_client()


def test_list_uses_verified_token_without_client_owner_filter(client):
    rows = [{'reservation_id': RESERVATION_ID, 'quantity': 3}]
    with patch('app.routes.equipment.authenticated_token', return_value='owner-token'), patch('app.routes.equipment.supabase_request', return_value=rows) as rpc:
        response = client.get('/api/equipment/reservations?created_by=someone-else')
    assert response.status_code == 200
    assert response.json == {'reservations': rows}
    rpc.assert_called_once_with('/rest/v1/rpc/my_equipment_reservations', token='owner-token', payload={})


@pytest.mark.parametrize('quantity', [None, True, 0, -1, 1.5, '2', 2147483648])
def test_bad_quantity_never_reaches_database(client, quantity):
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request') as rpc:
        response = client.patch(PATH, json={'quantity': quantity})
    assert response.status_code == 400
    rpc.assert_not_called()


@pytest.mark.parametrize('method', ['PATCH', 'DELETE'])
def test_invalid_id_never_reaches_database(client, method):
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request') as rpc:
        response = client.open('/api/equipment/reservations/bad', method=method, json={'quantity': 2})
    assert response.status_code == 400
    rpc.assert_not_called()


@pytest.mark.parametrize('quantity', [1, 5])
def test_update_forwards_replacement_quantity_and_token(client, quantity):
    with patch('app.routes.equipment.authenticated_token', return_value='owner-token'), patch('app.routes.equipment.supabase_request', return_value={'reservation': {'quantity': quantity}}) as rpc:
        response = client.patch(PATH, json={'quantity': quantity, 'created_by': 'someone-else'})
    assert response.status_code == 200
    rpc.assert_called_once_with('/rest/v1/rpc/update_equipment_reservation', token='owner-token', payload={
        'p_reservation_id': RESERVATION_ID, 'p_quantity': quantity,
    })


@pytest.mark.parametrize('status,message', [(404, 'Reservation not found or access unavailable.'), (409, 'Insufficient equipment: you can reserve at most 3 for this event.')])
def test_database_rejection_is_displayable(client, status, message):
    with patch('app.routes.equipment.authenticated_token', return_value='token'), patch('app.routes.equipment.supabase_request', return_value={'error': message, 'status': status}):
        response = client.patch(PATH, json={'quantity': 5})
    assert response.status_code == status
    assert response.json['error'] == message


def test_cancel_calls_owner_checked_rpc(client):
    with patch('app.routes.equipment.authenticated_token', return_value='owner-token'), patch('app.routes.equipment.supabase_request', return_value={'cancelled': True}) as rpc:
        response = client.delete(PATH)
    assert response.status_code == 200
    assert response.json['cancelled']
    rpc.assert_called_once_with('/rest/v1/rpc/cancel_equipment_reservation', token='owner-token', payload={'p_reservation_id': RESERVATION_ID})


def test_management_requires_login(client):
    assert client.get('/api/equipment/reservations').status_code == 401
    assert client.patch(PATH, json={'quantity': 2}).status_code == 401
    assert client.delete(PATH).status_code == 401
