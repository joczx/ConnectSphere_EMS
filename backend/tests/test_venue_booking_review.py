"""Unit tests for Venue Staff approving or rejecting venue booking requests.

Each test names the acceptance criterion it covers. Supabase is mocked, so
these check the API's own behaviour; the role rules and the once-only decision
are the database's, and are verified against a real database separately (see
docs/venue-bookings.md).
"""
from unittest.mock import patch

import pytest

from app import create_app
from app.schemas.venue_booking_review import parse_review

HEADERS = {'Authorization': 'Bearer staff-token'}
BOOKING_ID = 'b21bdd3b-5fbb-4588-b070-f9a7e923ef02'
USER = {'id': 'staff'}

PENDING = {
    'booking_id': BOOKING_ID, 'status': 'submitted', 'event_name': 'Halloween',
    'event_id': 6, 'venue_name': 'Training Hall', 'attendance': 40,
    'starts_at': '2026-10-31T10:35:00+00:00', 'ends_at': '2026-10-31T15:35:00+00:00',
    'venue_requirements': 'Room layout: Classroom', 'current_shortfalls': [],
}


def client():
    return create_app().test_client()


# --- "requires Venue Staff to provide a reason when rejecting" -------------

def test_a_rejection_needs_a_reason():
    assert 'comments' in parse_review({'outcome': 'rejected', 'comments': '   '})[1]
    assert 'comments' in parse_review({'outcome': 'rejected'})[1]


def test_an_approval_does_not():
    data, errors = parse_review({'outcome': 'approved'})
    assert not errors
    assert data == {'outcome': 'approved', 'comments': ''}


def test_comments_are_trimmed():
    data, _ = parse_review({'outcome': 'rejected', 'comments': '  Closed for repairs.  '})
    assert data['comments'] == 'Closed for repairs.'


@pytest.mark.parametrize('body,field', [
    ({'outcome': 'maybe'}, 'outcome'),
    ({}, 'outcome'),
    ({'outcome': 'approved', 'comments': 42}, 'comments'),
    ({'outcome': 'approved', 'comments': 'x' * 2001}, 'comments'),
])
def test_invalid_decisions(body, field):
    assert field in parse_review(body)[1]


def test_a_decision_must_be_an_object():
    assert parse_review(['approved'])[1]


@patch('app.routes.venue_bookings.supabase_request', return_value=USER)
def test_a_rejection_without_a_reason_never_reaches_the_database(query):
    response = client().post(f'/api/venue-bookings/{BOOKING_ID}/review',
                             json={'outcome': 'rejected', 'comments': ''}, headers=HEADERS)
    assert response.status_code == 400
    assert 'comments' in response.json['errors']
    assert query.call_count == 1  # only the sign-in check


# --- "Venue Staff can approve or reject a venue booking request" ------------

@pytest.mark.parametrize('outcome,comments', [('approved', ''), ('rejected', 'Fully booked.')])
@patch('app.routes.venue_bookings.supabase_request')
def test_a_decision_is_recorded_by_the_database(query, outcome, comments):
    query.side_effect = [USER, {'booking': {**PENDING, 'status': outcome}}]
    response = client().post(f'/api/venue-bookings/{BOOKING_ID}/review',
                             json={'outcome': outcome, 'comments': comments}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json['booking']['status'] == outcome
    assert query.call_args.args[0] == '/rest/v1/rpc/review_venue_booking'
    assert query.call_args.kwargs['payload'] == {
        'p_booking_id': BOOKING_ID, 'p_outcome': outcome, 'p_comments': comments,
    }
    # The reviewer is whoever is signed in, so the caller's own token is used.
    assert query.call_args.kwargs['token'] == 'staff-token'


@patch('app.routes.venue_bookings.supabase_request')
def test_a_forged_reviewer_in_the_body_is_ignored(query):
    query.side_effect = [USER, {'booking': PENDING}]
    client().post(f'/api/venue-bookings/{BOOKING_ID}/review',
                  json={'outcome': 'approved', 'reviewed_by': 'someone-else'}, headers=HEADERS)
    assert 'p_reviewed_by' not in query.call_args.kwargs['payload']


@pytest.mark.parametrize('refusal,status', [
    ('Only Venue Staff can approve or reject venue bookings.', 403),
    ('This request has already been approved.', 409),
    ('Another member of Venue Staff decided this request first.', 409),
])
@patch('app.routes.venue_bookings.supabase_request')
def test_the_database_refusal_reaches_the_reviewer(query, refusal, status):
    query.side_effect = [USER, {'error': refusal, 'status': status}]
    response = client().post(f'/api/venue-bookings/{BOOKING_ID}/review',
                             json={'outcome': 'approved'}, headers=HEADERS)
    assert response.status_code == status
    assert response.json['error'] == refusal
    assert 'status' not in response.json


@patch('app.routes.venue_bookings.supabase_request')
def test_an_event_that_changed_since_the_request_blocks_approval(query):
    query.side_effect = [USER, {
        'error': 'The event has changed since this was requested, and the venue no longer meets its requirements. Reject the request instead.',
        'unmet_requirements': ['Holds 20, but 50 are expected.'],
        'status': 409,
    }]
    response = client().post(f'/api/venue-bookings/{BOOKING_ID}/review',
                             json={'outcome': 'approved'}, headers=HEADERS)
    assert response.status_code == 409
    assert response.json['unmet_requirements'] == ['Holds 20, but 50 are expected.']


@patch('app.routes.venue_bookings.supabase_request')
def test_a_malformed_id_is_not_found(query):
    query.return_value = USER
    response = client().post('/api/venue-bookings/not-a-uuid/review',
                             json={'outcome': 'approved'}, headers=HEADERS)
    assert response.status_code == 404


@patch('app.routes.venue_bookings.supabase_request')
def test_reviewing_requires_sign_in(query):
    response = client().post(f'/api/venue-bookings/{BOOKING_ID}/review', json={'outcome': 'approved'})
    assert response.status_code == 401
    query.assert_not_called()


# --- "view pending requests" and "displays relevant booking details" --------

@patch('app.routes.venue_bookings.supabase_request')
def test_one_request_is_read_with_its_details(query):
    query.side_effect = [USER, {'booking': PENDING, 'can_review': True}]
    response = client().get(f'/api/venue-bookings/{BOOKING_ID}', headers=HEADERS)
    assert response.status_code == 200
    booking = response.json['booking']
    for field in ('starts_at', 'ends_at', 'attendance', 'venue_requirements'):
        assert booking[field] == PENDING[field]
    assert response.json['can_review'] is True
    assert query.call_args.kwargs['payload'] == {'p_booking_id': BOOKING_ID}


@patch('app.routes.venue_bookings.supabase_request')
def test_a_request_the_caller_may_not_see_is_not_found(query):
    query.side_effect = [USER, {'error': 'Booking request not found or access unavailable.', 'status': 404}]
    response = client().get(f'/api/venue-bookings/{BOOKING_ID}', headers=HEADERS)
    assert response.status_code == 404


# --- "alerts the Event Coordinator on the status and the comments" ---------

@patch('app.routes.venue_bookings.supabase_request')
def test_the_coordinator_reads_their_alerts(query):
    alert = {'notification_id': 7, 'venue_booking_id': BOOKING_ID,
             'notification_type': 'venue_booking_rejected',
             'message': 'Your booking request for Training Hall (Halloween) was rejected. Comments: Fully booked.'}
    query.side_effect = [USER, [alert]]
    response = client().get('/api/venue-bookings/alerts', headers=HEADERS)
    assert response.status_code == 200
    assert response.json['alerts'] == [alert]
    assert query.call_args.args[0] == '/rest/v1/rpc/venue_booking_alerts'


@patch('app.routes.venue_bookings.supabase_request')
def test_alerts_are_dismissed_by_id(query):
    query.side_effect = [USER, {'dismissed': 2}]
    response = client().post('/api/venue-bookings/alerts/dismiss',
                             json={'notification_ids': [7, 8]}, headers=HEADERS)
    assert response.status_code == 200
    assert query.call_args.kwargs['payload'] == {'p_notification_ids': [7, 8]}


@pytest.mark.parametrize('body', [{}, {'notification_ids': []}, {'notification_ids': ['7']},
                                  {'notification_ids': [True]}, {'notification_ids': [0]}])
@patch('app.routes.venue_bookings.supabase_request', return_value=USER)
def test_dismissing_needs_real_alert_ids(query, body):
    response = client().post('/api/venue-bookings/alerts/dismiss', json=body, headers=HEADERS)
    assert response.status_code == 400
    assert query.call_count == 1
