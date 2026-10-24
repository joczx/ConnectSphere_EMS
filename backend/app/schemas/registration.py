"""Registration settings use explicit, timezone-aware instants."""
from datetime import datetime, timezone


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
