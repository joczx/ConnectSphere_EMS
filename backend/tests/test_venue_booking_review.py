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
BOOKINGS_URL = '/api/venue-bookings'
USER = {'id': 'staff'}

PENDING = {
    'booking_id': BOOKING_ID, 'status': 'submitted', 'event_name': 'Halloween',
    'event_id': 6, 'venue_name': 'Training Hall', 'attendance': 40,
    'starts_at': '2026-10-31T10:35:00+00:00', 'ends_at': '2026-10-31T15:35:00+00:00',
    'venue_requirements': 'Room layout: Classroom', 'current_shortfalls': [],
}


def client():
    return create_app().test_client()


def review_request(body, booking_id=BOOKING_ID, headers=HEADERS):
    """Send a venue-staff decision, omitting auth when a test needs to."""
    options = {'json': body}
    if headers is not None:
        options['headers'] = headers
    return client().post(f'{BOOKINGS_URL}/{booking_id}/review', **options)


# --- "requires Venue Staff to provide a reason when rejecting" -------------

# Ensures rejected decisions require a non-blank reason.
def test_a_rejection_needs_a_reason():
    assert 'comments' in parse_review({'outcome': 'rejected', 'comments': '   '})[1]
    assert 'comments' in parse_review({'outcome': 'rejected'})[1]


# Verifies an approval remains valid when no comments are supplied.
def test_an_approval_does_not():
    data, errors = parse_review({'outcome': 'approved'})
    assert not errors
    assert data == {'outcome': 'approved', 'comments': ''}


# Ensures valid comments are trimmed before being sent to the review workflow.
def test_comments_are_trimmed():
    data, _ = parse_review({'outcome': 'rejected', 'comments': '  Closed for repairs.  '})
    assert data['comments'] == 'Closed for repairs.'


# Ensures invalid outcomes and comment values are rejected by decision validation.
@pytest.mark.parametrize('body,field', [
    ({'outcome': 'maybe'}, 'outcome'),
    ({}, 'outcome'),
    ({'outcome': 'approved', 'comments': 42}, 'comments'),
    ({'outcome': 'approved', 'comments': 'x' * 2001}, 'comments'),
])
def test_invalid_decisions(body, field):
    assert field in parse_review(body)[1]


# Ensures a review decision body must be a JSON object.
def test_a_decision_must_be_an_object():
    assert parse_review(['approved'])[1]


# Ensures an invalid rejection is stopped before the review RPC is called.
@patch('app.routes.venue_bookings.supabase_request', return_value=USER)
def test_a_rejection_without_a_reason_never_reaches_the_database(query):
    response = review_request({'outcome': 'rejected', 'comments': ''})
    assert response.status_code == 400
    assert 'comments' in response.json['errors']
    assert query.call_count == 1  # only the sign-in check


# --- "Venue Staff can approve or reject a venue booking request" ------------

# Verifies valid approval and rejection decisions are forwarded and persisted.
@pytest.mark.parametrize('outcome,comments', [('approved', ''), ('rejected', 'Fully booked.')])
@patch('app.routes.venue_bookings.supabase_request')
def test_a_decision_is_recorded_by_the_database(query, outcome, comments):
    query.side_effect = [USER, {'booking': {**PENDING, 'status': outcome}}]
    response = review_request({'outcome': outcome, 'comments': comments})
    assert response.status_code == 200
    assert response.json['booking']['status'] == outcome
    assert query.call_args.args[0] == '/rest/v1/rpc/review_venue_booking'
    assert query.call_args.kwargs['payload'] == {
        'p_booking_id': BOOKING_ID, 'p_outcome': outcome, 'p_comments': comments,
    }
    # The reviewer is whoever is signed in, so the caller's own token is used.
    assert query.call_args.kwargs['token'] == 'staff-token'


# Ensures a forged reviewer value cannot override the signed-in reviewer.
@patch('app.routes.venue_bookings.supabase_request')
def test_a_forged_reviewer_in_the_body_is_ignored(query):
    query.side_effect = [USER, {'booking': PENDING}]
    review_request({'outcome': 'approved', 'reviewed_by': 'someone-else'})
    assert 'p_reviewed_by' not in query.call_args.kwargs['payload']


# Ensures database review refusals retain their status and message for the caller.
@pytest.mark.parametrize('refusal,status', [
    ('Only Venue Staff can approve or reject venue bookings.', 403),
    ('This request has already been approved.', 409),
    ('Another member of Venue Staff decided this request first.', 409),
])
@patch('app.routes.venue_bookings.supabase_request')
def test_the_database_refusal_reaches_the_reviewer(query, refusal, status):
    query.side_effect = [USER, {'error': refusal, 'status': status}]
    response = review_request({'outcome': 'approved'})
    assert response.status_code == status
    assert response.json['error'] == refusal
    assert 'status' not in response.json


# Ensures approval is blocked when changed event details no longer fit the venue.
@patch('app.routes.venue_bookings.supabase_request')
def test_an_event_that_changed_since_the_request_blocks_approval(query):
    query.side_effect = [USER, {
        'error': 'The event has changed since this was requested, and the venue no longer meets its requirements. Reject the request instead.',
        'unmet_requirements': ['Holds 20, but 50 are expected.'],
        'status': 409,
    }]
    response = review_request({'outcome': 'approved'})
    assert response.status_code == 409
    assert response.json['unmet_requirements'] == ['Holds 20, but 50 are expected.']


# Ensures review rejects a malformed booking ID before calling the review RPC.
@patch('app.routes.venue_bookings.supabase_request')
def test_a_malformed_id_is_not_found(query):
    query.return_value = USER
    response = review_request({'outcome': 'approved'}, booking_id='not-a-uuid')
    assert response.status_code == 404


# Ensures only signed-in users can submit a Venue Staff decision.
@patch('app.routes.venue_bookings.supabase_request')
def test_reviewing_requires_sign_in(query):
    response = review_request({'outcome': 'approved'}, headers=None)
    assert response.status_code == 401
    query.assert_not_called()


# --- "view pending requests" and "displays relevant booking details" --------

# Verifies Venue Staff can read a pending request with all required booking details.
@patch('app.routes.venue_bookings.supabase_request')
def test_one_request_is_read_with_its_details(query):
    query.side_effect = [USER, {'booking': PENDING, 'can_review': True}]
    response = client().get(f'{BOOKINGS_URL}/{BOOKING_ID}', headers=HEADERS)
    assert response.status_code == 200
    booking = response.json['booking']
    for field in ('starts_at', 'ends_at', 'attendance', 'venue_requirements'):
        assert booking[field] == PENDING[field]
    assert response.json['can_review'] is True
    assert query.call_args.kwargs['payload'] == {'p_booking_id': BOOKING_ID}


# Ensures a booking unavailable to the caller is returned as not found.
@patch('app.routes.venue_bookings.supabase_request')
def test_a_request_the_caller_may_not_see_is_not_found(query):
    query.side_effect = [USER, {'error': 'Booking request not found or access unavailable.', 'status': 404}]
    response = client().get(f'{BOOKINGS_URL}/{BOOKING_ID}', headers=HEADERS)
    assert response.status_code == 404
