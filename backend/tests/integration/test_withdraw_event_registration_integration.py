"""SCRUM-35 integration cases TC-SCRUM35-001--010.

Run from backend with RUN_INTEGRATION_TESTS=1 and .env.integration-test.
Normal requests exercise real user tokens, registrations and database updates.
002 arranges a historical planning event/registration with the service key and
calls the real withdrawal RPC; no triggers or functions are disabled. It tests
after-start refusal, not exact equality of two clocks across an HTTP request.
009/010 fault only the withdrawal RPC transport while authentication stays real.
The imported SCRUM-33 fixtures remove all owned event data and temporary users.
"""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

import pytest

from app.services import event_store, registration_service
from tests.integration.supabase_admin import admin_request, user_id_for
from tests.integration.test_register_for_event_integration import (
    details, new_event, records, register, registration_flow,
)


RPC_PATH = '/rest/v1/rpc/withdraw_event_registration'
SUCCESS = 'Your registration has been successfully withdrawn.'
TOO_LATE = 'Registration cannot be withdrawn at or after the event start time.'


def withdraw(client, headers, event):
    return client.post(f"/api/events/{event['event_id']}/registrations/withdraw", headers=headers)


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def available_capacity(client, sign_in, event):
    response = client.get('/api/registration-events', headers=sign_in('Attendee'))
    assert response.status_code == 200, response.get_json()
    return next(row['available_capacity'] for row in response.get_json()['events']
                if row['event_id'] == event['event_id'])


@pytest.fixture(scope='module')
def protected_registration(client, sign_in, new_event):
    """Unchanged registration for refusal/fault tests to verify no side effects."""
    event = new_event()
    response = register(client, sign_in('Attendee'), event)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['registration']['status'] == 'registered'
    return event


@pytest.fixture(scope='module')
def other_attendee(registration_flow):
    return registration_flow.user('SCRUM-35 other attendee', 'Attendee')


def test_tc_scrum35_001_003_004_real_withdrawal_updates_status_and_confirms_success(client, sign_in, new_event):
    """001/003/004: allowed before start, persisted Withdrawn and success message."""
    event = new_event()
    assert instant(event['start_datetime']) > datetime.now(timezone.utc)
    response = register(client, sign_in('Attendee'), event)
    assert response.status_code == 200, response.get_json()
    response = withdraw(client, sign_in('Attendee'), event)
    assert response.status_code == 200, response.get_json()
    assert response.headers['Cache-Control'] == 'no-store'
    result = response.get_json()
    assert result['message'] == SUCCESS
    assert 'error' not in result
    returned = result['registration']
    saved, = records(event)
    assert returned['event_id'] == saved['event_id'] == event['event_id']
    assert returned['attendee_id'] == saved['attendee_id'] == user_id_for('Attendee')
    assert returned['status'] == saved['status'] == 'withdrawn'
    assert returned['withdrawn_at']
    assert instant(returned['withdrawn_at']) == instant(saved['withdrawn_at'])


@pytest.fixture(scope='module')
def started_registration(registration_flow):
    """Arrange historical data without editing a confirmed event or disabling guards.

    The event is created by request/approval in Planning. Only its fixture dates
    are moved into the past, and a historical registration is inserted. The
    withdrawal guard is independent of the operational stage.
    """
    event = registration_flow.event(capacity=1)
    now = datetime.now(timezone.utc)
    changed, = admin_request(f"/rest/v1/events?event_id=eq.{event['event_id']}", {
        'start_datetime': (now - timedelta(hours=1)).isoformat(),
        'end_datetime': (now + timedelta(hours=1)).isoformat(),
    }, 'PATCH')
    assert instant(changed['start_datetime']) < now
    admin_request('/rest/v1/event_registration', {
        'event_id': event['event_id'], 'attendee_id': user_id_for('Attendee'),
        'status': 'registered', **details(),
    })
    return changed


def test_tc_scrum35_002_started_event_refuses_withdrawal_without_changing_data(client, sign_in, started_registration):
    before = records(started_registration)
    response = withdraw(client, sign_in('Attendee'), started_registration)
    assert response.status_code == 409, response.get_json()
    assert response.get_json() == {'error': TOO_LATE}
    assert records(started_registration) == before


@pytest.mark.parametrize('capacity,waiting_list,expected_before,expected_after', [
    pytest.param(3, False, 2, 3, id='registered-place-released'),
    pytest.param(1, False, 0, 1, id='full-event-place-released'),
    pytest.param(1, True, 0, 0, id='waitlisted-withdrawal-releases-no-place'),
])
def test_tc_scrum35_005_capacity_updates_after_actual_withdrawal(
        client, sign_in, new_event, other_attendee, capacity, waiting_list, expected_before, expected_after):
    event = new_event(capacity=capacity, waiting_list=waiting_list)
    if waiting_list:
        first = register(client, other_attendee['headers'], event)
        assert first.status_code == 200, first.get_json()
        assert first.get_json()['registration']['status'] == 'registered'
    response = register(client, sign_in('Attendee'), event)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['registration']['status'] == ('waiting_list' if waiting_list else 'registered')
    assert available_capacity(client, sign_in, event) == expected_before

    response = withdraw(client, sign_in('Attendee'), event)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['registration']['status'] == 'withdrawn'
    assert response.get_json()['available_capacity'] == expected_after
    assert available_capacity(client, sign_in, event) == expected_after
    saved = records(event)
    confirmed_count = sum(row['status'] == 'registered' for row in saved)
    assert confirmed_count == (1 if waiting_list else 0)
    assert capacity - confirmed_count == expected_after


def test_tc_scrum35_006_authentication_required_without_calling_rpc(client):
    with patch.object(registration_service, 'supabase_request', wraps=registration_service.supabase_request) as rpc:
        response = client.post('/api/events/1/registrations/withdraw')
    assert response.status_code == 401
    assert response.get_json() == {'error': 'Please sign in again.'}
    rpc.assert_not_called()


def test_tc_scrum35_007_real_non_attendee_cannot_withdraw(client, sign_in, protected_registration):
    before = records(protected_registration)
    response = withdraw(client, sign_in('Event Organiser'), protected_registration)
    assert response.status_code == 403
    assert response.get_json() == {'error': 'Only attendees can withdraw registrations.'}
    assert records(protected_registration) == before


def test_tc_scrum35_008_attendee_without_registration_cannot_withdraw_another_users_record(
        client, protected_registration, other_attendee):
    before = records(protected_registration)
    response = withdraw(client, other_attendee['headers'], protected_registration)
    assert response.status_code == 404
    assert response.get_json() == {'error': 'Registration not found.'}
    assert records(protected_registration) == before


def inject_rpc_failure(monkeypatch, error_factory):
    original = event_store.urlopen
    calls = []

    def urlopen(request, *args, **kwargs):
        if urlsplit(request.full_url).path == RPC_PATH:
            calls.append(request.full_url)
            raise error_factory(request)
        return original(request, *args, **kwargs)

    monkeypatch.setattr(event_store, 'urlopen', urlopen)
    return calls


def test_tc_scrum35_009_missing_rpc_returns_error_without_confirming_withdrawal(
        client, sign_in, protected_registration, monkeypatch):
    before = records(protected_registration)
    headers = sign_in('Attendee')
    body = json.dumps({'code': 'PGRST202', 'message': 'Function not found.'}).encode()
    calls = inject_rpc_failure(monkeypatch, lambda request:
        HTTPError(request.full_url, 404, 'Not Found', {}, BytesIO(body)))
    response = withdraw(client, headers, protected_registration)
    assert len(calls) == 1
    assert response.status_code == 503
    assert response.get_json() == {'error': 'Registration is not configured yet. Apply supabase/046_event_registration.sql through 052_event_registration_roster.sql in order.'}
    assert records(protected_registration) == before


def test_tc_scrum35_010_database_outage_does_not_confirm_withdrawal(
        client, sign_in, protected_registration, monkeypatch):
    before = records(protected_registration)
    headers = sign_in('Attendee')
    calls = inject_rpc_failure(monkeypatch, lambda request: URLError('Controlled test outage'))
    response = withdraw(client, headers, protected_registration)
    assert len(calls) == 1
    assert response.status_code == 503
    assert response.get_json() == {'error': 'Event service is temporarily unavailable.'}
    assert records(protected_registration) == before
