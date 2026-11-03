"""SCRUM-32 integration cases TC-SCRUM32-001 through TC-SCRUM32-008.

From backend (PowerShell):
    $env:RUN_INTEGRATION_TESTS = '1'
    python -m pytest tests/integration/test_view_upcoming_events_integration.py -v

Uses the separate .env.integration-test project and real role accounts. Events
go through approval, venue booking and safety approval. Service-role requests
are for fixture setup/verification/cleanup, never the attendee request tested.

006/007 inject failures only at the catalogue RPC's HTTP transport; authentication
remains real. No database function is removed and no shared service is stopped.
004 checks exclusion of this run's ineligible records, without deleting other
tests' eligible events to force an empty shared catalogue. No tests are xfailed.
"""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit

import pytest

from app.services import event_store
from tests.integration.supabase_admin import admin_request
from tests.integration.test_notifications import Flow, submit_for_safety


CATALOGUE = '/api/registration-events'
RPC_PATH = '/rest/v1/rpc/attendee_registration_events'


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def read_catalogue(client, sign_in):
    response = client.get(CATALOGUE, headers=sign_in('Attendee'))
    assert response.status_code == 200, response.get_json()
    assert response.headers['Cache-Control'] == 'no-store'
    rows = response.get_json()['events']
    assert isinstance(rows, list)
    return rows


def cleanup(flow):
    """Remove only this run's data, even when an assertion fails."""
    errors = []

    def remove(path):
        try:
            admin_request(path, method='DELETE')
        except Exception as error:
            errors.append(f'{path}: {error}')

    for request_id in flow.requests:
        try:
            rows = admin_request(f'/rest/v1/events?select=event_id,event_name&event_request_id=eq.{request_id}')
        except Exception as error:
            errors.append(str(error))
            continue
        for event in rows:
            event_id = event['event_id']
            for table in ('event_registration', 'venue_booking_requests'):
                remove(f'/rest/v1/{table}?event_id=eq.{event_id}')
            name = quote(event['event_name'], safe='')
            remove(f'/rest/v1/notifications?notification_id=gt.{flow.since}&body=like.*{name}*')
            remove(f'/rest/v1/events?event_id=eq.{event_id}')
        remove(f'/rest/v1/event_request?event_request_id=eq.{request_id}')
    for venue_id in flow.venues:
        remove(f'/rest/v1/venues?venue_id=eq.{venue_id}')
    assert not errors, 'Fixture cleanup failed:\n' + '\n'.join(errors)


@pytest.fixture(scope='module')
def catalogue_flow(client, sign_in):
    for role in ('Attendee', 'Event Organiser', 'Event Coordinator Lead',
                 'Event Coordinator', 'Venue Staff', 'Safety Officer'):
        sign_in(role)
    flow = Flow(client, sign_in)
    try:
        yield flow
    finally:
        cleanup(flow)


@pytest.fixture(scope='module')
def make_confirmed_event(catalogue_flow):
    def make(state='open'):
        event = submit_for_safety(catalogue_flow)
        event_id = event['event_id']
        catalogue_flow.call('Safety Officer', 'post',
            f'/api/operational-safety-reviews/{event_id}/decision', {'outcome': 'approved'})
        now = datetime.now(timezone.utc)
        periods = {
            'open': (now - timedelta(days=1), now + timedelta(days=5)),
            'not_open': (now + timedelta(days=1), now + timedelta(days=5)),
            'closed': (now - timedelta(days=2), now - timedelta(days=1)),
            'cancelled': (now - timedelta(days=1), now + timedelta(days=5)),
        }
        opens, closes = periods[state]
        catalogue_flow.call('Event Organiser', 'patch', f'/api/events/{event_id}/registration-period', {
            'registration_opens_at': opens.isoformat(), 'registration_closes_at': closes.isoformat(),
            'waiting_list_enabled': False})
        if state == 'cancelled':
            catalogue_flow.call('Event Organiser', 'post', f'/api/events/{event_id}/cancel', {})
        stored, = admin_request(f'/rest/v1/events?select=*&event_id=eq.{event_id}')
        return {**stored, 'expected_venue_name': event['venue_name']}
    return make


@pytest.fixture(scope='module')
def open_events(make_confirmed_event):
    return [make_confirmed_event(), make_confirmed_event()]


def test_tc_scrum32_001_ac1_attendee_reads_two_real_upcoming_open_events(client, sign_in, open_events):
    """TC-001 / AC1: real confirmed, upcoming events are visible to Attendees."""
    events = {row['event_id']: row for row in read_catalogue(client, sign_in)}
    now = datetime.now(timezone.utc)
    for expected in open_events:
        assert expected['event_id'] in events
        event = events[expected['event_id']]
        assert event['status'] == 'confirmed'
        assert instant(event['start_datetime']) > now
        assert instant(event['registration_opens_at']) <= now < instant(event['registration_closes_at'])
        assert event['available_capacity'] == expected['capacity_needed']


def test_tc_scrum32_002_ac2_returns_persisted_details_and_approved_venue(client, sign_in, open_events):
    """TC-002 / AC2: compare attendee details with stored event and booked venue."""
    expected = open_events[0]
    event = next(row for row in read_catalogue(client, sign_in) if row['event_id'] == expected['event_id'])
    for field in ('event_name', 'description', 'waiting_list_enabled'):
        assert event[field] == expected[field], field
    for field in ('start_datetime', 'end_datetime', 'registration_opens_at', 'registration_closes_at'):
        assert instant(event[field]) == instant(expected[field]), field
    assert event['capacity'] == expected['capacity_needed']
    assert event['available_capacity'] == expected['capacity_needed']
    assert event['venues'] == [expected['expected_venue_name']], 'Apply migration 058 for attendee venue information.'


def test_tc_scrum32_003_ac3_next_read_reflects_committed_confirmed_event_update(
        client, sign_in, make_confirmed_event, catalogue_flow):
    """TC-003 / AC3: a supported post-confirmation edit appears on the next read.

    Confirmed arrangements are immutable; update registration settings through
    the Organiser API rather than bypassing lifecycle guards to edit the name.
    """
    expected = make_confirmed_event()
    event_id = expected['event_id']
    before = next(row for row in read_catalogue(client, sign_in) if row['event_id'] == event_id)
    closing = (instant(before['registration_closes_at']) + timedelta(hours=1)).isoformat()
    catalogue_flow.call('Event Organiser', 'patch', f'/api/events/{event_id}/registration-period', {
        'registration_opens_at': before['registration_opens_at'],
        'registration_closes_at': closing, 'waiting_list_enabled': True})
    persisted, = admin_request(f'/rest/v1/events?select=*&event_id=eq.{event_id}')
    after = next(row for row in read_catalogue(client, sign_in) if row['event_id'] == event_id)
    assert instant(after['registration_closes_at']) == instant(closing)
    assert after['registration_closes_at'] != before['registration_closes_at']
    assert after['waiting_list_enabled'] is True
    assert after['status'] == persisted['status'] == 'confirmed'
    for field in ('event_name', 'description'):
        assert after[field] == persisted[field], field
    for field in ('start_datetime', 'end_datetime'):
        assert instant(after[field]) == instant(persisted[field]), field
    assert after['venues'] == [expected['expected_venue_name']]


@pytest.mark.parametrize('state', ['cancelled', 'closed'])
def test_tc_scrum32_004_ac4_ineligible_test_events_are_absent(client, sign_in, make_confirmed_event, state):
    """TC-004 / AC4: persisted cancelled/closed events must be absent."""
    event = make_confirmed_event(state)
    owned_rows = [row for row in read_catalogue(client, sign_in) if row['event_id'] == event['event_id']]
    assert owned_rows == [], f'AC4: {state} event is still exposed: {owned_rows}'


def test_confirmed_event_is_hidden_before_opening_and_registration_is_refused(
        client, sign_in, make_confirmed_event):
    event = make_confirmed_event('not_open')
    rows = read_catalogue(client, sign_in)
    assert all(row['event_id'] != event['event_id'] for row in rows)
    response = client.post(f"/api/events/{event['event_id']}/registrations",
        headers=sign_in('Attendee'), json={'full_name': 'Early Attendee',
        'contact_email': 'early@connectsphere.invalid', 'contact_phone': '+65 6123 4567'})
    assert response.status_code == 409
    assert response.get_json() == {'error': 'Registration is not yet open.'}


def test_tc_scrum32_005_authentication_is_required(client):
    response = client.get(CATALOGUE)
    assert response.status_code == 401
    assert response.get_json() == {'error': 'Please sign in again.'}
    assert 'events' not in response.get_json()


def inject_rpc_transport_failure(monkeypatch, error_factory):
    """Fault only the catalogue transport, forwarding real auth HTTP requests."""
    real_urlopen = event_store.urlopen
    calls = []

    def urlopen(request, *args, **kwargs):
        if urlsplit(request.full_url).path == RPC_PATH:
            calls.append(request.full_url)
            raise error_factory(request)
        return real_urlopen(request, *args, **kwargs)

    monkeypatch.setattr(event_store, 'urlopen', urlopen)
    return calls


def test_tc_scrum32_006_missing_registration_rpc_is_reported(client, sign_in, monkeypatch):
    """TC-006: missing-function HTTP response becomes configuration guidance."""
    headers = sign_in('Attendee')
    body = json.dumps({'code': 'PGRST202', 'message': 'Function not found.'}).encode()
    calls = inject_rpc_transport_failure(monkeypatch, lambda request:
        HTTPError(request.full_url, 404, 'Not Found', {}, BytesIO(body)))
    response = client.get(CATALOGUE, headers=headers)
    assert len(calls) == 1
    assert response.status_code == 503
    assert response.get_json()['error'].startswith('Registration is not configured yet.')
    assert 'events' not in response.get_json()


def test_tc_scrum32_007_unavailable_database_is_not_an_empty_catalogue(client, sign_in, monkeypatch):
    """TC-007: transport outage becomes 503 rather than a successful empty list."""
    headers = sign_in('Attendee')
    calls = inject_rpc_transport_failure(monkeypatch, lambda request: URLError('Injected database outage'))
    response = client.get(CATALOGUE, headers=headers)
    assert len(calls) == 1
    assert response.status_code == 503
    assert response.get_json() == {'error': 'Event service is temporarily unavailable.'}
    assert 'events' not in response.get_json()


def test_tc_scrum32_008_non_attendee_receives_real_database_refusal(client, sign_in):
    """TC-008: a real non-attendee token is refused by the database RPC."""
    response = client.get(CATALOGUE, headers=sign_in('Event Organiser'))
    assert response.status_code == 403
    assert response.get_json() == {'error': 'Only attendees can browse registration events.'}
    assert 'events' not in response.get_json()
