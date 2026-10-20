"""Event edits must distinguish validation, stale writes and audit failures."""
import io
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

from app.services import event_service as service, event_store, event_status_service, supabase_client


@pytest.fixture
def existing(monkeypatch):
    row = {'event_id': 1, 'event_name': 'Old', 'status': 'planning', 'capacity_needed': 20,
           'start_datetime': '2099-01-01T10:00:00+00:00', 'end_datetime': '2099-01-01T12:00:00+00:00'}
    monkeypatch.setattr(service, 'load_event', lambda *args: row)
    return row


@pytest.mark.parametrize('payload,status,field', [
    ({'unknown': 1}, 400, '_body'),
    ({'end_datetime': '2099-01-01T09:00:00+00:00'}, 400, 'end_datetime'),
    ({'capacity_needed': 30}, 409, None),
])
def test_invalid_or_unconfirmed_edit_never_writes(monkeypatch, existing, payload, status, field):
    query = Mock()
    monkeypatch.setattr(service, 'supabase_request', query)
    with pytest.raises(service.EventError) as error:
        service.update_event(1, payload, 'token')
    assert error.value.status == status
    body = error.value.to_dict()
    if field:
        assert field in body['errors']
    else:
        assert body['critical_fields'] == ['Expected attendance']
    query.assert_not_called()


def test_unchanged_event_has_no_write(existing):
    assert service.update_event(1, {'event_name': 'Old'}, 'token') == (existing, None)


def test_readonly_event_cannot_be_edited(existing):
    existing['status'] = 'completed'
    with pytest.raises(service.EventError) as error:
        service.update_event(1, {'event_name': 'New'}, 'token')
    assert error.value.status == 409


def test_missing_event(monkeypatch):
    monkeypatch.setattr(service, 'supabase_request', lambda *args, **kwargs: [])
    with pytest.raises(service.EventError) as error:
        service.load_event(1, 'token')
    assert error.value.status == 404
    assert service.list_activity(1, 'token') == []


def test_event_disappearing_during_edit_is_permission_error(monkeypatch):
    monkeypatch.setattr(service, 'load_event', Mock(side_effect=service.EventError('Gone', 404)))
    error = service._why_nothing_was_written(1, {}, 'version', 'token')
    assert error.status == 403 and not error.stale


def test_audit_and_identity_outage_do_not_undo_saved_edit(monkeypatch):
    monkeypatch.setattr(service, 'supabase_request', Mock(side_effect=event_store.StoreError(503)))
    assert service._current_user_id('token') is None
    assert service._record_activity(1, 'edit', {'event_name': {'from': 'Old', 'to': 'New'}}, 'token') is None


def test_lifecycle_does_not_swallow_unrelated_database_errors(monkeypatch):
    original = event_store.StoreError(503)
    monkeypatch.setattr(event_status_service, 'supabase_request', Mock(side_effect=original))
    with pytest.raises(event_store.StoreError) as error:
        event_status_service.lifecycle_call('refresh_visible_event_statuses', 'token', {})
    assert error.value is original


def test_supabase_empty_response(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', 'https://example.test')
    monkeypatch.setenv('SUPABASE_ANON_KEY', 'test-key')
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b''
    monkeypatch.setattr(event_store, 'urlopen', Mock(return_value=response))
    assert event_store.supabase_request('/rest/v1/events') == []


@pytest.mark.parametrize('body,code', [(b'{"code":"42703","message":"missing column"}', '42703'), (b'not json', None), (b'[]', None)])
def test_upstream_errors_are_logged_without_leaking_database_details(monkeypatch, caplog, body, code):
    monkeypatch.setenv('SUPABASE_URL', 'https://example.test')
    monkeypatch.setenv('SUPABASE_ANON_KEY', 'test-key')
    original = HTTPError('https://example.test', 400, 'Bad request', {}, io.BytesIO(body))
    monkeypatch.setattr(event_store, 'urlopen', Mock(side_effect=original))
    with pytest.raises(event_store.StoreError) as error:
        event_store.supabase_request('/rest/v1/events')
    assert error.value.status == 503 and error.value.code == code
    assert 'Supabase 400 failed' in caplog.text
    assert 'missing column' not in error.value.message


def test_supabase_missing_credentials_and_outside_request(monkeypatch):
    monkeypatch.delenv('SUPABASE_URL', raising=False)
    with pytest.raises(RuntimeError, match='SUPABASE_URL'):
        supabase_client.get_supabase()
    assert supabase_client._bearer_token() is None
