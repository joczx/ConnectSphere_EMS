"""Call the database lifecycle rules with the signed-in user's credentials."""
from app.services.event_service import EventError
from app.services.event_store import StoreError, supabase_request


def lifecycle_call(name, token, payload):
    try:
        result = supabase_request('/rest/v1/rpc/' + name, token=token,
                                  payload=payload, method='POST')
    except StoreError as error:
        if error.code == '23514':
            raise EventError('The event cannot advance until its required conditions are met.', status=409) from error
        raise
    if isinstance(result, dict) and result.get('error'):
        raise EventError(result['error'], status=result.get('status', 400))
    return result
