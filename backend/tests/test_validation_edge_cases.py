"""Malformed values and boundary conditions not covered by happy-path stories."""
from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from app.schemas import event, event_request, venue_booking, venue_search
from app.services import event_venue_criteria as criteria, venue_search_service


@pytest.mark.parametrize('payload,field', [
    ({'event_name': 12}, 'event_name'), ({'room_layout': []}, 'room_layout'),
    ({'capacity_needed': True}, 'capacity_needed'),
    ({'start_datetime': 12}, 'start_datetime'),
    ({'required_facilities': ['']}, 'required_facilities'),
    ({'equipment_requirements': ['projector']}, 'equipment_requirements'),
    ({'equipment_requirements': [{'equipment_type': 'projector', 'quantity': 1, 'notes': 12}]}, 'equipment_requirements'),
])
def test_request_rejects_malformed_field_values(payload, field):
    _, errors = event_request.parse_payload(payload)
    assert field in errors


def test_request_dates_accept_datetime_and_blank_values():
    moment = datetime(2099, 1, 1, tzinfo=timezone.utc)
    record, errors = event_request.parse_payload({'start_datetime': moment, 'end_datetime': '   '})
    assert not errors
    assert record['start_datetime'] == moment.isoformat()
    assert record['end_datetime'] is None


@pytest.mark.parametrize('status,word', [('completed', 'over'), ('cancelled', 'cancelled'), (None, 'unknown'), ('submitted', 'submitted')])
def test_event_readonly_explanation(status, word):
    assert word in event.why_not_editable({'status': status})


@pytest.mark.parametrize('payload,field', [
    ({'capacity': 'abc'}, 'capacity'), ({'capacity': []}, 'capacity'),
    ({'location': 1}, 'location'), ({'location': 'a' * 101}, 'location'),
    ({'layouts': 'theatre'}, 'layouts'), ({'facilities': [1]}, 'facilities'),
    ({'layouts': ['unknown']}, 'layouts'), ({'blind_accessible': 'false'}, 'blind_accessible'),
    ({'start_date': '01-01-2099'}, 'end_date'), ({'end_date': '01-01-2099'}, 'start_date'),
    ({'start_date': 'bad', 'end_date': '01-01-2099'}, 'start_date'),
    ({'start_date': 42, 'end_date': '01-01-2099'}, 'start_date'),
])
def test_venue_filters_report_errors_per_field(payload, field):
    _, errors = venue_search.parse_filters(payload)
    assert field in errors


def test_empty_date_and_invalid_booking_body():
    errors = {}
    assert venue_search._date('', 'start_date', errors) is None
    assert not errors
    assert 'body' in venue_booking.parse_booking(None)[1]


def test_blind_accessibility_is_preserved_in_search_and_requirement_gate():
    requirements = criteria.criteria_from_event({'need_blind_accessibility': True})
    assert criteria.search_filters(requirements)['blind_accessible'] == 'true'
    assert any(item['field'] == 'need_blind_accessibility' for item in criteria.describe(requirements))
    unmet = criteria.unmet_requirements({'blind_accessible': False}, requirements)
    assert [item['field'] for item in unmet] == ['need_blind_accessibility']


@pytest.mark.parametrize('value', [date(2099, 1, 1), datetime(2099, 1, 1), datetime(2099, 1, 1, tzinfo=timezone.utc)])
def test_event_dates_accept_native_date_and_datetime(value):
    assert criteria.local_date(value) == date(2099, 1, 1)


def test_venue_search_removes_venues_closed_on_requested_dates(monkeypatch):
    rows = [{'venue_id': 'open'}, {'venue_id': 'closed'}]
    query = Mock(return_value=rows)
    monkeypatch.setattr(venue_search_service, 'supabase_request', query)
    monkeypatch.setattr(venue_search_service, 'matches_operating_hours', lambda venue, filters: venue['venue_id'] == 'open')
    filters, errors = venue_search.parse_filters({})
    assert not errors
    assert venue_search_service.search_venues(filters, 'token') == rows[:1]
    assert query.call_args.kwargs['token'] == 'token'
