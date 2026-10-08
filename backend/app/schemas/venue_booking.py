"""Validation for a complete venue booking request.

A request is made for one event in planning. The event decides the period and
the headcount, so those are copied from it rather than typed again, and the
database refuses a request whose copy disagrees with the event it names.
"""
from datetime import datetime, timezone
from uuid import UUID


def parse_booking(body):
    if not isinstance(body, dict):
        return {}, {'body': 'Provide a booking request object.'}
    data, errors = {}, {}
    event_id = body.get('event_id')
    # public.events.event_id is an integer, and the booking is only ever made
    # from the event being planned, so there is nothing to accept here but one.
    if type(event_id) is not int or not 1 <= event_id <= 2147483647:
        errors['event_id'] = 'Start from the event you are planning a venue for.'
    else:
        data['event_id'] = event_id
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
