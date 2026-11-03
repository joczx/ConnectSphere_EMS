"""SCRUM-36: unit tests for viewing managed-event registration information.

Supabase is mocked here. Actual role/assignment enforcement and status counts
are exercised separately by frontend/tests/registration-db.mjs.
"""
from unittest.mock import patch

import pytest

from app import create_app


@pytest.fixture
def roster():
    return {
        'event': {'event_id': 41, 'event_name': 'Community Technology Fair'},
        'total_registered': 1, 'total_waitlisted': 1, 'total_withdrawn': 1,
        'registrations': [
            {'attendee_id': 'attendee-1', 'full_name': 'Alex Tan',
             'contact_email': 'alex@example.com', 'contact_phone': '+65 8123 4567',
             'status': 'registered', 'registered_at': '2027-05-01T09:00:00+08:00',
             'withdrawn_at': None},
            {'attendee_id': 'attendee-2', 'full_name': 'Jamie Lim',
             'contact_email': 'jamie@example.com', 'contact_phone': '+65 8234 5678',
             'status': 'waiting_list', 'registered_at': '2027-05-01T10:00:00+08:00',
             'withdrawn_at': None},
            {'attendee_id': 'attendee-3', 'full_name': 'Sam Lee',
             'contact_email': 'sam@example.com', 'contact_phone': '+65 8345 6789',
             'status': 'withdrawn', 'registered_at': '2027-05-01T11:00:00+08:00',
             'withdrawn_at': '2027-05-02T12:00:00+08:00'},
        ],
    }


def fetch_roster(result, actor='organiser', event_id=41):
    client = create_app().test_client()
    token = f'verified-{actor}'
    with patch('app.routes.events.supabase_request', return_value={'id': actor}) as auth, \
         patch('app.services.registration_service.supabase_request', return_value=result) as rpc:
        response = client.get(f'/api/events/{event_id}/registrations?event_organiser_id=someone-else',
                              headers={'Authorization': f'Bearer {token}'})
    auth.assert_called_once_with('/auth/v1/user', token=token)
    rpc.assert_called_once_with('/rest/v1/rpc/event_registration_roster', token=token,
                               payload={'p_event_id': event_id}, method='POST')
    return response


@pytest.mark.parametrize('actor', ['organiser', 'coordinator'])
def test_tc_scrum36_001_002_004_authorised_roster_details_and_statuses(roster, actor):
    """TC-SCRUM36-001/002/004: AC1 access, AC2 contacts and AC4 statuses.

    Role and assignment decisions are mocked, not evaluated by Python.
    """
    response = fetch_roster(roster, actor=actor)
    assert response.status_code == 200
    assert response.json == roster
    assert response.json['event']['event_id'] == 41
    records = response.json['registrations']
    assert len(records) == 3
    for returned, expected in zip(records, roster['registrations']):
        for field in ('attendee_id', 'full_name', 'contact_email', 'contact_phone', 'status', 'withdrawn_at'):
            assert returned[field] == expected[field], field
    assert [item['status'] for item in records] == ['registered', 'waiting_list', 'withdrawn']
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('registered_count', [0, 1, 3])
def test_tc_scrum36_003_ac3_returns_registered_total_separately_from_other_statuses(
        roster, registered_count):
    """AC3: return the supplied confirmed total, excluding other statuses.

    The database computes totals; this test verifies API serialization only.
    """
    confirmed = [dict(roster['registrations'][0], attendee_id=f'confirmed-{i}')
                 for i in range(registered_count)]
    result = {**roster, 'total_registered': registered_count,
              'registrations': confirmed + roster['registrations'][1:]}
    response = fetch_roster(result)
    assert response.status_code == 200
    assert response.json['total_registered'] == registered_count
    assert response.json['total_waitlisted'] == 1
    assert response.json['total_withdrawn'] == 1
    assert len(response.json['registrations']) == registered_count + 2


def test_tc_scrum36_003_ac3_event_without_attendees_returns_zero_totals(roster):
    result = {**roster, 'total_registered': 0, 'total_waitlisted': 0,
              'total_withdrawn': 0, 'registrations': []}
    response = fetch_roster(result)
    assert response.status_code == 200
    assert response.json == result


@pytest.mark.parametrize('actor,status,message', [
    ('unassigned-organiser', 404, 'Event not found or access unavailable.'),
    ('unassigned-coordinator', 404, 'Event not found or access unavailable.'),
    ('attendee', 403, 'Only event organisers and coordinators can view registration information.'),
])
def test_tc_scrum36_005_ac5_access_refusal_exposes_no_registration_information(actor, status, message):
    """AC5: propagate RPC access refusals without returning roster data."""
    response = fetch_roster({'error': message, 'status': status}, actor=actor)
    assert response.status_code == status
    assert response.json == {'error': message}
    for field in ('event', 'registrations', 'total_registered', 'total_waitlisted', 'total_withdrawn'):
        assert field not in response.json


def test_event_roster_requires_authentication():
    client = create_app().test_client()
    with patch('app.services.registration_service.supabase_request') as rpc:
        assert client.get('/api/events/1/registrations').status_code == 401
        rpc.assert_not_called()


# AC1-4: verified identity, managed event, contact details, totals and statuses.


# AC5: unauthorised responses must not expose attendee information.
