"""Unit tests for attendee registration with personal/contact details and email.

Covers input validation, authenticated submission, refusal responses and SMTP
confirmation delivery/retry. Actual registration-window and capacity enforcement
is verified separately by frontend/tests/registration-db.mjs.
"""
from unittest.mock import patch

import pytest

from app import create_app
from app.schemas.registration import parse_attendee
from app.services.event_service import EventError
from app.services.event_store import StoreError
from app.services.registration_service import registration_call
from app.services.registration_email_service import send_pending_emails


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



@pytest.fixture
def mail_config(monkeypatch):
    for key, value in {'SUPABASE_SERVICE_ROLE_KEY': 'server-secret', 'SMTP_HOST': 'smtp.example.com',
                       'SMTP_USERNAME': 'sender', 'SMTP_PASSWORD': 'secret', 'SMTP_FROM': 'events@example.com'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('SMTP_PORT', raising=False)



def test_sender_requires_configuration(monkeypatch):
    monkeypatch.delenv('SMTP_HOST', raising=False)
    with pytest.raises(ValueError, match='Configure'):
        send_pending_emails()



def test_empty_queue_does_not_connect_to_smtp(mail_config):
    with patch('app.services.registration_email_service.supabase_request', return_value=[]), \
         patch('app.services.registration_email_service.smtplib.SMTP') as smtp:
        assert send_pending_emails() == 0
    smtp.assert_not_called()



def queued_email():
    return {'id': 1, 'recipient': 'alex@example.com', 'subject': 'Event registration confirmed',
            'body': 'Your registration is confirmed for Conference.'}



def test_sender_delivers_confirmation_and_marks_it_sent(mail_config):
    with patch('app.services.registration_email_service.supabase_request', side_effect=[[queued_email()], []]) as rpc, \
         patch('app.services.registration_email_service.smtplib.SMTP') as smtp:
        assert send_pending_emails() == 1
    smtp.assert_called_once_with('smtp.example.com', 587, timeout=15)
    connection = smtp.return_value.__enter__.return_value
    connection.starttls.assert_called_once()
    connection.login.assert_called_once_with('sender', 'secret')
    message = connection.send_message.call_args.args[0]
    assert message['To'] == 'alex@example.com'
    assert message['Subject'] == 'Event registration confirmed'
    assert 'Your registration is confirmed' in message.get_content()
    assert rpc.call_args.kwargs['method'] == 'PATCH'
    assert rpc.call_args.kwargs['token'] == 'server-secret'
    assert rpc.call_args.kwargs['payload']['sent_at']



def test_email_failure_leaves_notification_pending_for_retry(mail_config):
    with patch('app.services.registration_email_service.supabase_request', return_value=[queued_email()]) as rpc, \
         patch('app.services.registration_email_service.smtplib.SMTP') as smtp:
        smtp.return_value.__enter__.return_value.send_message.side_effect = OSError('SMTP unavailable')
        with pytest.raises(OSError, match='SMTP unavailable'):
            send_pending_emails()
    assert rpc.call_count == 1  # Never marks an undelivered email as sent.

