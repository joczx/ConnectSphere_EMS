"""Registration settings use explicit, timezone-aware instants."""
from datetime import datetime, timezone
import re


def parse_attendee(payload):
    fields = {'full_name': 150, 'contact_email': 254, 'contact_phone': 30}
    if not isinstance(payload, dict) or set(payload) != set(fields):
        return {}, {'_body': 'Provide your full name, contact email and phone number.'}
    record, errors = {}, {}
    for field, limit in fields.items():
        value = payload[field]
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            errors[field] = f'Enter a value between 1 and {limit} characters.'
        else:
            record[field] = value.strip()
    if 'full_name' in record and any(ord(char) < 32 for char in record['full_name']):
        errors['full_name'] = 'Enter a valid full name.'
    if 'contact_email' in record and not re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+', record['contact_email']):
        errors['contact_email'] = 'Enter a valid email address.'
    if 'contact_phone' in record and not re.fullmatch(r'\+?[0-9 ()-]{7,30}', record['contact_phone']):
        errors['contact_phone'] = 'Enter a valid phone number.'
    elif 'contact_phone' in record and len(re.sub(r'\D', '', record['contact_phone'])) < 7:
        errors['contact_phone'] = 'Enter a valid phone number.'
    return record, errors


def parse_settings(payload):
    fields = {'registration_opens_at', 'registration_closes_at', 'waiting_list_enabled'}
    if not isinstance(payload, dict) or set(payload) != fields:
        return {}, {'_body': 'Provide opening time, closing time and waiting list preference.'}
    record, errors = {}, {}
    for field in ('registration_opens_at', 'registration_closes_at'):
        try:
            value = payload[field]
            if not isinstance(value, str):
                raise ValueError()
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                raise ValueError()
            record[field] = parsed.astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError, OverflowError):
            errors[field] = 'Enter a valid date and time with a timezone.'
    if type(payload['waiting_list_enabled']) is not bool:
        errors['waiting_list_enabled'] = 'Choose whether to enable the waiting list.'
    else:
        record['waiting_list_enabled'] = payload['waiting_list_enabled']
    if not errors and datetime.fromisoformat(record['registration_closes_at']) <= datetime.fromisoformat(record['registration_opens_at']):
        errors['registration_closes_at'] = 'Registration must close after it opens.'
    return record, errors
