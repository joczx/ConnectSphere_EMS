"""Validation for a complete venue booking request."""
from datetime import datetime, timezone
from uuid import UUID


def parse_booking(body):
    if not isinstance(body, dict):
        return {}, {'body': 'Provide a booking request object.'}
    data, errors = {}, {}
    for field, limit in [('event_name', 200), ('venue_requirements', 5000)]:
        value = body.get(field)
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            errors[field] = f'{field.replace("_", " ").capitalize()} is required (maximum {limit} characters).'
        else:
            data[field] = value.strip()
    try:
        data['venue_id'] = str(UUID(str(body.get('venue_id', ''))))
    except ValueError:
        errors['venue_id'] = 'Select a valid venue.'
    attendance = body.get('attendance')
    if type(attendance) is not int or not 1 <= attendance <= 2147483647:
        errors['attendance'] = 'Attendance must be a positive whole number.'
    else:
        data['attendance'] = attendance
    dates = {}
    for field in ('starts_at', 'ends_at'):
        try:
            value = datetime.fromisoformat(body[field].replace('Z', '+00:00'))
            if value.tzinfo is None:
                raise ValueError
            dates[field] = value
            data[field] = value.isoformat()
        except (KeyError, TypeError, AttributeError, ValueError):
            errors[field] = 'Provide a valid date and time with a timezone.'
    if len(dates) == 2:
        if dates['ends_at'] <= dates['starts_at']:
            errors['ends_at'] = 'End must be after start.'
        if dates['starts_at'] <= datetime.now(timezone.utc):
            errors['starts_at'] = 'Start must be in the future.'
    return data, errors
