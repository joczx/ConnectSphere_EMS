"""Unit tests for attendee registration with personal/contact details.

Covers input validation, authenticated submission and refusal responses.
Actual registration-window and capacity enforcement
is verified separately by frontend/tests/registration-db.mjs.
"""
from unittest.mock import patch

import pytest

from app import create_app
from app.schemas.registration import parse_attendee
from app.services.event_service import EventError
from app.services.event_store import StoreError
from app.services.registration_email_service import send_pending_emails
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


def test_registration_refusal_without_status_uses_default_and_preserves_field_errors():
    errors = {'event_id': 'Registration unavailable.'}
    with patch('app.services.registration_service.supabase_request',
               return_value={'error': 'Cannot register.', 'errors': errors}):
        with pytest.raises(EventError) as caught:
            registration_call('register_for_event', 'verified', {'p_event_id': 1})
    assert caught.value.status == 400
    assert caught.value.to_dict() == {'error': 'Cannot register.', 'errors': errors}


def test_registration_service_preserves_non_object_store_result():
    with patch('app.services.registration_service.supabase_request', return_value=[]) as query:
        assert registration_call('register_for_event', 'verified', {'p_event_id': 1}) == []
    query.assert_called_once_with('/rest/v1/rpc/register_for_event', token='verified',
                                 payload={'p_event_id': 1}, method='POST')


@pytest.mark.parametrize('error,expected_status', [
    (StoreError(409, code='23514'), 409),
    (StoreError(401), 401),
    (StoreError(503), 503),
])
def test_registration_store_failures_return_safe_api_errors(error, expected_status):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', side_effect=error):
        response = client.post('/api/events/1/registrations', json=attendee_details(),
                               headers={'Authorization': 'Bearer verified'})
    assert response.status_code == expected_status
    assert 'error' in response.json
    assert 'registration' not in response.json



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
    result = {'registration': {'status': 'registered'}}
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value=result) as rpc:
        response = client.post('/api/events/1/registrations', json=attendee_details(), headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == result
    rpc.assert_called_once_with('/rest/v1/rpc/register_for_event', token='verified', method='POST',
        payload={'p_event_id': 1, **{'p_' + k: v for k, v in attendee_details().items()}})


@pytest.fixture
def mail_config(monkeypatch):
    for key, value in {'SUPABASE_SERVICE_ROLE_KEY': 'server-secret', 'SMTP_HOST': 'smtp.example.com',
                       'SMTP_USERNAME': 'sender', 'SMTP_PASSWORD': 'secret', 'SMTP_FROM': 'events@example.com'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('SMTP_PORT', raising=False)


def test_registration_email_sender_requires_configuration(mail_config, monkeypatch):
    """TC-SCRUM33-026 / AC5: the confirmation sender refuses to run without
    its SMTP settings rather than silently dropping registration emails."""
    monkeypatch.delenv('SMTP_HOST')
    with patch('app.services.registration_email_service.supabase_request') as rpc:
        with pytest.raises(ValueError, match='Configure'):
            send_pending_emails()
    rpc.assert_not_called()


def test_registration_email_is_sent_and_marked_sent(mail_config):
    """TC-SCRUM33-027 / AC5: a queued registration confirmation is emailed to
    the attendee over STARTTLS and then marked sent, so it is not sent again."""
    queued = {'id': 1, 'recipient': 'alex@example.com', 'subject': 'Event registration confirmed',
              'body': 'Your registration is confirmed for Conference.'}
    with patch('app.services.registration_email_service.supabase_request', side_effect=[[queued], []]) as rpc, \
         patch('app.services.registration_email_service.smtplib.SMTP') as smtp:
        assert send_pending_emails() == 1
    smtp.assert_called_once_with('smtp.example.com', 587, timeout=15)
    connection = smtp.return_value.__enter__.return_value
    connection.starttls.assert_called_once()
    connection.login.assert_called_once_with('sender', 'secret')
    message = connection.send_message.call_args.args[0]
    assert (message['To'], message['Subject']) == ('alex@example.com', 'Event registration confirmed')
    assert 'Your registration is confirmed' in message.get_content()
    assert rpc.call_args.args == ('/rest/v1/registration_email_outbox?id=eq.1',)
    assert rpc.call_args.kwargs['method'] == 'PATCH' and rpc.call_args.kwargs['payload']['sent_at']
