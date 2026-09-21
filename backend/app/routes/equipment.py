from uuid import UUID
from flask import Blueprint, jsonify, request

from app.services.equipment_availability_service import EquipmentAvailabilityError, check_equipment_availability
from app.services.equipment_request_service import supabase_request
from app.services.event_store import StoreError, authenticated_token


equipment = Blueprint('equipment', __name__, url_prefix='/api')


@equipment.after_request
def prevent_caching(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@equipment.errorhandler(StoreError)
def store_error(error):
    if error.code in {'PGRST202', 'PGRST205', '42P01', '42703'}:
        return jsonify(error='Equipment reservations are not configured in the database yet. Please contact your administrator.'), 503
    message = 'Please sign in again.' if error.status == 401 else 'Equipment service is temporarily unavailable.'
    return jsonify(error=message), error.status


@equipment.errorhandler(EquipmentAvailabilityError)
def availability_error(error):
    return jsonify(error=error.message, details=error.detail), error.status


def _bearer_token():
    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token.strip():
        raise StoreError(401)
    return token.strip()


@equipment.get('/equipment-types')
def equipment_types():
    token = _bearer_token()
    rows = supabase_request('/rest/v1/equipment?select=equipment_type', token=token)
    types = sorted({row['equipment_type'] for row in rows if row.get('equipment_type')})
    return jsonify(equipment_types=types)


@equipment.get('/equipment-availability')
def equipment_availability():
    token = _bearer_token()
    payload = {
        'equipment_type': request.args.get('equipment_type'),
        'quantity': request.args.get('quantity'),
        'start_datetime': request.args.get('start_datetime'),
        'end_datetime': request.args.get('end_datetime'),
    }
    result = check_equipment_availability(payload, token)
    return jsonify(result)

@equipment.get('/equipment/events')
def events():
    token = authenticated_token()
    return jsonify(events=supabase_request('/rest/v1/events?select=event_id,event_name&order=event_name.asc', token=token))


@equipment.get('/equipment/availability')
def availability():
    token = authenticated_token()
    event_id = request.args.get('event_id', '').strip()
    if not event_id:
        return jsonify(error='Select an event.'), 400
    result = supabase_request('/rest/v1/rpc/equipment_availability', token=token,
                              payload={'p_event_id': event_id})
    return jsonify(result), (400 if result.get('error') else 200)


@equipment.post('/equipment/reservations')
def reserve():
    token = authenticated_token()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error='Provide an event, equipment and quantity.'), 400
    event_id, equipment_id, quantity = (body.get(k) for k in ('event_id', 'equipment_id', 'quantity'))
    if not isinstance(event_id, str) or not event_id.strip() or not isinstance(equipment_id, str):
        return jsonify(error='Select an event and equipment.'), 400
    try:
        if not equipment_id.isdecimal() or not 1 <= int(equipment_id) <= 2147483647:
            raise ValueError
        equipment_id = int(equipment_id)
    except ValueError:
        return jsonify(error='Select valid equipment.'), 400
    if type(quantity) is not int or not 1 <= quantity <= 2147483647:
        return jsonify(error='Quantity must be a positive whole number.'), 400
    result = supabase_request('/rest/v1/rpc/reserve_equipment', token=token, payload={
        'p_event_id': event_id.strip(), 'p_equipment_id': equipment_id, 'p_quantity': quantity,
    })
    return jsonify(result), (409 if result.get('error') else 201)


@equipment.get('/equipment/reservations')
def my_reservations():
    token = authenticated_token()
    rows = supabase_request('/rest/v1/rpc/my_equipment_reservations', token=token, payload={})
    return jsonify(reservations=rows)


@equipment.route('/equipment/reservations/<reservation_id>', methods=['PATCH', 'DELETE'])
def manage_reservation(reservation_id):
    token = authenticated_token()
    try:
        reservation_id = str(UUID(reservation_id))
    except ValueError:
        return jsonify(error='Select a valid reservation.'), 400
    payload = {'p_reservation_id': reservation_id}
    operation = 'cancel_equipment_reservation'
    if request.method == 'PATCH':
        body = request.get_json(silent=True)
        quantity = body.get('quantity') if isinstance(body, dict) else None
        if type(quantity) is not int or not 1 <= quantity <= 2147483647:
            return jsonify(error='Quantity must be a positive whole number.'), 400
        payload['p_quantity'] = quantity
        operation = 'update_equipment_reservation'
    result = supabase_request('/rest/v1/rpc/' + operation, token=token, payload=payload)
    return jsonify(result), (result.get('status', 409) if result.get('error') else 200)
