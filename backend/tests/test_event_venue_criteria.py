"""Unit tests for searching venues against the event being planned.

Covers the rework of the venue booking flow: a coordinator opens Venue Search
from an event in planning, the event's own requirements become the search
conditions, and a venue that cannot meet them is not offered for a booking
request even once the filters have been cleared.

No database is needed. Supabase calls are patched at the route boundary.
"""

from datetime import date
from unittest.mock import patch

import pytest

from app import create_app
from app.services.event_service import EventError
from app.services.event_venue_criteria import (
    annotate,
    closed_days,
    criteria_from_event,
    describe,
    local_date,
    meets,
    search_filters,
    unmet_requirements,
)

HEADERS = {'Authorization': 'Bearer coordinator-token'}


@pytest.fixture(autouse=True)
def nothing_booked():
    # These tests are about requirements. Availability is covered by
    # test_venue_booking_conflicts.py, so no venue here is booked.
    with patch('app.services.venue_availability.approved_bookings', return_value=[]):
        yield

OPEN_ALL_WEEK = {
    day: {'open': '08:00', 'close': '22:00'}
    for day in ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
}

# A Thursday in Singapore time, so the operating-hours checks have a known day.
EVENT = {
    'event_id': 4,
    'event_name': 'Orientation',
    'status': 'planning',
    'capacity_needed': 350,
    'room_layout': 'theatre',
    'required_facilities': ['projector', 'wifi'],
    'need_wheelchair_accessibility': True,
    'need_blind_accessibility': False,
    'start_datetime': '2026-11-05T01:00:00+00:00',
    'end_datetime': '2026-11-05T09:00:00+00:00',
}

VENUE = {
    'venue_id': 'b21bdd3b-5fbb-4588-b070-f9a7e923ef02',
    'venue_name': 'Auditorium',
    'capacity': 500,
    'facilities': ['projector', 'wifi', 'stage'],
    'supported_room_layouts': ['theatre', 'banquet'],
    'wheelchair_accessible': True,
    'blind_accessible': False,
    'operating_hours': OPEN_ALL_WEEK,
}


def criteria(**overrides):
    return criteria_from_event({**EVENT, **overrides})


def venue(**overrides):
    return {**VENUE, **overrides}


# --- What the event requires -------------------------------------------------

def test_criteria_are_taken_from_the_event_being_planned():
    found = criteria()
    assert found['capacity'] == 350
    assert found['layout'] == 'theatre'
    assert found['facilities'] == ['projector', 'wifi']
    assert found['wheelchair_accessible'] is True
    # Not needed is not a requirement; a venue that happens to have it is fine.
    assert found['blind_accessible'] is None


def test_dates_are_the_singapore_days_the_event_runs_on():
    # 01:00 UTC is 09:00 the same day in Singapore; 17:00 UTC is the next day.
    assert local_date('2026-11-05T01:00:00+00:00') == date(2026, 11, 5)
    assert local_date('2026-11-05T17:00:00+00:00') == date(2026, 11, 6)
    assert local_date(None) is None
    assert local_date('not a date') is None


def test_an_unanswered_requirement_does_not_constrain_the_search():
    found = criteria(capacity_needed=None, room_layout=None, required_facilities=None)
    assert found['capacity'] is None
    assert found['layout'] is None
    assert found['facilities'] == []
    assert search_filters(found) == {
        'wheelchair_accessible': 'true',
        'start_date': '05-11-2026',
        'end_date': '05-11-2026',
    }


def test_requirements_become_venue_search_filters():
    assert search_filters(criteria()) == {
        'capacity': '350',
        'layouts': ['theatre'],
        'facilities': ['projector', 'wifi'],
        'wheelchair_accessible': 'true',
        'start_date': '05-11-2026',
        'end_date': '05-11-2026',
    }


def test_a_facility_the_catalogue_cannot_record_is_not_sent_as_a_filter():
    # The search refuses an unknown facility, which would turn "no venue has a
    # whiteboard" into an error instead of an empty, explained result.
    found = criteria(required_facilities=['projector', 'whiteboard'])
    assert search_filters(found)['facilities'] == ['projector']


def test_but_every_venue_is_still_marked_as_missing_it():
    found = criteria(required_facilities=['projector', 'whiteboard'])
    unmet = unmet_requirements(venue(), found)
    assert unmet[0]['detail'] == 'Missing whiteboard.'


def test_half_a_date_range_is_never_sent_because_the_search_refuses_it():
    assert 'start_date' not in search_filters(criteria(end_datetime=None))


def test_requirements_are_described_with_the_event_field_labels():
    described = {item['label']: item['value'] for item in describe(criteria())}
    assert described['Expected attendance'] == 'At least 350'
    assert described['Room layout'] == 'Theatre'
    assert described['Venue requirements'] == 'Projector, Wifi'
    assert described['Wheelchair accessibility'] == 'Required'
    assert 'Accessibility for blind attendees' not in described


# --- Whether a venue meets them ---------------------------------------------

def test_a_venue_meeting_every_requirement_may_be_requested():
    assert meets(venue(), criteria()) is True
    assert unmet_requirements(venue(), criteria()) == []


@pytest.mark.parametrize('changes,field,detail', [
    ({'capacity': 80}, 'capacity_needed', 'Holds 80, but 350 are expected.'),
    ({'capacity': None}, 'capacity_needed', 'This venue does not record a capacity.'),
    ({'supported_room_layouts': ['banquet']}, 'room_layout',
     'Does not support a theatre layout.'),
    ({'facilities': ['projector']}, 'required_facilities', 'Missing wifi.'),
    ({'wheelchair_accessible': False}, 'need_wheelchair_accessibility',
     'This venue is not wheelchair accessible.'),
])
def test_each_unmet_requirement_is_named_and_explained(changes, field, detail):
    unmet = unmet_requirements(venue(**changes), criteria())
    assert [item['field'] for item in unmet] == [field]
    assert unmet[0]['detail'] == detail


def test_exactly_enough_capacity_is_enough():
    assert meets(venue(capacity=350), criteria()) is True


def test_every_shortfall_is_reported_rather_than_just_the_first():
    unmet = unmet_requirements(
        venue(capacity=10, facilities=[], wheelchair_accessible=False), criteria()
    )
    assert len(unmet) == 3


def test_a_venue_closed_on_the_event_day_cannot_be_used():
    hours = {**OPEN_ALL_WEEK, 'thursday': {'closed': True}}
    unmet = unmet_requirements(venue(operating_hours=hours), criteria())
    assert unmet[0]['detail'] == 'Closed on Thursday.'


def test_being_closed_on_another_day_does_not_matter():
    hours = {**OPEN_ALL_WEEK, 'sunday': {'closed': True}}
    assert meets(venue(operating_hours=hours), criteria()) is True


def test_a_venue_with_no_recorded_hours_is_treated_as_closed():
    assert not meets(venue(operating_hours=None), criteria())


def test_hours_are_not_checked_when_the_event_has_no_period():
    assert closed_days(venue(operating_hours=None), None, None) == []


def test_a_period_longer_than_a_week_reports_each_day_once():
    days = closed_days(venue(operating_hours={}), date(2026, 11, 1), date(2026, 11, 30))
    assert len(days) == 7
    assert len(set(days)) == 7


def test_annotating_does_not_change_the_venue_it_was_given():
    original = venue(capacity=10)
    assessed = annotate([original], criteria())
    assert assessed[0]['eligible'] is False
    assert assessed[0]['unmet_requirements']
    assert 'eligible' not in original


# --- The event-aware endpoints ----------------------------------------------

@patch('app.routes.events.load_event', return_value=EVENT)
@patch('app.routes.events.supabase_request', return_value={'id': 'coordinator'})
def test_venue_criteria_endpoint_returns_filters_and_wording(query, event):
    response = create_app().test_client().get('/api/events/4/venue-criteria', headers=HEADERS)
    assert response.status_code == 200
    assert response.json['filters']['capacity'] == '350'
    assert response.json['filters']['layouts'] == ['theatre']
    assert response.json['event']['event_name'] == 'Orientation'
    assert response.json['planning'] is True
    assert response.json['planning_note'] is None
    assert event.call_args.args[:2] == ('4', 'coordinator-token')


@patch('app.routes.events.load_event', return_value={**EVENT, 'status': 'confirmed'})
@patch('app.routes.events.supabase_request', return_value={'id': 'coordinator'})
def test_venue_criteria_endpoint_explains_an_event_past_planning(query, event):
    response = create_app().test_client().get('/api/events/4/venue-criteria', headers=HEADERS)
    assert response.status_code == 200
    assert response.json['planning'] is False
    assert 'confirmed' in response.json['planning_note']


@patch('app.routes.events.supabase_request')
def test_venue_criteria_endpoint_requires_authentication(query):
    assert create_app().test_client().get('/api/events/4/venue-criteria').status_code == 401
    query.assert_not_called()


@patch('app.routes.events.load_event',
       side_effect=EventError('Event not found or access unavailable.', status=404))
@patch('app.routes.events.supabase_request', return_value={'id': 'coordinator'})
def test_venue_criteria_endpoint_hides_an_event_the_caller_cannot_read(query, event):
    # Row level security returns no rows rather than a denial, and an event the
    # coordinator is not assigned to must not be searchable.
    response = create_app().test_client().get('/api/events/9/venue-criteria', headers=HEADERS)
    assert response.status_code == 404


@patch('app.routes.events.supabase_request')
def test_venue_criteria_endpoint_rejects_a_malformed_event_id(query):
    query.return_value = {'id': 'coordinator'}
    response = create_app().test_client().get('/api/events/4;drop/venue-criteria', headers=HEADERS)
    assert response.status_code == 404


@patch('app.routes.venues.load_event')
@patch('app.routes.venues.search_venues')
@patch('app.routes.venues.authenticated_token', return_value='coordinator-token')
def test_search_marks_each_venue_against_the_event(token, search, event):
    search.return_value = [venue(), venue(venue_id='second', capacity=10)]
    event.return_value = EVENT
    response = create_app().test_client().get('/api/venues/search?event_id=4')
    assert response.status_code == 200
    assert [item['eligible'] for item in response.json['venues']] == [True, False]
    assert response.json['eligible_count'] == 1
    assert response.json['event']['event_id'] == 4
    assert response.json['venues'][1]['unmet_requirements'][0]['label'] == 'Expected attendance'


@patch('app.routes.venues.load_event')
@patch('app.routes.venues.search_venues')
@patch('app.routes.venues.authenticated_token', return_value='coordinator-token')
def test_an_event_does_not_narrow_the_results_so_filters_can_be_cleared(token, search, event):
    # The coordinator may read the whole catalogue while planning an event. The
    # filters decide what is listed; the event only decides what is selectable.
    search.return_value = [venue(capacity=10)]
    event.return_value = EVENT
    response = create_app().test_client().get('/api/venues/search?event_id=4')
    assert response.json['count'] == 1
    assert response.json['venues'][0]['eligible'] is False
    assert search.call_args.args[0]['capacity'] is None


@patch('app.routes.venues.search_venues')
@patch('app.routes.venues.authenticated_token', return_value='coordinator-token')
def test_search_without_an_event_is_unchanged(token, search):
    search.return_value = [venue()]
    response = create_app().test_client().get('/api/venues/search')
    assert response.json['count'] == 1
    assert 'eligible' not in response.json['venues'][0]
    assert 'event' not in response.json


@patch('app.routes.venues.search_venues')
@patch('app.routes.venues.authenticated_token', return_value='coordinator-token')
def test_search_rejects_a_malformed_event_id(token, search):
    search.return_value = []
    response = create_app().test_client().get('/api/venues/search?event_id=4%20or%201=1')
    assert response.status_code == 404


@patch('app.routes.venues.load_event')
@patch('app.routes.venues.supabase_request')
@patch('app.routes.venues.authenticated_token', return_value='coordinator-token')
def test_one_venue_carries_the_verdict_for_the_event_it_is_viewed_for(token, query, event):
    query.return_value = [venue(capacity=10)]
    event.return_value = EVENT
    response = create_app().test_client().get(
        '/api/venues/b21bdd3b-5fbb-4588-b070-f9a7e923ef02?event_id=4'
    )
    assert response.status_code == 200
    assert response.json['venue']['eligible'] is False
    assert response.json['requirements'][0]['value'] == 'At least 350'
