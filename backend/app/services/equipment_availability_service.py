from datetime import datetime

from app.services.equipment_request_service import supabase_request


class EquipmentAvailabilityError(ValueError):
    def __init__(self, message, status=400, detail=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.detail = detail or {}


def _clean_text(value, field_name, error_message):
    if value is None:
        raise EquipmentAvailabilityError(error_message, 400, {field_name: error_message})
    text = str(value).strip()
    if not text:
        raise EquipmentAvailabilityError(error_message, 400, {field_name: error_message})
    return text


def _parse_datetime(value, field_name, error_message):
    if value in (None, ''):
        raise EquipmentAvailabilityError(error_message, 400, {field_name: error_message})
    if not isinstance(value, str):
        raise EquipmentAvailabilityError(error_message, 400, {field_name: error_message})
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise EquipmentAvailabilityError(error_message, 400, {field_name: error_message}) from exc


def _overlaps(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def _current_user_id(token):
    user = supabase_request('/auth/v1/user', token=token)
    user_id = user.get('id') if isinstance(user, dict) else None
    if not user_id:
        raise EquipmentAvailabilityError('Authentication required.', 401)
    return user_id


def check_equipment_availability(payload, token):
    if not isinstance(payload, dict):
        raise EquipmentAvailabilityError('Equipment availability request details must be provided as JSON.', 400)

    equipment_type = _clean_text(payload.get('equipment_type'), 'equipment_type', 'Equipment type is required.')
    raw_quantity = payload.get('quantity')
    if isinstance(raw_quantity, str):
        raw_quantity = raw_quantity.strip()
    try:
        quantity = int(raw_quantity)
    except (TypeError, ValueError):
        raise EquipmentAvailabilityError('quantity must be a whole number greater than zero.', 400, {'quantity': 'quantity must be a whole number greater than zero.'})
    if quantity <= 0:
        raise EquipmentAvailabilityError('quantity must be a whole number greater than zero.', 400, {'quantity': 'quantity must be a whole number greater than zero.'})

    start_str = payload.get('start_datetime')
    end_str = payload.get('end_datetime')
    required_start = _parse_datetime(start_str, 'start_datetime', 'Required start date and time is required.')
    required_end = _parse_datetime(end_str, 'end_datetime', 'Required end date and time is required.')
    if required_end <= required_start:
        raise EquipmentAvailabilityError('Required end date and time must be later than the start date and time.', 400, {'end_datetime': 'Required end date and time must be later than the start date and time.'})

    _current_user_id(token)

    equipment_rows = supabase_request('/rest/v1/equipment?select=*', token=token)
    request_rows = supabase_request('/rest/v1/equipment_request?select=equipment_id,quantity,status,events(start_datetime,end_datetime)', token=token)

    committed_by_equipment = {}
    for request in request_rows:
        if not isinstance(request, dict):
            continue
        status = str(request.get('status', '')).strip().lower()
        if status not in {'accepted', 'in_progress', 'partially_accepted', 'completed'}:
            continue
        event = request.get('events') or {}
        if not isinstance(event, dict):
            continue
        event_start = event.get('start_datetime')
        event_end = event.get('end_datetime')
        if not event_start or not event_end:
            continue
        try:
            event_start_dt = _parse_datetime(str(event_start), 'start_datetime', 'Required event date and time is missing.')
            event_end_dt = _parse_datetime(str(event_end), 'end_datetime', 'Required event date and time is missing.')
        except EquipmentAvailabilityError:
            continue
        if not _overlaps(required_start, required_end, event_start_dt, event_end_dt):
            continue
        equipment_id = request.get('equipment_id')
        if equipment_id is None:
            continue
        committed_by_equipment[equipment_id] = committed_by_equipment.get(equipment_id, 0) + int(request.get('quantity') or 0)

    matched_results = []
    for item in equipment_rows:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get('equipment_type', '')).strip()
        if not item_type:
            continue
        if str(item_type).strip().lower() != equipment_type.strip().lower():
            continue

        equipment_id = item.get('equipment_id')
        total_quantity = int(item.get('total_quantity') or 0)
        allocated = committed_by_equipment.get(equipment_id, 0)
        available_quantity = max(0, total_quantity - allocated)
        if available_quantity <= 0:
            continue

        matched_results.append({
            'equipment_id': equipment_id,
            'equipment_type': item_type,
            'equipment_model': item.get('equipment_model'),
            'available_quantity': available_quantity,
            'requested_quantity': quantity,
            'required_start': start_str,
            'required_end': end_str,
            'fulfillment_status': 'available' if available_quantity >= quantity else 'partially_available',
        })

    if not matched_results:
        return {
            'results': [],
            'message': 'No suitable equipment is available for the selected criteria.',
        }

    return {
        'results': matched_results,
        'message': 'Availability checked successfully.',
    }
