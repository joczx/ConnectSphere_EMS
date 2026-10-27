"""Run from backend: python send_registration_emails.py (schedule every minute)."""
from app.services.registration_email_service import send_pending_emails


if __name__ == '__main__':
    print(f'Sent {send_pending_emails()} registration emails.')
