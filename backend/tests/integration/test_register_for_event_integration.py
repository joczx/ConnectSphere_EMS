"""SCRUM-33: registration integration cases 001--014 plus capacity/period checks.

Run from backend with RUN_INTEGRATION_TESTS=1. Uses .env.integration-test only.
Normal requests use real user tokens and the live isolated database. Cases
008/011--014 inject only HTTP transport responses for register_for_event, never
fake service results or change a shared SQL function. AC5 is the success message
displayed by the on-screen alert. Cleanup is restricted to this module's fixtures.
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
from tests.integration.test_notifications import Flow, submit_for_safety
from tests.integration.test_view_upcoming_events_integration import cleanup


RPC_PATH = '/rest/v1/rpc/register_for_event'


def details(**changes):
    return {'full_name': 'Alex Tan', 'contact_email': 'alex@example.com',
            'contact_phone': '+65 8123 4567', **changes}


def register(client, headers, event, payload=None):
    return client.post(f"/api/events/{event['event_id']}/registrations",
                       headers=headers, json=details() if payload is None else payload)


def records(event):
    return admin_request(f"/rest/v1/event_registration?event_id=eq.{event['event_id']}")


@pytest.fixture(scope='module')
def registration_flow(client, sign_in):
    for role in ('Attendee', 'Event Organiser', 'Event Coordinator Lead',
                 'Event Coordinator', 'Venue Staff', 'Safety Officer'):
        sign_in(role)
    flow = Flow(client, sign_in)
    try:
        yield flow
    finally:
        try:
            cleanup(flow)
        finally:
            for user_id in flow.users:
                admin_request(f'/auth/v1/admin/users/{user_id}', method='DELETE')


@pytest.fixture(scope='module')
def new_event(registration_flow):
    def make(state='open', capacity=40, waiting_list=False):
        event = submit_for_safety(registration_flow, capacity)
        event_id = event['event_id']
        registration_flow.call('Safety Officer', 'post',
            f'/api/operational-safety-reviews/{event_id}/decision', {'outcome': 'approved'})
        now = datetime.now(timezone.utc)
        opens, closes = {
            'open': (now - timedelta(days=1), now + timedelta(days=5)),
            'closed': (now - timedelta(days=2), now - timedelta(days=1)),
            'not_open': (now + timedelta(days=1), now + timedelta(days=5)),
        }[state]
        registration_flow.call('Event Organiser', 'patch', f'/api/events/{event_id}/registration-period', {
            'registration_opens_at': opens.isoformat(), 'registration_closes_at': closes.isoformat(),
            'waiting_list_enabled': waiting_list})
        return event
    return make


@pytest.fixture(scope='module')
def validation_event(new_event):
    return new_event()


@pytest.fixture(scope='module')
def successful_registration(client, sign_in, new_event):
    event = new_event()
    response = register(client, sign_in('Attendee'), event)
    assert response.status_code == 200, response.get_json()
    return event, response.get_json()


def test_tc_scrum33_001_personal_details_are_persisted_and_success_confirmed(successful_registration):
    event, result = successful_registration
    assert result['registration']['status'] == 'registered'
    assert result['message'] == 'You are registered for the event.'
    assert set(result) == {'registration', 'message'}
    assert result['registration']['event_id'] == event['event_id']
    assert result['registration']['attendee_id'] == user_id_for('Attendee')
    saved, = records(event)
    for field, value in details().items():
        assert result['registration'][field] == saved[field] == value


def test_tc_scrum33_002_personal_details_are_trimmed_before_persistence(client, sign_in, new_event):
    event = new_event()
    response = register(client, sign_in('Attendee'), event,
        details(full_name='  Alex Tan  ', contact_email=' alex@example.com ', contact_phone=' +65 8123 4567 '))
    assert response.status_code == 200, response.get_json()
    saved, = records(event)
    for field, value in details().items():
        assert saved[field] == response.get_json()['registration'][field] == value


INVALID_DETAILS = [
    pytest.param({key: value for key, value in details().items() if key != field}, id=f'TC-003-missing-{field}')
    for field in ('full_name', 'contact_email', 'contact_phone')
] + [
    pytest.param(details(full_name=' '), id='TC-003-blank-name'),
    pytest.param(details(full_name='a' * 151), id='TC-003-name-too-long'),
    pytest.param(details(contact_phone='letters'), id='TC-003-invalid-phone'),
    pytest.param(details(full_name=123), id='TC-009-numeric-name'),
    pytest.param(details(full_name='Alex\nTan'), id='TC-009-name-control-character'),
    pytest.param(details(contact_email='alex@example.com\r\nBcc: other@example.com'), id='TC-009-email-header-injection'),
    pytest.param(details(contact_phone='-------'), id='TC-009-phone-without-digits'),
]


@pytest.mark.parametrize('payload', INVALID_DETAILS)
def test_tc_scrum33_003_009_mandatory_and_unsafe_details_are_rejected(client, sign_in, validation_event, payload):
    before = records(validation_event)
    response = register(client, sign_in('Attendee'), validation_event, payload)
    assert response.status_code == 400
    assert response.get_json()['errors']
    assert 'registration' not in response.get_json()
    assert records(validation_event) == before == []


def test_tc_scrum33_004_empty_details_never_reach_registration_rpc(client, sign_in, validation_event):
    with patch.object(registration_service, 'supabase_request', wraps=registration_service.supabase_request) as rpc:
        response = register(client, sign_in('Attendee'), validation_event, {})
    assert response.status_code == 400
    assert response.get_json()['errors']
    rpc.assert_not_called()
    assert records(validation_event) == []


def test_tc_scrum33_005_closed_period_is_refused_by_real_database(client, sign_in, new_event):
    event = new_event('closed')
    response = register(client, sign_in('Attendee'), event)
    assert response.status_code == 409
    assert response.get_json() == {'error': 'Registration has closed.'}
    assert records(event) == []


def test_tc_scrum33_006_non_attendee_is_refused_by_real_database(client, sign_in, validation_event):
    response = register(client, sign_in('Event Organiser'), validation_event)
    assert response.status_code == 403
    assert response.get_json() == {'error': 'Only attendees can register for events.'}
    assert records(validation_event) == []


def test_tc_scrum33_007_authentication_is_required(client):
    response = client.post('/api/events/1/registrations', json=details())
    assert response.status_code == 401
    assert 'registration' not in response.get_json()


def inject_rpc(monkeypatch, *, body=None, http_status=200, outage=False):
    """Intercept only registration transport, forwarding actual auth requests."""
    original = event_store.urlopen
    calls = []

    def urlopen(request, *args, **kwargs):
        if urlsplit(request.full_url).path != RPC_PATH:
            return original(request, *args, **kwargs)
        calls.append(request)
        if outage:
            raise URLError('Controlled test outage')
        encoded = json.dumps(body).encode()
        if http_status != 200:
            raise HTTPError(request.full_url, http_status, 'Injected database response', {}, BytesIO(encoded))
        return BytesIO(encoded)

    monkeypatch.setattr(event_store, 'urlopen', urlopen)
    return calls


def test_tc_scrum33_008_structured_field_refusal_defaults_to_400(client, sign_in, validation_event, monkeypatch):
    headers = sign_in('Attendee')
    refusal = {'error': 'Cannot register.', 'errors': {'event_id': 'Registration unavailable.'}}
    calls = inject_rpc(monkeypatch, body=refusal)
    response = register(client, headers, validation_event)
    assert len(calls) == 1
    assert response.status_code == 400
    assert response.get_json() == refusal
    assert records(validation_event) == []


def test_tc_scrum33_010_email_syntax_is_not_checked(client, sign_in, new_event):
    event = new_event()
    response = register(client, sign_in('Attendee'), event, details(contact_email='not-an-email'))
    assert response.status_code == 200, response.get_json()
    saved, = records(event)
    assert saved['contact_email'] == response.get_json()['registration']['contact_email'] == 'not-an-email'


def test_tc_scrum33_011_missing_rpc_returns_configuration_guidance(client, sign_in, validation_event, monkeypatch):
    headers = sign_in('Attendee')
    calls = inject_rpc(monkeypatch, body={'code': 'PGRST202', 'message': 'Function not found.'}, http_status=404)
    response = register(client, headers, validation_event)
    assert len(calls) == 1
    assert response.status_code == 503
    assert '046_event_registration.sql' in response.get_json()['error']
    assert 'registration' not in response.get_json()


def test_tc_scrum33_012_storage_permission_failure_is_preserved_as_safe_http_error(
        client, sign_in, validation_event, monkeypatch):
    headers = sign_in('Attendee')
    calls = inject_rpc(monkeypatch, body={'code': '42501', 'message': 'Internal database detail.'}, http_status=403)
    response = register(client, headers, validation_event)
    assert len(calls) == 1
    assert response.status_code == 403
    assert response.get_json() == {'error': 'You do not have permission to change this event.'}
    assert 'Internal database detail.' not in response.get_data(as_text=True)


def test_tc_scrum33_013_non_object_rpc_result_is_forwarded(client, sign_in, validation_event, monkeypatch):
    headers = sign_in('Attendee')
    calls = inject_rpc(monkeypatch, body=[])
    response = register(client, headers, validation_event)
    assert len(calls) == 1
    assert response.status_code == 200
    assert response.get_json() == []
    assert json.loads(calls[0].data) == {'p_event_id': validation_event['event_id'],
        **{'p_' + key: value for key, value in details().items()}}


@pytest.mark.parametrize('http_status,body,outage,expected', [
    (409, {'code': '23514', 'message': 'Internal constraint detail.'}, False, 409),
    (401, {'message': 'Token refused.'}, False, 401),
    (200, None, True, 503),
])
def test_tc_scrum33_014_database_failures_return_safe_api_errors(
        client, sign_in, validation_event, monkeypatch, http_status, body, outage, expected):
    headers = sign_in('Attendee')
    calls = inject_rpc(monkeypatch, body=body, http_status=http_status, outage=outage)
    response = register(client, headers, validation_event)
    assert len(calls) == 1
    assert response.status_code == expected
    assert response.get_json()['error']
    assert 'registration' not in response.get_json()
    assert 'Internal constraint detail.' not in response.get_data(as_text=True)


@pytest.fixture(scope='module')
def filler(registration_flow):
    return registration_flow.user('SCRUM-33 capacity filler', 'Attendee')


@pytest.mark.parametrize('waiting_list', [False, True], ids=['capacity-refusal', 'explicit-waitlist'])
def test_ac4_full_event_refuses_extra_confirmed_place(client, sign_in, new_event, filler, waiting_list):
    event = new_event(capacity=1, waiting_list=waiting_list)
    first = register(client, filler['headers'], event)
    assert first.status_code == 200, first.get_json()
    assert first.get_json()['registration']['status'] == 'registered'
    second = register(client, sign_in('Attendee'), event)
    if waiting_list:
        assert second.status_code == 200, second.get_json()
        assert second.get_json()['registration']['status'] == 'waiting_list'
    else:
        assert second.status_code == 409
        assert second.get_json() == {'error': 'This event is full. The waiting list is disabled.'}
    rows = records(event)
    assert sum(row['status'] == 'registered' for row in rows) == 1
    assert len(rows) == (2 if waiting_list else 1)


def test_registration_before_opening_is_refused(client, sign_in, new_event):
    event = new_event('not_open')
    response = register(client, sign_in('Attendee'), event)
    assert response.status_code == 409
    assert response.get_json() == {'error': 'Registration is not yet open.'}
    assert records(event) == []
