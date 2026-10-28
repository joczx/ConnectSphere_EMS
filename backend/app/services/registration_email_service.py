"""Deliver persisted registration notifications. Run one sender at a time."""
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage

from app.services.event_store import supabase_request


def send_pending_emails():
    required = ('SUPABASE_SERVICE_ROLE_KEY', 'SMTP_HOST', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'SMTP_FROM')
    if any(not os.environ.get(name) for name in required):
        raise ValueError('Configure the service role key and SMTP settings before sending registration emails.')
    token = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    pending = supabase_request('/rest/v1/registration_email_outbox?sent_at=is.null&order=id&limit=100', token=token)
    delivered = 0
    for item in pending:
        message = EmailMessage()
        message['From'] = os.environ['SMTP_FROM']
        message['To'] = item['recipient']
        message['Subject'] = item['subject']
        message['Message-ID'] = f"<registration-{item['id']}@{os.environ['SMTP_FROM'].split('@')[-1]}>"
        message.set_content(item['body'])
        # Require encrypted SMTP; delivery errors leave the row pending for retry.
        with smtplib.SMTP(os.environ['SMTP_HOST'], int(os.environ.get('SMTP_PORT', '587')), timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(os.environ['SMTP_USERNAME'], os.environ['SMTP_PASSWORD'])
            smtp.send_message(message)
        supabase_request(f"/rest/v1/registration_email_outbox?id=eq.{item['id']}", token=token,
                         method='PATCH', payload={'sent_at': datetime.now(timezone.utc).isoformat()})
        delivered += 1
    return delivered
