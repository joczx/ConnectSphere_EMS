from unittest.mock import patch

import pytest
from app import create_app
from app.schemas.registration import parse_settings


def settings(**changes):
    return {'registration_opens_at': '2027-01-01T10:00:00+08:00',
            'registration_closes_at': '2027-01-02T10:00:00+08:00',
            'waiting_list_enabled': True, **changes}


@pytest.mark.parametrize('changes', [
    {'registration_closes_at': '2027-01-01T02:00:00Z'},
    {'registration_closes_at': '2026-12-31T00:00:00Z'},
    {'registration_opens_at': '2027-01-01T10:00'},
    {'registration_opens_at': None}, {'registration_closes_at': 'invalid'},
    {'waiting_list_enabled': 'true'}, {'waiting_list_enabled': 1},
    {'status': 'confirmed'},
])
def test_invalid_settings(changes):
    assert parse_settings(settings(**changes))[1]


def test_timezone_and_fractional_second_ordering():
    record, errors = parse_settings(settings(registration_closes_at='2027-01-01T02:00:00.100Z'))
    assert not errors
    assert record['registration_opens_at'] == '2027-01-01T02:00:00+00:00'


@pytest.mark.parametrize('method,path', [
    ('patch', '/api/events/1/registration-period'),
    ('get', '/api/registration-events'), ('post', '/api/events/1/registrations'),
])
def test_registration_requires_authentication(method, path):
    client = create_app().test_client()
    with patch('app.services.registration_service.supabase_request') as rpc:
        assert getattr(client, method)(path).status_code == 401
        rpc.assert_not_called()


def test_settings_pass_verified_token_and_not_client_identity():
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.services.registration_service.supabase_request', return_value={'event': {'event_id': 1}}) as rpc:
        response = client.patch('/api/events/1/registration-period', json=settings(),
                                headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert rpc.call_args.kwargs['token'] == 'verified'
    assert rpc.call_args.kwargs['payload']['p_event_id'] == 1


@pytest.mark.parametrize('status,message', [
    (409, 'Registration has closed.'),
    (403, 'Only attendees can register for events.'),
])
def test_registration_refusal_is_returned_to_attendee(status, message):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value={'error': message, 'status': status}):
        response = client.post('/api/events/1/registrations', headers={'Authorization': 'Bearer attendee'})
    assert response.status_code == status
    assert response.json['error'] == message
