from flask import Blueprint, jsonify, request

from app.services.event_store import StoreError
from app.services.equipment_request_service import (
    EquipmentRequestError,
    create_equipment_request,
    delete_equipment_request,
    list_equipment_requests,
    update_equipment_request,
)

bp = Blueprint('equipment_requests', __name__, url_prefix='/api/events')


@bp.errorhandler(EquipmentRequestError)
def handle_error(error):
    return jsonify(error.to_dict()), error.status

@bp.errorhandler(StoreError)
def handle_store_error(error):
    return jsonify(error.to_dict()), error.status


@bp.get('/<int:event_id>/equipment-requests')
def list_requests(event_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '', 1).strip()
    if not token:
        raise EquipmentRequestError('Authentication required.', 401)
    rows = list_equipment_requests(event_id, token)
    return jsonify({'count': len(rows), 'equipment_requests': rows})


@bp.post('/<int:event_id>/equipment-requests')
def create_request(event_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '', 1).strip()
    if not token:
        raise EquipmentRequestError('Authentication required.', 401)

    payload = request.get_json(silent=True)
    row = create_equipment_request(event_id, payload, token)
    return jsonify({
        'message': 'Equipment request submitted successfully.',
        'equipment_request': row,
    }), 201


@bp.patch('/<int:event_id>/equipment-requests/<int:request_id>')
def update_request(event_id, request_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '', 1).strip()
    if not token:
        raise EquipmentRequestError('Authentication required.', 401)

    row = update_equipment_request(event_id, request_id, request.get_json(silent=True), token)
    return jsonify({
        'message': 'Equipment request updated successfully.',
        'equipment_request': row,
    })


@bp.delete('/<int:event_id>/equipment-requests/<int:request_id>')
def delete_request(event_id, request_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '', 1).strip()
    if not token:
        raise EquipmentRequestError('Authentication required.', 401)

    row = delete_equipment_request(event_id, request_id, token)
    return jsonify({
        'message': 'Equipment request deleted.',
        'equipment_request': row,
    })
