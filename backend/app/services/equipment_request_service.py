from datetime import datetime

from app.services.event_store import supabase_request


class EquipmentRequestError(Exception):
    def __init__(self, message, status=400, errors=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.errors = errors or {}

    def to_dict(self):
        body = {'error': self.message}
        if self.errors:
            body['errors'] = self.errors
        return body


def list_equipment_requests(event_id, token):
    rows = supabase_request(
        f'/rest/v1/equipment_request?select=*&event_id=eq.{event_id}',
        token=token,
    )
    return rows


def create_equipment_request(event_id, payload, token):
    if not isinstance(payload, dict):
        raise EquipmentRequestError('Equipment request details must be provided as JSON.', 400)

    current_user = _current_user_id(token)
    event = _load_event(event_id, token)

    # assigned_coordinator = event.get('event_coordinator_id')
    # if not assigned_coordinator or current_user != assigned_coordinator:
    #     raise EquipmentRequestError(
    #         'Only the assigned Event Coordinator can create equipment requests for this event.',
    #         403,
    #     )

    equipment_type = _clean_text(payload.get('equipment_type'), 'equipment_type', 'Equipment type is required.')
    quantity = payload.get('quantity')
    if type(quantity) is not int or quantity <= 0:
        raise EquipmentRequestError('quantity must be a whole number greater than zero.', 400, {'quantity': 'quantity must be a whole number greater than zero.'})

    technical_requirements = payload.get('technical_requirements')
    if technical_requirements is not None:
        if not isinstance(technical_requirements, str):
            raise EquipmentRequestError('technical_requirements must be text.', 400, {'technical_requirements': 'technical_requirements must be text.'})
        technical_requirements = technical_requirements.strip() or None


    record = {
        'event_id': int(event_id),
        'requested_by': current_user,
        'quantity': quantity,
        'status': 'pending',
        'technical_requirements': technical_requirements,
        'equipment_type': equipment_type,
    }

    rows = supabase_request('/rest/v1/equipment_request', token=token, payload=record)
    return rows[0] if isinstance(rows, list) and rows else record


def _current_user_id(token):
    user = supabase_request('/auth/v1/user', token=token)
    user_id = user.get('id')
    if not user_id:
        raise EquipmentRequestError('Authentication required to create equipment requests.', 401)
    return user_id


def _load_event(event_id, token):
    rows = supabase_request(
        f'/rest/v1/events?select=event_id,event_coordinator_id&event_id=eq.{event_id}',
        token=token,
    )
    if not rows:
        raise EquipmentRequestError('Event not found or access unavailable.', 404)
    return rows[0]


def _clean_text(value, field_name, missing_message):
    if not isinstance(value, str):
        raise EquipmentRequestError(missing_message, 400, {field_name: missing_message})
    cleaned = value.strip()
    if not cleaned:
        raise EquipmentRequestError(missing_message, 400, {field_name: missing_message})
    return cleaned
