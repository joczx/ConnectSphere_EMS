"""Verify the actual outgoing HTTP method/body, not just mocked RPC calls."""
import json
from unittest.mock import Mock, patch
import pytest
from app.services.event_store import supabase_request


@pytest.mark.parametrize('path,payload,explicit,expected', [
    ('/rest/v1/rpc/equipment_window_availability', {'p_start': '2026-10-06T05:24:00Z', 'p_end': '2026-10-07T05:24:00Z'}, None, 'POST'),
    ('/rest/v1/rpc/reserve_equipment', {'p_event_id': '1', 'p_equipment_id': 10, 'p_quantity': 2}, None, 'POST'),
    ('/rest/v1/rpc/reservable_equipment_events', {}, None, 'POST'),
    ('/rest/v1/equipment?select=equipment_type', None, None, 'GET'),
    ('/auth/v1/user', None, None, 'GET'),
    ('/rest/v1/events', {'event_name': 'Workshop'}, 'PATCH', 'PATCH'),
])
def test_outgoing_method_and_json_arguments(path, payload, explicit, expected):
    response = Mock()
    response.read.return_value = b'[]'
    context = Mock()
    context.__enter__ = Mock(return_value=response)
    context.__exit__ = Mock(return_value=False)
    with patch.dict('os.environ', {'SUPABASE_URL': 'https://example.test', 'SUPABASE_ANON_KEY': 'test-key'}), \
         patch('app.services.event_store.urlopen', return_value=context) as send:
        assert supabase_request(path, token='test-token', payload=payload, method=explicit) == []
    request = send.call_args.args[0]
    assert request.get_method() == expected
    if payload is None:
        assert request.data is None
    else:
        assert json.loads(request.data) == payload
