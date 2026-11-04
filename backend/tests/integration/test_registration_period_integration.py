"""SCRUM-214 integration cases 001--018; see docs/registration-period-integration-tests.md.

015 follows the current catalogue contract (hidden outside the open period;
registration_status restored for visible events). Completed/null stages in 016 remain unit-only.
012/017/018 inject only period-RPC transport responses, keeping auth real.
"""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

import pytest

from app.services import event_store, registration_service
from tests.integration.supabase_admin import admin_request
from tests.integration.test_notifications import submit_for_safety
from tests.integration.test_register_for_event_integration import (
    new_event, register, records, registration_flow,
)


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def settings(**changes):
    now = datetime.now(timezone(timedelta(hours=8)))
    return {'registration_opens_at': (now - timedelta(days=1)).isoformat(),
            'registration_closes_at': (now + timedelta(days=4)).isoformat(),
            'waiting_list_enabled': False, **changes}


def save(client, headers, event, payload):
    return client.patch(f"/api/events/{event['event_id']}/registration-period", headers=headers, json=payload)


def stored(event):
    row, = admin_request(f"/rest/v1/events?event_id=eq.{event['event_id']}")
    return {field: row[field] for field in settings()}


def assert_settings(actual, expected):
    for field in ('registration_opens_at', 'registration_closes_at'):
        assert instant(actual[field]) == instant(expected[field])
    assert actual['waiting_list_enabled'] is expected['waiting_list_enabled']


@pytest.fixture(scope='module')
def confirmed_event(new_event):
    return new_event()


@pytest.fixture(scope='module')
def outsider(registration_flow):
    return registration_flow.user('SCRUM214 unassigned organiser', 'Event Organiser')


@pytest.mark.parametrize('enabled', [True, False])
def test_tc_scrum214_001_004_initial_settings_and_waiting_list_toggle(client, sign_in, registration_flow, enabled):
    event = submit_for_safety(registration_flow)
    registration_flow.call('Safety Officer', 'post', f"/api/operational-safety-reviews/{event['event_id']}/decision", {'outcome': 'approved'})
    assert stored(event)['registration_opens_at'] is None
    for preference in (enabled, not enabled):
        payload = settings(waiting_list_enabled=preference)
        with patch.object(registration_service, 'supabase_request', wraps=registration_service.supabase_request) as rpc:
            response = save(client, sign_in('Event Organiser'), event, payload)
        assert response.status_code == 200, response.get_json()
        assert_settings(response.get_json()['event'], payload)
        assert_settings(stored(event), payload)
        sent = rpc.call_args.kwargs['payload']
        for field in ('registration_opens_at', 'registration_closes_at'):
            assert sent['p_' + field] == instant(payload[field]).astimezone(timezone.utc).isoformat()
        assert sent['p_waiting_list_enabled'] is preference


@pytest.mark.parametrize('offset', [-1, 0], ids=['closing-before-opening', 'closing-equals-opening'])
def test_tc_scrum214_002_bad_order_does_not_call_rpc(client, sign_in, confirmed_event, offset):
    payload = settings()
    payload['registration_closes_at'] = (instant(payload['registration_opens_at']) + timedelta(seconds=offset)).isoformat()
    before = stored(confirmed_event)
    with patch.object(registration_service, 'supabase_request', wraps=registration_service.supabase_request) as rpc:
        response = save(client, sign_in('Event Organiser'), confirmed_event, payload)
    assert response.status_code == 400
    assert 'registration_closes_at' in response.get_json()['errors']
    rpc.assert_not_called()
    assert stored(confirmed_event) == before


@pytest.mark.parametrize('phase', ['not_open', 'open'])
def test_tc_scrum214_003_update_before_and_during_period(client, sign_in, new_event, phase):
    event = new_event(phase)
    before = stored(event)
    payload = {**before, 'registration_opens_at': (instant(before['registration_opens_at']) + timedelta(hours=1)).isoformat(),
               'registration_closes_at': (instant(before['registration_closes_at']) + timedelta(hours=1)).isoformat()}
    response = save(client, sign_in('Event Organiser'), event, payload)
    assert response.status_code == 200, response.get_json()
    assert_settings(response.get_json()['event'], payload)
    assert_settings(stored(event), payload)
    assert stored(event) != before


@pytest.mark.parametrize('phase,message', [('not_open', 'Registration is not yet open.'), ('open', None), ('closed', 'Registration has closed.')])
def test_tc_scrum214_005_007_real_registration_window_and_messages(client, sign_in, new_event, phase, message):
    event = new_event(phase)
    response = register(client, sign_in('Attendee'), event)
    if message:
        assert response.status_code == 409
        assert response.get_json() == {'error': message}
        assert records(event) == []
    else:
        assert response.status_code == 200, response.get_json()
        row, = records(event)
        assert row['status'] == response.get_json()['registration']['status'] == 'registered'


def test_tc_scrum214_006_attendee_sees_updated_dates(client, sign_in, new_event):
    event = new_event()
    def catalogue():
        response = client.get('/api/registration-events', headers=sign_in('Attendee'))
        assert response.status_code == 200, response.get_json()
        assert response.headers['Cache-Control'] == 'no-store'
        assert all(row['registration_status'] == 'open' for row in response.get_json()['events'])
        return next(row for row in response.get_json()['events'] if row['event_id'] == event['event_id'])
    before = catalogue()
    payload = {**settings(), 'registration_opens_at': (instant(before['registration_opens_at']) + timedelta(hours=1)).isoformat(),
               'registration_closes_at': (instant(before['registration_closes_at']) + timedelta(hours=1)).isoformat()}
    response = save(client, sign_in('Event Organiser'), event, payload)
    assert response.status_code == 200, response.get_json()
    after = catalogue()
    assert_settings(after, payload)
    assert instant(after['registration_opens_at']) != instant(before['registration_opens_at'])
    assert instant(after['registration_closes_at']) != instant(before['registration_closes_at'])


@pytest.mark.parametrize('changes,field', [
    ({'registration_opens_at': 'invalid'}, 'registration_opens_at'),
    ({'registration_opens_at': '2027-01-01T10:00:00'}, 'registration_opens_at'),
    ({'registration_opens_at': None}, 'registration_opens_at'),
    ({'waiting_list_enabled': 'true'}, 'waiting_list_enabled'),
    ({'unexpected': True}, '_body'),
])
def test_tc_scrum214_008_invalid_settings_leave_data_unchanged(client, sign_in, confirmed_event, changes, field):
    before = stored(confirmed_event)
    with patch.object(registration_service, 'supabase_request', wraps=registration_service.supabase_request) as rpc:
        response = save(client, sign_in('Event Organiser'), confirmed_event, settings(**changes))
    assert response.status_code == 400
    assert field in response.get_json()['errors']
    rpc.assert_not_called()
    assert stored(confirmed_event) == before


def test_tc_scrum214_009_timezone_fractional_second_ordering(client, sign_in, new_event):
    event = new_event('not_open')
    opening = datetime.now(timezone(timedelta(hours=8))) + timedelta(days=2)
    payload = settings(registration_opens_at=opening.isoformat(),
        registration_closes_at=(opening.astimezone(timezone.utc) + timedelta(milliseconds=100)).isoformat())
    response = save(client, sign_in('Event Organiser'), event, payload)
    assert response.status_code == 200, response.get_json()
    assert_settings(stored(event), payload)


def test_tc_scrum214_010_authentication_required(client):
    with patch.object(registration_service, 'supabase_request', wraps=registration_service.supabase_request) as rpc:
        response = client.patch('/api/events/1/registration-period', json=settings())
    assert response.status_code == 401
    assert set(response.get_json()) == {'error'}
    rpc.assert_not_called()


def test_tc_scrum214_011_database_rejects_closing_after_event_starts(client, sign_in, confirmed_event):
    before = stored(confirmed_event)
    payload = settings(registration_closes_at=(instant(confirmed_event['start_datetime']) + timedelta(hours=1)).isoformat())
    response = save(client, sign_in('Event Organiser'), confirmed_event, payload)
    assert response.status_code == 400, response.get_json()
    assert response.get_json()['errors']['registration_closes_at'] == 'Registration must close before the event starts.'
    assert stored(confirmed_event) == before


def inject_rpc(monkeypatch, *, body=None, missing=False, outage=False):
    original = event_store.urlopen
    calls = []
    def urlopen(request, *args, **kwargs):
        if urlsplit(request.full_url).path != '/rest/v1/rpc/set_event_registration_period':
            return original(request, *args, **kwargs)
        calls.append(request)
        if outage:
            raise URLError('Controlled test outage')
        if missing:
            raise HTTPError(request.full_url, 404, 'Not Found', {}, BytesIO(json.dumps({'code': 'PGRST202', 'message': 'Function not found.'}).encode()))
        return BytesIO(json.dumps(body).encode())
    monkeypatch.setattr(event_store, 'urlopen', urlopen)
    return calls


def test_tc_scrum214_012_rpc_refusal_defaults_to_400(client, sign_in, confirmed_event, monkeypatch):
    headers = sign_in('Event Organiser')
    before = stored(confirmed_event)
    calls = inject_rpc(monkeypatch, body={'error': 'Invalid period.'})
    response = save(client, headers, confirmed_event, settings())
    assert len(calls) == 1
    assert response.status_code == 400
    assert response.get_json() == {'error': 'Invalid period.'}
    assert stored(confirmed_event) == before


def test_tc_scrum214_013_closed_period_cannot_be_reopened(client, sign_in, new_event):
    event = new_event('closed')
    before = stored(event)
    response = save(client, sign_in('Event Organiser'), event, settings())
    assert response.status_code == 409, response.get_json()
    assert response.get_json() == {'error': 'Registration settings can only change before or during registration.'}
    assert stored(event) == before


def test_tc_scrum214_014_unassigned_organiser_cannot_save(client, confirmed_event, outsider):
    before = stored(confirmed_event)
    response = save(client, outsider['headers'], confirmed_event, settings())
    assert response.status_code == 403, response.get_json()
    assert set(response.get_json()) == {'error'}
    assert stored(confirmed_event) == before


@pytest.mark.parametrize('phase', ['not_open', 'closed'])
def test_tc_scrum214_015_catalogue_hides_unavailable_periods(client, sign_in, new_event, phase):
    event = new_event(phase)
    response = client.get('/api/registration-events', headers=sign_in('Attendee'))
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert all(row['event_id'] != event['event_id'] for row in response.get_json()['events'])
    assert all(row['registration_status'] == 'open' for row in response.get_json()['events'])


@pytest.mark.parametrize('stage', ['planning', 'pending_safety_checks', 'cancelled'])
def test_tc_scrum214_016_only_confirmed_events_accept_settings(client, sign_in, registration_flow, stage):
    flow = registration_flow
    event = submit_for_safety(flow) if stage == 'pending_safety_checks' else flow.event()
    if stage == 'cancelled':
        flow.call('Event Organiser', 'post', f"/api/events/{event['event_id']}/cancel")
    row, = admin_request(f"/rest/v1/events?event_id=eq.{event['event_id']}")
    assert row['status'] == stage
    with patch.object(registration_service, 'supabase_request', wraps=registration_service.supabase_request) as rpc:
        response = save(client, sign_in('Event Organiser'), event, settings())
    assert response.status_code == 409, response.get_json()
    assert 'confirmed' in response.get_json()['error']
    rpc.assert_not_called()
    assert stored(event)['registration_opens_at'] is None


@pytest.mark.parametrize('missing,message', [
    pytest.param(True, 'Registration is not configured yet. Apply supabase/046_event_registration.sql through 052_event_registration_roster.sql in order.', id='TC-SCRUM214-017'),
    pytest.param(False, 'Event service is temporarily unavailable.', id='TC-SCRUM214-018'),
])
def test_tc_scrum214_017_018_save_transport_failure_returns_no_success(client, sign_in, confirmed_event, monkeypatch, missing, message):
    headers = sign_in('Event Organiser')
    before = stored(confirmed_event)
    calls = inject_rpc(monkeypatch, missing=missing, outage=not missing)
    response = save(client, headers, confirmed_event, settings())
    assert len(calls) == 1
    assert response.status_code == 503
    assert response.get_json() == {'error': message}
    assert stored(confirmed_event) == before
