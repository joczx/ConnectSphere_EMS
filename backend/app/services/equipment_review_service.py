from app.services.event_store import supabase_request
from app.services.equipment_request_service import EquipmentRequestError


def review_equipment_request(request_id, payload, token):
    if not isinstance(payload, dict):
        raise EquipmentRequestError('Provide a review decision.', 400)
    outcome = payload.get('outcome')
    if outcome not in ('accepted', 'rejected', 'partially_accepted'):
        raise EquipmentRequestError('Choose Accept, Reject or Partially accept.', 400)
    equipment_id = payload.get('equipment_id')
    quantity = payload.get('accepted_quantity')
    reason = payload.get('reason', '')
    if not isinstance(reason, str):
        raise EquipmentRequestError('The reason must be text.', 400)
    if outcome == 'rejected':
        if not reason.strip():
            raise EquipmentRequestError('Enter a reason for rejection.', 400)
        equipment_id, quantity = None, None
    else:
        if type(equipment_id) is not int or not 1 <= equipment_id <= 2147483647:
            raise EquipmentRequestError('Select equipment to reserve.', 400)
        if outcome == 'partially_accepted':
            if type(quantity) is not int or not 1 <= quantity <= 2147483647:
                raise EquipmentRequestError('Accepted quantity must be a positive whole number.', 400)
        else:
            quantity = None
    result = supabase_request('/rest/v1/rpc/review_equipment_request', token=token, payload={
        'p_request_id': request_id, 'p_outcome': outcome,
        'p_equipment_id': equipment_id, 'p_accepted_quantity': quantity,
        'p_reason': reason.strip(),
    })
    if result.get('error'):
        raise EquipmentRequestError(result['error'], result.get('status', 409))
    return result
