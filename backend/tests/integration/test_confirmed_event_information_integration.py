"""SCRUM-157 live API tests: TC-SCRUM157-001 through 007 only.

AC4 checks /api/events?status=confirmed against real mixed-status fixtures.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.services import registration_service
from tests.integration.supabase_admin import admin_request, delete_as_user, user_id_for
from tests.integration.test_register_for_event_integration import registration_flow


def settings(**changes):
    now = datetime.now(timezone(timedelta(hours=8)))
    return {'registration_opens_at': (now - timedelta(days=1)).isoformat(),
            'registration_closes_at': (now + timedelta(days=5)).isoformat(),
            'waiting_list_enabled': False, **changes}


def read(client, sign_in, path, role='Event Organiser'):
    return client.get(path, headers=sign_in(role))


@pytest.fixture(scope='module')
def arranged_event(registration_flow, sign_in):
    flow = registration_flow
    sign_in('Technical Support Staff')
    event, venue, item = flow.event(), flow.venue(), flow.equipment_item()
    try:
        flow.decide(flow.book(event, venue), 'approved')
        requested = flow.request_equipment(event, item, 2, 'HDMI setup and testing')
        flow.review_equipment(requested, 'accepted', item, 2)
        flow.call('Event Coordinator', 'post', f"/api/events/{event['event_id']}/safety-checks")
        flow.call('Safety Officer', 'post', f"/api/operational-safety-reviews/{event['event_id']}/decision", {'outcome': 'approved'})
        yield event, venue, item, requested
    finally:
        event_id = event['event_id']
        admin_request(f'/rest/v1/equipment_reservations?event_id=eq.{event_id}', method='DELETE')
        admin_request(f'/rest/v1/equipment_request?event_id=eq.{event_id}', {
            'status': 'pending', 'accepted_quantity': None, 'reviewed_by': None, 'reviewed_at': None,
            'equipment_id': None, 'reason_for_rejection': None}, 'PATCH')
        delete_as_user(f'/rest/v1/equipment_request?event_id=eq.{event_id}', sign_in('Event Coordinator'))
        admin_request(f"/rest/v1/equipment?equipment_id=eq.{item['equipment_id']}", method='DELETE')


@pytest.fixture(scope='module')
def planning_event(registration_flow):
    return registration_flow.event()


@pytest.mark.parametrize('role', ['Event Organiser', 'Event Coordinator'])
def test_tc_scrum157_001_confirmed_times_and_approved_venue(client, sign_in, arranged_event, role):
    event, venue, _, _ = arranged_event
    response = read(client, sign_in, f"/api/events/{event['event_id']}", role)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()['event']
    assert result['status'] == 'confirmed'
    for field in ('event_id', 'event_name', 'start_datetime', 'end_datetime'):
        assert result[field] == event[field]
    assert response.headers['Cache-Control'] == 'no-store'
    response = read(client, sign_in, f"/api/venue-bookings/events/{event['event_id']}", role)
    assert response.status_code == 200, response.get_json()
    approved = [row for row in response.get_json()['bookings'] if row['status'] == 'approved']
    assert any(row['venue_id'] == venue['venue_id'] and row['venue_name'] == venue['venue_name'] for row in approved)
    assert response.headers['Cache-Control'] == 'no-store'


def test_tc_scrum157_002_accepted_equipment_and_assigned_support(client, sign_in, arranged_event):
    event, _, item, requested = arranged_event
    response = read(client, sign_in, f"/api/events/{event['event_id']}")
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['event']['technical_support_id'] == user_id_for('Technical Support Staff')
    response = read(client, sign_in, f"/api/events/{event['event_id']}/equipment-requests")
    assert response.status_code == 200, response.get_json()
    row, = [r for r in response.get_json()['equipment_requests'] if r['equipment_request_id'] == requested['equipment_request_id']]
    assert row['equipment_type'] == item['equipment_type']
    assert row['status'] == 'accepted'
    assert row['quantity'] == row['accepted_quantity'] == 2
    assert row['technical_requirements'] == 'HDMI setup and testing'


def test_tc_scrum157_003_opening_date_normalised_and_persisted(client, sign_in, arranged_event):
    event = arranged_event[0]
    payload = settings()
    with patch.object(registration_service, 'supabase_request', wraps=registration_service.supabase_request) as rpc:
        response = client.patch(f"/api/events/{event['event_id']}/registration-period", headers=sign_in('Event Organiser'), json=payload)
    assert response.status_code == 200, response.get_json()
    sent = rpc.call_args.kwargs['payload']
    saved = read(client, sign_in, f"/api/events/{event['event_id']}").get_json()['event']
    for field in ('registration_opens_at', 'registration_closes_at'):
        expected = datetime.fromisoformat(payload[field]).astimezone(timezone.utc)
        assert sent['p_' + field] == expected.isoformat()
        assert datetime.fromisoformat(saved[field]) == expected
        assert datetime.fromisoformat(response.get_json()['event'][field]) == expected


def test_tc_scrum157_004_catalogue_displays_only_confirmed_events(client, sign_in, arranged_event, planning_event):
    response = read(client, sign_in, '/api/events?status=confirmed')
    assert response.status_code == 200
    rows = response.get_json()['events']
    assert any(row['event_id'] == arranged_event[0]['event_id'] for row in rows)
    assert all(row['status'] == 'confirmed' for row in rows)
    assert all(row['event_id'] != planning_event['event_id'] for row in rows)


@pytest.mark.parametrize('changes,field', [
    ({'registration_opens_at': 'invalid'}, 'registration_opens_at'),
    ({'registration_opens_at': '2027-01-01T09:00:00'}, 'registration_opens_at'),
    ({'waiting_list_enabled': 'true'}, 'waiting_list_enabled'),
    ({'registration_closes_at': '2000-01-01T00:00:00+00:00'}, 'registration_closes_at'),
    (None, '_body'),
])
def test_tc_scrum157_005_invalid_settings_never_call_rpc(client, sign_in, arranged_event, changes, field):
    payload = {} if changes is None else settings(**changes)
    with patch.object(registration_service, 'supabase_request', wraps=registration_service.supabase_request) as rpc:
        response = client.patch(f"/api/events/{arranged_event[0]['event_id']}/registration-period", headers=sign_in('Event Organiser'), json=payload)
    assert response.status_code == 400
    assert field in response.get_json()['errors']
    rpc.assert_not_called()


def test_tc_scrum157_006_coordinator_cannot_set_period(client, sign_in, arranged_event):
    response = client.patch(f"/api/events/{arranged_event[0]['event_id']}/registration-period", headers=sign_in('Event Coordinator'), json=settings())
    assert response.status_code == 403, response.get_json()
    assert set(response.get_json()) == {'error'}


@pytest.mark.parametrize('stage', ['planning', 'pending_safety_checks', 'cancelled'])
def test_tc_scrum157_007_nonconfirmed_settings_refused(client, sign_in, registration_flow, stage):
    flow = registration_flow
    event = flow.event()
    if stage == 'pending_safety_checks':
        venue = flow.venue()
        flow.decide(flow.book(event, venue), 'approved')
        flow.call('Event Coordinator', 'post', f"/api/events/{event['event_id']}/safety-checks")
    elif stage == 'cancelled':
        flow.call('Event Organiser', 'post', f"/api/events/{event['event_id']}/cancel")
    actual = read(client, sign_in, f"/api/events/{event['event_id']}").get_json()['event']
    assert actual['status'] == stage
    with patch.object(registration_service, 'supabase_request', wraps=registration_service.supabase_request) as rpc:
        response = client.patch(f"/api/events/{event['event_id']}/registration-period", headers=sign_in('Event Organiser'), json=settings())
    assert response.status_code == 409, response.get_json()
    rpc.assert_not_called()
