from flask import Blueprint, jsonify, request

from app.services.equipment_availability_service import EquipmentAvailabilityError, check_equipment_availability
from app.services.equipment_request_service import supabase_request
from app.services.event_store import StoreError


equipment = Blueprint('equipment', __name__, url_prefix='/api')


@equipment.after_request
def prevent_caching(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@equipment.errorhandler(StoreError)
def store_error(error):
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
