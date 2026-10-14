"""API checks for the read-only Operational Safety Review story.

The database RPC applies the Safety Officer role and lifecycle status. These
tests ensure the Flask layer always authenticates first, calls the intended
RPC with the caller's token, and returns the review information unchanged.
"""
from unittest.mock import patch

from app import create_app


HEADERS = {'Authorization': 'Bearer safety-token'}
def client():
    return create_app().test_client()


@patch('app.routes.operational_safety.lifecycle_call')
@patch('app.routes.operational_safety.authenticated_token', return_value='safety-token')
def test_safety_officer_can_access_events_pending_safety_checks(token, call):
    queue = {'events': [{
        'event_id': 8, 'event_name': 'Welcome Night',
        'start_datetime': '2026-11-03T10:00:00Z',
        'end_datetime': '2026-11-03T12:00:00Z', 'capacity_needed': 180,
        'venue_name': 'Function Hall',
    }]}
    call.return_value = queue

    response = client().get('/api/operational-safety-reviews', headers=HEADERS)

    assert response.status_code == 200
    assert response.json == queue
    assert response.headers['Cache-Control'] == 'no-store'
    assert call.call_args.args == ('safety_review_queue', 'safety-token', {})


@patch('app.routes.operational_safety.lifecycle_call')
@patch('app.routes.operational_safety.authenticated_token', return_value='safety-token')
def test_safety_review_displays_all_required_arrangement_information(token, call):
    detail = {'event': {
        'event_id': 8, 'expected_attendance': 180, 'venue_capacity': 220,
        'room_layout': 'theatre', 'emergency_access': 'North entrance',
        'accessibility_requirements': ['Wheelchair accessibility required'],
        'equipment_placement': ['PA system – Hall rear'],
        'crowd_movement': 'Enter from east, exit north.',
        'venue_restrictions': 'Keep fire exits clear.',
    }}
    call.return_value = detail

    response = client().get('/api/operational-safety-reviews/8', headers=HEADERS)

    assert response.status_code == 200
    event = response.json['event']
    for field in ('expected_attendance', 'venue_capacity', 'room_layout', 'emergency_access',
                  'accessibility_requirements', 'equipment_placement', 'crowd_movement',
                  'venue_restrictions'):
        assert field in event
    assert call.call_args.args == ('safety_review_event', 'safety-token', {'p_event_id': 8})


@patch('app.routes.operational_safety.lifecycle_call')
@patch('app.routes.operational_safety.authenticated_token', return_value='safety-token')
def test_database_refusal_for_non_safety_officer_is_returned(token, call):
    from app.services.event_service import EventError
    call.side_effect = EventError('Only Safety Officers can review operational safety arrangements.', status=403)

    response = client().get('/api/operational-safety-reviews', headers=HEADERS)

    assert response.status_code == 403
    assert response.json['error'].startswith('Only Safety Officers')


@patch('app.routes.operational_safety.authenticated_token')
def test_safety_review_requires_sign_in(token):
    from app.services.event_store import StoreError
    token.side_effect = StoreError(401)
    response = client().get('/api/operational-safety-reviews')

    assert response.status_code == 401
    assert response.json == {'error': 'Please sign in again.'}


@patch('app.routes.operational_safety.authenticated_token')
def test_safety_review_service_outage_returns_a_safe_error(token):
    """Covers the non-authentication StoreError branch in the blueprint."""
    from app.services.event_store import StoreError
    token.side_effect = StoreError(503)

    response = client().get('/api/operational-safety-reviews', headers=HEADERS)

    assert response.status_code == 503
    assert response.json == {'error': 'Operational safety information is temporarily unavailable.'}


@patch('app.routes.operational_safety.lifecycle_call')
@patch('app.routes.operational_safety.authenticated_token', return_value='safety-token')
def test_safety_officer_decision_is_sent_to_the_database_workflow(token, call):
    decision = {
        'message': 'Safety changes requested. Address the remarks before proceeding.',
        'event': {'event_id': 8, 'status': 'planning'},
        'decision': {'outcome': 'changes_requested', 'remarks': 'Move the cable run away from the exit.'},
    }
    call.return_value = decision

    response = client().post('/api/operational-safety-reviews/8/decision', headers=HEADERS, json={
        'outcome': 'changes_requested',
        'remarks': 'Move the cable run away from the exit.',
        'affected_arrangements': ['technical'],
    })

    assert response.status_code == 200
    assert response.json == decision
    assert call.call_args.args == ('record_safety_decision', 'safety-token', {
        'p_event_id': 8,
        'p_outcome': 'changes_requested',
        'p_remarks': 'Move the cable run away from the exit.',
        'p_affected_arrangements': ['technical'],
    })


@patch('app.routes.operational_safety.lifecycle_call')
@patch('app.routes.operational_safety.authenticated_token', return_value='safety-token')
def test_invalid_safety_decision_is_returned_from_the_database(token, call):
    from app.services.event_service import EventError
    call.side_effect = EventError('Remarks are required when rejecting or requesting changes.', status=400)

    response = client().post('/api/operational-safety-reviews/8/decision', headers=HEADERS, json=['rejected'])

    assert response.status_code == 400
    assert response.json == {'error': 'Remarks are required when rejecting or requesting changes.'}
    assert call.call_args.args == ('record_safety_decision', 'safety-token', {
        'p_event_id': 8, 'p_outcome': None, 'p_remarks': None, 'p_affected_arrangements': None,
    })
