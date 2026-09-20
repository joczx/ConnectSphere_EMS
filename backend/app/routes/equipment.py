"""Equipment reservations for every signed-in user; no role checks."""
from uuid import UUID
from flask import Blueprint, jsonify, request
from app.routes.events import authenticated_token
from app.services.event_store import StoreError, supabase_request

equipment = Blueprint('equipment', __name__, url_prefix='/api/equipment')


@equipment.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@equipment.errorhandler(StoreError)
def unavailable(error):
    return jsonify(error='Please sign in again.' if error.status == 401 else
                   'Equipment service is unavailable. Please try again.'), error.status


@equipment.get('/events')
def events():
    token = authenticated_token()
    return jsonify(events=supabase_request('/rest/v1/rpc/equipment_events', token=token, payload={}))


@equipment.get('/availability')
def availability():
    token = authenticated_token()
    event_id = request.args.get('event_id', '').strip()
    if not event_id:
        return jsonify(error='Select an event.'), 400
    result = supabase_request('/rest/v1/rpc/equipment_availability', token=token,
                              payload={'p_event_id': event_id})
    return jsonify(result), (400 if result.get('error') else 200)


@equipment.post('/reservations')
def reserve():
    token = authenticated_token()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error='Provide an event, equipment and quantity.'), 400
    event_id, equipment_id, quantity = (body.get(k) for k in ('event_id', 'equipment_id', 'quantity'))
    if not isinstance(event_id, str) or not event_id.strip() or not isinstance(equipment_id, str):
        return jsonify(error='Select an event and equipment.'), 400
    try:
        equipment_id = str(UUID(equipment_id))
    except ValueError:
        return jsonify(error='Select valid equipment.'), 400
    if type(quantity) is not int or not 1 <= quantity <= 2147483647:
        return jsonify(error='Quantity must be a positive whole number.'), 400
    result = supabase_request('/rest/v1/rpc/reserve_equipment', token=token, payload={
        'p_event_id': event_id.strip(), 'p_equipment_id': equipment_id, 'p_quantity': quantity,
    })
    return jsonify(result), (409 if result.get('error') else 201)
