"""SCRUM-36 TC001--009: real managed-event rosters; transport faults for 008/009."""
from io import BytesIO
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

import pytest

from app.services import event_store, registration_service
from tests.integration.test_register_for_event_integration import (
    details, new_event, records, register, registration_flow,
)


def roster(client, headers, event):
    return client.get(f"/api/events/{event['event_id']}/registrations", headers=headers)


def withdraw(client, user, event):
    response = client.post(f"/api/events/{event['event_id']}/registrations/withdraw", headers=user['headers'])
    assert response.status_code == 200, response.get_json()


@pytest.fixture(scope='module')
def actors(registration_flow):
    return {name: registration_flow.user(name, role) for name, role in [
        ('Alex Tan', 'Attendee'), ('Jamie Lim', 'Attendee'), ('Sam Lee', 'Attendee'),
        ('Extra One', 'Attendee'), ('Extra Two', 'Attendee'),
        ('Unassigned organiser', 'Event Organiser'), ('Unassigned coordinator', 'Event Coordinator'),
    ]}


@pytest.fixture(scope='module')
def make_roster(client, new_event, actors):
    def make(count):
        event = new_event(capacity=max(1, count), waiting_list=True)
        expected = {}

        def add(name, status):
            user = actors[name]
            payload = details(full_name=name, contact_email=name.lower().replace(' ', '.') + '@example.com')
            response = register(client, user['headers'], event, payload)
            assert response.status_code == 200, response.get_json()
            assert response.get_json()['registration']['status'] == status
            expected[user['id']] = {**payload, 'status': status}

        add('Sam Lee', 'registered')
        if count:
            withdraw(client, actors['Sam Lee'], event)
            expected[actors['Sam Lee']['id']]['status'] = 'withdrawn'
            for name in ['Alex Tan', 'Extra One', 'Extra Two'][:count]:
                add(name, 'registered')
        add('Jamie Lim', 'waiting_list')
        if not count:
            withdraw(client, actors['Sam Lee'], event)
            expected[actors['Sam Lee']['id']]['status'] = 'withdrawn'
        return event, expected
    return make


@pytest.fixture(scope='module')
def mixed_roster(make_roster):
    return make_roster(1)


@pytest.mark.parametrize('role', ['Event Organiser', 'Event Coordinator'])
def test_tc_scrum36_001_002_004_managers_read_real_contacts_and_statuses(client, sign_in, mixed_roster, role):
    event, expected = mixed_roster
    response = roster(client, sign_in(role), event)
    assert response.status_code == 200, response.get_json()
    assert response.headers['Cache-Control'] == 'no-store'
    result = response.get_json()
    assert result['event'] == {key: event[key] for key in ('event_id', 'event_name')}
    returned = {row['attendee_id']: row for row in result['registrations']}
    assert set(returned) == set(expected)
    saved = {row['attendee_id']: row for row in records(event)}
    for attendee_id, fields in expected.items():
        for field, value in fields.items():
            assert returned[attendee_id][field] == saved[attendee_id][field] == value
        assert returned[attendee_id]['registered_at']
        assert bool(returned[attendee_id]['withdrawn_at']) == (fields['status'] == 'withdrawn')


@pytest.mark.parametrize('count', [0, 1, 3])
def test_tc_scrum36_003_real_database_counts_statuses_separately(client, sign_in, make_roster, mixed_roster, count):
    event, expected = mixed_roster if count == 1 else make_roster(count)
    response = roster(client, sign_in('Event Organiser'), event)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result['total_registered'] == count
    assert result['total_waitlisted'] == 1
    assert result['total_withdrawn'] == 1
    assert len(result['registrations']) == len(expected) == count + 2
    for status, field in [('registered', 'total_registered'), ('waiting_list', 'total_waitlisted'), ('withdrawn', 'total_withdrawn')]:
        assert sum(row['status'] == status for row in records(event)) == result[field]


@pytest.mark.parametrize('actor,status,message', [
    ('Unassigned organiser', 404, 'Event not found or access unavailable.'),
    ('Unassigned coordinator', 404, 'Event not found or access unavailable.'),
    ('Alex Tan', 403, 'Only event organisers and coordinators can view registration information.'),
])
def test_tc_scrum36_005_real_unauthorised_roles_receive_no_roster(client, actors, mixed_roster, actor, status, message):
    event, _ = mixed_roster
    response = roster(client, actors[actor]['headers'], event)
    assert response.status_code == status, response.get_json()
    assert response.get_json() == {'error': message}


@pytest.mark.parametrize('role', ['Event Organiser', 'Event Coordinator'])
def test_tc_scrum36_006_empty_event_has_zero_totals(client, sign_in, new_event, role):
    event = new_event()
    response = roster(client, sign_in(role), event)
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == {
        'event': {key: event[key] for key in ('event_id', 'event_name')},
        'total_registered': 0, 'total_waitlisted': 0, 'total_withdrawn': 0, 'registrations': [],
    }
    assert response.headers['Cache-Control'] == 'no-store'


def test_tc_scrum36_007_authentication_required_without_rpc(client):
    with patch.object(registration_service, 'supabase_request', wraps=registration_service.supabase_request) as rpc:
        response = client.get('/api/events/1/registrations')
    assert response.status_code == 401
    assert response.get_json() == {'error': 'Please sign in again.'}
    rpc.assert_not_called()


@pytest.mark.parametrize('missing,message', [
    pytest.param(True, 'Registration is not configured yet. Apply supabase/046_event_registration.sql through 052_event_registration_roster.sql in order.', id='TC-SCRUM36-008'),
    pytest.param(False, 'Event service is temporarily unavailable.', id='TC-SCRUM36-009'),
])
def test_tc_scrum36_008_009_transport_errors_expose_no_roster(client, sign_in, mixed_roster, monkeypatch, missing, message):
    event, _ = mixed_roster
    headers = sign_in('Event Organiser')
    original = event_store.urlopen
    calls = []
    before = records(event)

    def urlopen(request, *args, **kwargs):
        if urlsplit(request.full_url).path == '/rest/v1/rpc/event_registration_roster':
            calls.append(request)
            if missing:
                body = json.dumps({'code': 'PGRST202', 'message': 'Function not found.'}).encode()
                raise HTTPError(request.full_url, 404, 'Not Found', {}, BytesIO(body))
            raise URLError('Controlled test outage')
        return original(request, *args, **kwargs)

    monkeypatch.setattr(event_store, 'urlopen', urlopen)
    response = roster(client, headers, event)
    assert len(calls) == 1
    assert response.status_code == 503
    assert response.get_json() == {'error': message}
    assert records(event) == before
