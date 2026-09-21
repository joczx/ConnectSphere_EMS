from datetime import datetime, timezone

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
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Timezone required')
        return parsed.astimezone(timezone.utc)
    except ValueError as exc:
        raise EquipmentAvailabilityError(error_message, 400, {field_name: error_message}) from exc


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
    if isinstance(raw_quantity, bool) or not isinstance(raw_quantity, (str, int)) or quantity <= 0:
        raise EquipmentAvailabilityError('quantity must be a whole number greater than zero.', 400, {'quantity': 'quantity must be a whole number greater than zero.'})

    start_str = payload.get('start_datetime')
    end_str = payload.get('end_datetime')
    required_start = _parse_datetime(start_str, 'start_datetime', 'Required start date and time is required.')
    required_end = _parse_datetime(end_str, 'end_datetime', 'Required end date and time is required.')
    if required_end <= required_start:
        raise EquipmentAvailabilityError('Required end date and time must be later than the start date and time.', 400, {'end_datetime': 'Required end date and time must be later than the start date and time.'})

    _current_user_id(token)

    equipment_rows = supabase_request('/rest/v1/rpc/equipment_window_availability', token=token, payload={
        'p_start': required_start.isoformat(), 'p_end': required_end.isoformat(),
    })

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
        available_quantity = max(0, int(item.get('available_quantity') or 0))
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
