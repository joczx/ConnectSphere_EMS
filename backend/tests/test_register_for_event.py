"""Unit tests for attendee registration with personal/contact details.

Covers input validation, authenticated submission and refusal responses. Actual
registration-window and capacity enforcement is verified separately by
frontend/tests/registration-db.mjs.
"""
from unittest.mock import patch

import pytest

from app import create_app
from app.schemas.registration import parse_attendee
from app.services.event_service import EventError
from app.services.event_store import StoreError
from app.services.registration_service import registration_call


def test_attendee_registration_requires_authentication():
    client = create_app().test_client()
    with patch('app.services.registration_service.supabase_request') as rpc:
        assert client.post('/api/events/1/registrations').status_code == 401
        rpc.assert_not_called()


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



def attendee_details(**changes):
    return {'full_name': 'Alex Tan', 'contact_email': 'alex@example.com', 'contact_phone': '+65 8123 4567', **changes}



@pytest.mark.parametrize('payload', [None, {}, [], attendee_details(full_name=' '),
    attendee_details(full_name=123), attendee_details(full_name='a' * 151),
    attendee_details(full_name='Alex\nTan'), attendee_details(contact_email=' '),
    attendee_details(contact_email='alex@example.com\r\nBcc: other@example.com'),
    attendee_details(contact_phone='letters'), attendee_details(contact_phone='-------')])
def test_mandatory_personal_details_are_validated(payload):
    assert parse_attendee(payload)[1]



def test_personal_details_are_trimmed():
    record, errors = parse_attendee(attendee_details(full_name=' Alex Tan '))
    assert not errors
    assert record == attendee_details()


def test_contact_email_format_is_not_validated():
    record, errors = parse_attendee(attendee_details(contact_email='not-an-email'))
    assert not errors
    assert record['contact_email'] == 'not-an-email'



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

