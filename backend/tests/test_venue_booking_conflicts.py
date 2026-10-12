"""Unit tests for identifying overlapping or conflicting venue bookings.

Each test names the acceptance criterion it covers. Supabase is mocked: the
refusals themselves, and the constraint that stops two overlapping approvals
under concurrency, are the database's (027_venue_booking_conflicts.sql) and are
verified against a real database separately.
"""
from unittest.mock import patch

import pytest

from app import create_app
from app.services.venue_availability import attach_conflicts, overlaps

HEADERS = {'Authorization': 'Bearer coordinator-token'}
USER = {'id': 'coordinator'}
HALL = 'b21bdd3b-5fbb-4588-b070-f9a7e923ef02'
ROOM = '3cf6f106-e05a-45ce-a6e5-825afcbf23cd'

# Saturday 31 October 2026, 18:00 to 21:00 in Singapore.
EVENING = ('2026-10-31T10:00:00+00:00', '2026-10-31T13:00:00+00:00')

EVENT = {
    'event_id': 6, 'event_name': 'Halloween', 'status': 'planning',
    'start_datetime': EVENING[0], 'end_datetime': EVENING[1],
}


def booking(starts, ends, venue_id=HALL, status='approved', **extra):
    return {'booking_id': 'b-' + starts, 'venue_id': venue_id, 'status': status,
            'starts_at': starts, 'ends_at': ends, **extra}


# --- "checks a request against existing bookings for the same venue and time" --

@pytest.mark.parametrize('other,expected', [
    (EVENING, True),                                                          # identical
    (('2026-10-31T09:00:00+00:00', '2026-10-31T11:00:00+00:00'), True),      # overlaps the start
    (('2026-10-31T12:00:00+00:00', '2026-10-31T14:00:00+00:00'), True),      # overlaps the end
    (('2026-10-31T11:00:00+00:00', '2026-10-31T12:00:00+00:00'), True),      # inside it
    (('2026-10-31T08:00:00+00:00', '2026-10-31T15:00:00+00:00'), True),      # around it
    (('2026-10-31T07:00:00+00:00', '2026-10-31T10:00:00+00:00'), False),     # ends as it starts
    (('2026-10-31T13:00:00+00:00', '2026-10-31T16:00:00+00:00'), False),     # starts as it ends
    (('2026-11-01T10:00:00+00:00', '2026-11-01T13:00:00+00:00'), False),     # next day
])
def test_periods_overlap_when_they_share_any_moment(other, expected):
    assert overlaps(*EVENING, *other) is expected
    # Overlap does not depend on which of the two is asked about first.
    assert overlaps(*other, *EVENING) is expected


def test_offsets_are_compared_as_moments_not_as_text():
    # 18:00 in Singapore is 10:00 UTC: the same moment, written differently.
    assert overlaps('2026-10-31T18:00:00+08:00', '2026-10-31T19:00:00+08:00', *EVENING)


def test_an_incomplete_period_never_reports_a_conflict():
    assert not overlaps(None, EVENING[1], *EVENING)
    assert not overlaps('not a date', EVENING[1], *EVENING)


# --- "considers a venue unavailable during the period of a confirmed booking" --

def test_an_approved_booking_makes_the_venue_unavailable():
    marked = attach_conflicts([{'venue_id': HALL, 'eligible': True}],
                              [booking(*EVENING)], *EVENING)
    assert marked[0]['eligible'] is False
    assert marked[0]['conflicts'][0]['starts_at'] == EVENING[0]


def test_a_pending_request_does_not():
    # Several coordinators may ask for the same slot; only approval takes it.
    marked = attach_conflicts([{'venue_id': HALL, 'eligible': True}],
                              [booking(*EVENING, status='submitted')], *EVENING)
    assert marked[0]['eligible'] is True
    assert marked[0]['conflicts'] == []


def test_a_booking_at_another_venue_does_not():
    marked = attach_conflicts([{'venue_id': HALL, 'eligible': True}],
                              [booking(*EVENING, venue_id=ROOM)], *EVENING)
    assert marked[0]['eligible'] is True


def test_a_venue_that_already_fails_a_requirement_stays_ineligible():
    marked = attach_conflicts([{'venue_id': HALL, 'eligible': False}], [], *EVENING)
    assert marked[0]['eligible'] is False


def test_marking_does_not_change_the_venue_it_was_given():
    original = {'venue_id': HALL, 'eligible': True}
    attach_conflicts([original], [booking(*EVENING)], *EVENING)
    assert 'conflicts' not in original


# --- Search results ("clearly displays the conflicting booking") -------------

def hall(**overrides):
    return {'venue_id': HALL, 'venue_name': 'Training Hall', 'capacity': 100,
            'facilities': [], 'supported_room_layouts': [], 'wheelchair_accessible': True,
            'blind_accessible': True, 'operating_hours': {
                day: {'open': '08:00', 'close': '22:00'} for day in
                ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')},
            **overrides}


@patch('app.services.venue_availability.supabase_request')
@patch('app.routes.venues.load_event', return_value=EVENT)
@patch('app.routes.venues.search_venues')
@patch('app.routes.venues.authenticated_token', return_value='coordinator-token')
def test_a_booked_venue_is_listed_but_cannot_be_requested(token, search, event, query):
    search.return_value = [hall(), hall(venue_id=ROOM, venue_name='Small Room')]
    query.return_value = [booking(*EVENING, event_name='Gala', visible=True)]
    response = create_app().test_client().get('/api/venues/search?event_id=6')

    hall_result, room_result = response.json['venues']
    assert hall_result['eligible'] is False
    assert hall_result['conflicts'][0]['event_name'] == 'Gala'
    assert room_result['eligible'] is True
    assert room_result['conflicts'] == []
    assert response.json['eligible_count'] == 1
    # One lookup for the whole page, for exactly the event's period.
    query.assert_called_once()
    assert query.call_args.args[0] == '/rest/v1/rpc/venue_unavailability'
    assert query.call_args.kwargs['payload'] == {'p_starts': EVENING[0], 'p_ends': EVENING[1]}
    assert query.call_args.kwargs['token'] == 'coordinator-token'


@patch('app.services.venue_availability.supabase_request')
@patch('app.routes.venues.load_event', return_value={**EVENT, 'end_datetime': None})
@patch('app.routes.venues.search_venues', return_value=[{'venue_id': HALL}])
@patch('app.routes.venues.authenticated_token', return_value='coordinator-token')
def test_an_event_without_a_period_is_not_checked(token, search, event, query):
    response = create_app().test_client().get('/api/venues/search?event_id=6')
    assert response.json['venues'][0]['conflicts'] == []
    query.assert_not_called()


@patch('app.services.venue_availability.supabase_request')
@patch('app.routes.venues.load_event', return_value=EVENT)
@patch('app.routes.venues.supabase_request')
@patch('app.routes.venues.authenticated_token', return_value='coordinator-token')
def test_the_venue_about_to_be_requested_carries_its_conflicts(token, detail, event, availability):
    detail.return_value = [hall()]
    availability.return_value = [booking(*EVENING, visible=False)]
    response = create_app().test_client().get(f'/api/venues/{HALL}?event_id=6')
    assert response.json['venue']['eligible'] is False
    assert response.json['venue']['conflicts'][0]['visible'] is False


# --- "prevents requesting/approving a booking that conflicts" ---------------

CONFLICT = {
    'error': "This venue is already booked for part of this event's time.",
    'conflicts': [booking(*EVENING, visible=False)],
    'status': 409,
}

REQUEST = dict(venue_id=HALL, event_id=6, event_name='Halloween',
               starts_at='2099-10-31T10:00:00+00:00', ends_at='2099-10-31T13:00:00+00:00',
               attendance=40, venue_requirements='None')


@patch('app.routes.venue_bookings.supabase_request')
def test_a_conflicting_request_is_refused_with_the_conflict(query):
    query.side_effect = [USER, CONFLICT]
    response = create_app().test_client().post('/api/venue-bookings', json=REQUEST, headers=HEADERS)
    assert response.status_code == 409
    assert response.json['conflicts'] == CONFLICT['conflicts']
    assert 'booking' not in response.json


@patch('app.routes.venue_bookings.supabase_request')
def test_a_conflicting_approval_is_refused_with_the_conflict(query):
    query.side_effect = [USER, {**CONFLICT, 'error': 'This venue is already booked for an overlapping period, so this request can only be rejected.'}]
    response = create_app().test_client().post(f'/api/venue-bookings/{HALL}/review',
                                               json={'outcome': 'approved'}, headers=HEADERS)
    assert response.status_code == 409
    assert response.json['conflicts'] == CONFLICT['conflicts']
