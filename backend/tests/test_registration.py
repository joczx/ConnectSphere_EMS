from unittest.mock import patch

import pytest
from app import create_app
from app.schemas.registration import parse_settings, parse_attendee
from app.services.event_service import EventError
from app.services.event_store import StoreError
from app.services.registration_service import registration_call


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
    ('post', '/api/events/1/registrations/withdraw'),
    ('get', '/api/my-registrations'),
    ('get', '/api/events/1/registrations'),
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
        response = client.post('/api/events/1/registrations', json=attendee_details(), headers={'Authorization': 'Bearer attendee'})
    assert response.status_code == status
    assert response.json['error'] == message


def test_missing_database_function_has_actionable_configuration_error():
    failure = StoreError(503, code='PGRST202')
    with patch('app.services.registration_service.supabase_request', side_effect=failure):
        with pytest.raises(EventError) as caught:
            registration_call('register_for_event', 'verified', {'p_event_id': 1})
    assert caught.value.status == 503
    assert '046_event_registration.sql' in caught.value.to_dict()['error']
    assert caught.value.__cause__ is failure


def test_other_database_errors_are_preserved():
    failure = StoreError(403, 'Access denied.', code='42501')
    with patch('app.services.registration_service.supabase_request', side_effect=failure):
        with pytest.raises(StoreError) as caught:
            registration_call('register_for_event', 'verified', {'p_event_id': 1})
    assert caught.value is failure


def test_database_refusal_without_status_defaults_to_bad_request():
    with patch('app.services.registration_service.supabase_request', return_value={'error': 'Invalid period.'}):
        with pytest.raises(EventError) as caught:
            registration_call('set_event_registration_period', 'verified', {})
    assert caught.value.status == 400
    assert caught.value.to_dict()['error'] == 'Invalid period.'


def test_registration_period_field_errors_are_returned_to_the_organiser():
    client = create_app().test_client()
    error = {'error': 'Registration must close before the event starts.', 'status': 400,
             'errors': {'registration_closes_at': 'Registration must close before the event starts.'}}
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.services.registration_service.supabase_request', return_value=error):
        response = client.patch('/api/events/1/registration-period', json=settings(),
                                headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 400
    assert response.json['errors'] == error['errors']


def test_invalid_period_is_rejected_before_database_call():
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.services.registration_service.supabase_request') as rpc:
        response = client.patch('/api/events/1/registration-period',
                                json=settings(registration_closes_at='2026-12-31T00:00:00Z'),
                                headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 400
    assert 'registration_closes_at' in response.json['errors']
    rpc.assert_not_called()


def test_attendee_information_returns_updated_period_and_disables_caching():
    client = create_app().test_client()
    event = {'event_id': 1, **settings(), 'registration_status': 'not_open'}
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value={'events': [event]}) as rpc:
        response = client.get('/api/registration-events', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == {'events': [event]}
    assert response.headers['Cache-Control'] == 'no-store'
    rpc.assert_called_once_with('/rest/v1/rpc/attendee_registration_events',
                                token='verified', payload={}, method='POST')


def attendee_details(**changes):
    return {'full_name': 'Alex Tan', 'contact_email': 'alex@example.com', 'contact_phone': '+65 8123 4567', **changes}


@pytest.mark.parametrize('payload', [None, {}, [], attendee_details(full_name=' '),
    attendee_details(full_name=123), attendee_details(full_name='a' * 151),
    attendee_details(full_name='Alex\nTan'), attendee_details(contact_email='bad'),
    attendee_details(contact_email='alex@example.com\r\nBcc: other@example.com'),
    attendee_details(contact_phone='letters'), attendee_details(contact_phone='-------')])
def test_mandatory_personal_details_are_validated(payload):
    assert parse_attendee(payload)[1]


def test_personal_details_are_trimmed():
    record, errors = parse_attendee(attendee_details(full_name=' Alex Tan '))
    assert not errors
    assert record == attendee_details()


def test_invalid_attendee_details_never_reach_database():
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request') as rpc:
        response = client.post('/api/events/1/registrations', json={}, headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 400
    assert response.json['errors']
    rpc.assert_not_called()


def test_registration_submits_details_using_authenticated_identity():
    client = create_app().test_client()
    result = {'registration': {'status': 'registered'}, 'notification': 'queued'}
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value=result) as rpc:
        response = client.post('/api/events/1/registrations', json=attendee_details(), headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == result
    rpc.assert_called_once_with('/rest/v1/rpc/register_for_event', token='verified', method='POST',
        payload={'p_event_id': 1, **{'p_' + k: v for k, v in attendee_details().items()}})


def test_withdrawal_uses_verified_identity_and_returns_confirmation_and_capacity():
    client = create_app().test_client()
    result = {'registration': {'status': 'withdrawn'}, 'available_capacity': 1,
              'message': 'Your registration has been successfully withdrawn.'}
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value=result) as rpc:
        response = client.post('/api/events/1/registrations/withdraw',
            json={'attendee_id': 'someone-else'}, headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == result
    rpc.assert_called_once_with('/rest/v1/rpc/withdraw_event_registration', token='verified',
                               payload={'p_event_id': 1}, method='POST')


@pytest.mark.parametrize('status,message', [
    (403, 'Only attendees can withdraw registrations.'),
    (404, 'Registration not found.'),
    (409, 'Registration cannot be withdrawn at or after the event start time.'),
])
def test_withdrawal_refusals_are_returned_unchanged(status, message):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value={'error': message, 'status': status}):
        response = client.post('/api/events/1/registrations/withdraw', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == status
    assert response.json['error'] == message


@pytest.mark.parametrize('records', [[], [
    {'event_id': 1, 'event_name': 'Conference', 'status': 'registered', 'venues': ['Hall']},
    {'event_id': 2, 'event_name': 'Workshop', 'status': 'waiting_list', 'venues': []},
    {'event_id': 3, 'event_name': 'Talk', 'status': 'withdrawn', 'venues': []},
]])
def test_my_registrations_returns_only_the_verified_users_rpc_result(records):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value={'registrations': records}) as rpc:
        response = client.get('/api/my-registrations?attendee_id=someone-else', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == {'registrations': records}
    assert response.headers['Cache-Control'] == 'no-store'
    rpc.assert_called_once_with('/rest/v1/rpc/my_event_registrations', token='verified', payload={}, method='POST')


def test_event_roster_passes_verified_token_and_event_id_only():
    result = {'event': {'event_id': 1, 'event_name': 'Conference'}, 'total_registered': 1,
              'total_waitlisted': 0, 'total_withdrawn': 0, 'registrations': [attendee_details(status='registered')]}
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.services.registration_service.supabase_request', return_value=result) as rpc:
        response = client.get('/api/events/1/registrations?event_organiser_id=someone-else',
                              headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == result
    assert response.headers['Cache-Control'] == 'no-store'
    rpc.assert_called_once_with('/rest/v1/rpc/event_registration_roster', token='verified',
                               payload={'p_event_id': 1}, method='POST')


@pytest.mark.parametrize('status', [403, 404])
def test_unauthorised_roster_response_contains_no_attendee_details(status):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'unassigned'}), \
         patch('app.services.registration_service.supabase_request', return_value={'error': 'Access unavailable.', 'status': status}):
        response = client.get('/api/events/1/registrations', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == status
    assert response.json == {'error': 'Access unavailable.'}
