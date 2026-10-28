from unittest.mock import patch

import pytest

from app.services.registration_email_service import send_pending_emails


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
