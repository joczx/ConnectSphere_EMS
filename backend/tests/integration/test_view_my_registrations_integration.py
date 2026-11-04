"""SCRUM-34 integration cases TC-SCRUM34-001--010.

Run from backend with RUN_INTEGRATION_TESTS=1. Normal cases use real users,
registrations, withdrawals and the isolated .env.integration-test database.
008/009 inject only the my_event_registrations HTTP transport failure, forwarding
real authentication. 010 exercises a real database role refusal. No shared RPC
is removed and no database is stopped. Fixtures clean up only their own data.

AC4 here checks the API empty-list contract. The visible no-records message and
status-label/date rendering are covered by frontend component/end-to-end tests.
"""
from io import BytesIO
from datetime import datetime
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

import pytest

from app.services import event_store, registration_service
from tests.integration.supabase_admin import admin_request
from tests.integration.test_register_for_event_integration import (
    details, new_event, register, registration_flow,
)


PATH = '/api/my-registrations'
RPC_PATH = '/rest/v1/rpc/my_event_registrations'


def get_registrations(client, attendee, query=''):
    response = client.get(PATH + query, headers=attendee['headers'])
    assert response.status_code == 200, response.get_json()
    assert response.headers['Cache-Control'] == 'no-store'
    assert isinstance(response.get_json()['registrations'], list)
    return response.get_json()['registrations']


@pytest.fixture(scope='module')
def attendees(registration_flow):
    return {name: registration_flow.user(f'SCRUM-34 {name}', 'Attendee')
            for name in ('owner', 'filler', 'empty')}


@pytest.fixture(scope='module')
def registration_records(client, new_event, attendees):
    """Distinct events for Confirmed, Waitlisted and Withdrawn registrations."""
    owner = attendees['owner']
    confirmed = new_event()
    response = register(client, owner['headers'], confirmed, details(full_name='SCRUM-34 owner'))
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['registration']['status'] == 'registered'

    waitlisted = new_event(capacity=1, waiting_list=True)
    first = register(client, attendees['filler']['headers'], waitlisted)
    assert first.status_code == 200, first.get_json()
    assert first.get_json()['registration']['status'] == 'registered'
    second = register(client, owner['headers'], waitlisted)
    assert second.status_code == 200, second.get_json()
    assert second.get_json()['registration']['status'] == 'waiting_list'

    withdrawn = new_event()
    response = register(client, owner['headers'], withdrawn)
    assert response.status_code == 200, response.get_json()
    response = client.post(f"/api/events/{withdrawn['event_id']}/registrations/withdraw",
                           headers=owner['headers'])
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['registration']['status'] == 'withdrawn'
    return {'registered': confirmed, 'waiting_list': waitlisted, 'withdrawn': withdrawn}


def test_tc_scrum34_001_attendee_views_their_real_registered_events(client, attendees, registration_records):
    rows = get_registrations(client, attendees['owner'])
    assert len(rows) == 3
    assert {row['event_id'] for row in rows} == {event['event_id'] for event in registration_records.values()}


@pytest.mark.parametrize('status', ['registered', 'waiting_list', 'withdrawn'],
                         ids=['Confirmed', 'Waitlisted', 'Withdrawn'])
def test_tc_scrum34_002_each_current_registration_status_is_returned(client, attendees, registration_records, status):
    rows = get_registrations(client, attendees['owner'])
    event_id = registration_records[status]['event_id']
    record = next(row for row in rows if row['event_id'] == event_id)
    assert record['status'] == status
    if status == 'withdrawn':
        assert record['withdrawn_at']


def test_tc_scrum34_003_returns_persisted_event_dates_times_and_approved_venue(
        client, attendees, registration_records):
    event = registration_records['registered']
    persisted, = admin_request(f"/rest/v1/events?select=event_id,event_name,start_datetime,end_datetime&event_id=eq.{event['event_id']}")
    rows = get_registrations(client, attendees['owner'])
    record = next(row for row in rows if row['event_id'] == event['event_id'])
    assert record['event_id'] == persisted['event_id']
    assert record['event_name'] == persisted['event_name']
    for field in ('start_datetime', 'end_datetime'):
        returned_time = datetime.fromisoformat(record[field].replace('Z', '+00:00'))
        stored_time = datetime.fromisoformat(persisted[field].replace('Z', '+00:00'))
        assert returned_time.tzinfo is not None
        assert returned_time == stored_time, field
    assert record['venues'] == [event['venue_name']]


def test_tc_scrum34_004_fresh_attendee_receives_empty_records(client, attendees):
    assert get_registrations(client, attendees['empty']) == []


def test_tc_scrum34_005_next_read_reflects_real_withdrawal(client, registration_flow, new_event):
    # A dedicated user/event avoids changing fixtures used by the status tests.
    attendee = registration_flow.user('SCRUM-34 changing status', 'Attendee')
    event = new_event()
    response = register(client, attendee['headers'], event)
    assert response.status_code == 200, response.get_json()
    before, = get_registrations(client, attendee)
    assert before['status'] == 'registered'

    response = client.post(f"/api/events/{event['event_id']}/registrations/withdraw",
                           headers=attendee['headers'])
    assert response.status_code == 200, response.get_json()
    after, = get_registrations(client, attendee)
    assert after['event_id'] == before['event_id'] == event['event_id']
    assert after['status'] == 'withdrawn'
    assert after['registered_at'] == before['registered_at']
    assert after['withdrawn_at'] == response.get_json()['registration']['withdrawn_at']


def test_tc_scrum34_006_authentication_is_required_without_calling_rpc(client):
    with patch.object(registration_service, 'supabase_request', wraps=registration_service.supabase_request) as rpc:
        response = client.get(PATH)
    assert response.status_code == 401
    assert response.get_json() == {'error': 'Please sign in again.'}
    rpc.assert_not_called()


def test_tc_scrum34_007_query_identity_cannot_expose_another_attendees_records(
        client, attendees, registration_records):
    # The empty user cannot read the owner's records by supplying their ID.
    assert get_registrations(client, attendees['empty'],
        f"?attendee_id={attendees['owner']['id']}") == []
    # Nor can a supplied empty-user ID override the real owner's identity.
    own = get_registrations(client, attendees['owner'],
        f"?attendee_id={attendees['empty']['id']}")
    assert {row['event_id'] for row in own} == {event['event_id'] for event in registration_records.values()}


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


def test_tc_scrum34_008_missing_function_is_not_reported_as_empty_records(client, sign_in, monkeypatch):
    headers = sign_in('Attendee')
    body = json.dumps({'code': 'PGRST202', 'message': 'Function not found.'}).encode()
    calls = inject_rpc_failure(monkeypatch, lambda request:
        HTTPError(request.full_url, 404, 'Not Found', {}, BytesIO(body)))
    response = client.get(PATH, headers=headers)
    assert len(calls) == 1
    assert response.status_code == 503
    assert response.get_json() == {'error': 'Registration is not configured yet. Apply supabase/046_event_registration.sql through 052_event_registration_roster.sql in order.'}
    assert 'registrations' not in response.get_json()


def test_tc_scrum34_009_database_outage_is_not_reported_as_empty_records(client, sign_in, monkeypatch):
    headers = sign_in('Attendee')
    calls = inject_rpc_failure(monkeypatch, lambda request: URLError('Controlled test outage'))
    response = client.get(PATH, headers=headers)
    assert len(calls) == 1
    assert response.status_code == 503
    assert response.get_json() == {'error': 'Event service is temporarily unavailable.'}
    assert 'registrations' not in response.get_json()


def test_tc_scrum34_010_real_non_attendee_request_returns_refusal(client, sign_in):
    response = client.get(PATH, headers=sign_in('Event Organiser'))
    assert response.status_code == 403
    assert response.get_json() == {'error': 'Only attendees can view their registrations.'}
    assert 'registrations' not in response.get_json()
