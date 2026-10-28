from app.services.event_store import StoreError, supabase_request
from app.services.event_service import EventError


def registration_call(name, token, payload):
    try:
        result = supabase_request('/rest/v1/rpc/' + name, token=token,
                                  payload=payload, method='POST')
    except StoreError as error:
        if error.code == 'PGRST202':
            raise EventError('Registration is not configured yet. Apply supabase/046_event_registration.sql through 051_my_registrations.sql in order.', 503) from error
        raise
    if isinstance(result, dict) and result.get('error'):
        raise EventError(result['error'], result.get('status', 400), errors=result.get('errors'))
    return result
