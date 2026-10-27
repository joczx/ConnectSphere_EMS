"""Unit tests for the Create and Submit Event Request user story.

Traces to the "Create and Submit Event Request" user story. Each test names
the acceptance criterion it covers so the mapping stays visible in the sprint
evidence. Schema functions, services and route handlers are tested separately.
Dependencies are mocked; no HTTP client or real Supabase calls are used.
UI rendering and database uniqueness require separate acceptance checks.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.schemas import event_request as schema
from app.services import event_request_service as service
from app.routes import event_requests as routes
from unittest.mock import Mock, patch
from flask import Flask

FUTURE = datetime.now(timezone.utc) + timedelta(days=30)

# Users are managed by Supabase Auth, so ids are UUIDs.
ORGANISER = "8c2d7e15-4b93-4a06-8f21-6e0b3d9a7c54"


def valid_payload(**overrides):
    payload = {
        "event_name": "Orientation Night",
        "purpose": "Welcome incoming students",
        "description": "An evening of introductions and campus tours.",
        "event_organiser_id": ORGANISER,
        "start_datetime": FUTURE.isoformat(),
        "end_datetime": (FUTURE + timedelta(hours=3)).isoformat(),
        "capacity_needed": 120,
        "room_layout": "theatre",
        "required_facilities": ["projector", "sound_system"],
        "need_wheelchair_accessibility": True,
        "need_blind_accessibility": False,
        "equipment_requirements": [
            {"equipment_type": "projector", "quantity": 2, "notes": "HDMI input"},
            {"equipment_type": "microphone", "quantity": 4},
        ],
        "registration_needs": "Open registration two weeks before, cap at 120.",
    }
    payload.update(overrides)
    return payload


def test_a_blank_mandatory_field_counts_as_missing():
    record, _ = schema.parse_payload(valid_payload(event_name="   "))

    assert "event_name" in schema.find_missing(record)


# Users are managed by Supabase Auth, so user_id is a UUID, not a number.
def test_an_organiser_id_must_be_a_uuid():
    _, errors = schema.parse_payload(valid_payload(event_organiser_id=1))

    assert "event_organiser_id" in errors
    assert "UUID" in errors["event_organiser_id"]


def test_an_organiser_id_that_is_not_a_valid_uuid_is_rejected():
    _, errors = schema.parse_payload(valid_payload(event_organiser_id="not-a-uuid"))

    assert "event_organiser_id" in errors


def test_an_organiser_id_is_normalised_to_canonical_form():
    """Upper case and braces are accepted spellings of the same UUID."""
    record, errors = schema.parse_payload(
        valid_payload(event_organiser_id=ORGANISER.upper())
    )

    assert errors == {}
    assert record["event_organiser_id"] == ORGANISER


# AC: The system prevents the user from submitting invalid event details.
def test_an_event_cannot_end_at_the_moment_it_starts():
    _, errors = schema.parse_payload(valid_payload(end_datetime=FUTURE.isoformat()))

    assert "end_datetime" in errors


def test_an_event_cannot_start_in_the_past():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    _, errors = schema.parse_payload(
        valid_payload(
            start_datetime=past.isoformat(),
            end_datetime=(past + timedelta(hours=2)).isoformat(),
        )
    )

    assert "start_datetime" in errors


def test_expected_attendance_must_be_a_number():
    _, errors = schema.parse_payload(valid_payload(capacity_needed="a lot"))

    assert "capacity_needed" in errors


def test_new_venue_search_room_layout_is_accepted():
    record, errors = schema.parse_payload(valid_payload(room_layout="exhibition"))

    assert errors == {}
    assert record["room_layout"] == "exhibition"


def test_a_timestamp_without_a_timezone_is_rejected():
    _, errors = schema.parse_payload(valid_payload(start_datetime="2027-01-01T09:00:00"))

    assert "start_datetime" in errors
    assert "timezone" in errors["start_datetime"]


def test_a_client_cannot_set_the_status_itself():
    """Status is system-controlled, so it is not a writable field."""
    _, errors = schema.parse_payload(valid_payload(status="planning"))

    assert "_body" in errors
    assert "status" in errors["_body"]


def test_a_non_object_body_is_rejected():
    _, errors = schema.parse_payload(["not", "an", "object"])

    assert "_body" in errors


def test_no_equipment_is_valid():
    """"Where relevant" means an event may need no equipment at all."""
    record, errors = schema.parse_payload(valid_payload(equipment_requirements=[]))

    assert errors == {}
    assert record["equipment_requirements"] == []


def test_equipment_requirements_must_be_a_list_of_items():
    _, errors = schema.parse_payload(
        valid_payload(equipment_requirements="projector, 2, HDMI input")
    )

    assert errors["equipment_requirements"] == "Equipment requirements must be a list."


def test_each_equipment_item_must_be_an_object():
    _, errors = schema.parse_payload(
        valid_payload(equipment_requirements=["projector, 2, HDMI input"])
    )

    assert errors["equipment_requirements"] == "Item 1: expected an equipment object."


def test_equipment_notes_must_be_text():
    _, errors = schema.parse_payload(
        valid_payload(
            equipment_requirements=[
                {"equipment_type": "projector", "quantity": 2, "notes": 12}
            ]
        )
    )

    assert errors["equipment_requirements"] == "Item 1: notes must be text."


@pytest.mark.parametrize("field", ["required_facilities", "equipment_requirements"])
def test_a_cleared_list_is_unanswered_and_blocks_submission(field):
    record, errors = schema.parse_payload(valid_payload(**{field: None}))

    assert errors == {}
    assert record[field] is None
    assert field in schema.find_missing(record)


def test_each_equipment_item_needs_a_type():
    _, errors = schema.parse_payload(
        valid_payload(equipment_requirements=[{"quantity": 2}])
    )

    assert "equipment type is required" in errors["equipment_requirements"]


def test_equipment_quantity_must_be_at_least_one():
    _, errors = schema.parse_payload(
        valid_payload(
            equipment_requirements=[{"equipment_type": "projector", "quantity": 0}]
        )
    )

    assert "at least 1" in errors["equipment_requirements"]


def test_equipment_quantity_must_be_a_number():
    _, errors = schema.parse_payload(
        valid_payload(
            equipment_requirements=[{"equipment_type": "projector", "quantity": "two"}]
        )
    )

    assert "whole number" in errors["equipment_requirements"]


def test_blank_registration_needs_are_stored_as_none():
    """No registration needed is recorded as null rather than an empty string."""
    record, errors = schema.parse_payload(valid_payload(registration_needs="   "))

    assert errors == {}
    assert record["registration_needs"] is None


# AC 2, 6, 7, 8: submission, database-generated ID, timestamp and status.
def test_service_submits_complete_request_and_returns_generated_id():
    record, errors = schema.parse_payload(valid_payload())
    assert not errors
    stored = {**record, 'event_request_id': 42, 'status': 'submitted',
              'submitted_at': '2026-10-04T01:00:00+00:00'}
    table = Mock()
    table.insert.return_value.execute.return_value.data = [stored]
    # Execute the insertion callback against a fake table; mock the DB wrapper.
    with patch.object(service, '_execute', side_effect=lambda operation, **kwargs: operation(table).data), \
         patch.object(service, '_now', return_value=stored['submitted_at']):
        result = service.create_event_request(valid_payload())
    assert result == stored
    inserted = table.insert.call_args.args[0]
    assert inserted['status'] == 'submitted'
    assert inserted['submitted_at'] == stored['submitted_at']
    assert 'event_request_id' not in inserted
    # This checks ID delegation/return, not the live database uniqueness constraint.


# AC 3, 4: missing mandatory information is reported before a database write.
@pytest.mark.parametrize('field', (*schema.MANDATORY_FOR_SUBMISSION, 'event_organiser_id'))
def test_service_blocks_each_missing_field(field):
    payload = valid_payload()
    del payload[field]
    with patch.object(service, '_execute') as write, \
         pytest.raises(service.EventRequestError) as caught:
        service.create_event_request(payload)
    assert caught.value.status_code == 400
    assert 'required' in caught.value.errors[field]
    write.assert_not_called()


# AC 5: malformed event details cannot reach persistence.
@pytest.mark.parametrize('changes,field', [
    ({'capacity_needed': 0}, 'capacity_needed'),
    ({'capacity_needed': 1.5}, 'capacity_needed'),
    ({'start_datetime': 'invalid'}, 'start_datetime'),
    ({'end_datetime': '2000-01-01T00:00:00Z'}, 'end_datetime'),
    ({'room_layout': 'invalid'}, 'room_layout'),
    ({'required_facilities': ['invalid']}, 'required_facilities'),
    ({'equipment_requirements': [{'equipment_type': 'mic', 'quantity': 0}]}, 'equipment_requirements'),
    ({'event_name': '   '}, 'event_name'),
    ({'status': 'planning'}, '_body'),
    ({'event_request_id': 123}, '_body'),
    ({'submitted_at': '2000-01-01T00:00:00Z'}, '_body'),
])
def test_service_blocks_invalid_details(changes, field):
    with patch.object(service, '_execute') as write, \
         pytest.raises(service.EventRequestError) as caught:
        service.create_event_request(valid_payload(**changes))
    assert field in caught.value.errors
    write.assert_not_called()


# AC 9: stored details can be retrieved for review (UI summary tested separately).
def test_service_returns_saved_details_for_review():
    stored = {**valid_payload(), 'event_request_id': 42, 'status': 'draft'}
    table = Mock()
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [stored]
    with patch.object(service, '_execute', side_effect=lambda operation, **kwargs: operation(table).data):
        result = service.get_event_request(42)
    assert result == stored
    table.select.assert_called_once_with(
        '*,event_organiser:users!event_organiser_id(name),'
        'event_coordinator:users!event_coordinator_id(name)'
    )
    table.select.return_value.eq.assert_called_once_with('event_request_id', 42)


# AC 10: isolate the route handler by replacing its service dependency.
def test_create_handler_returns_success_confirmation():
    stored = {'event_request_id': 42, 'status': 'submitted'}
    app = Flask(__name__)
    with app.test_request_context(json=valid_payload()), \
         patch.object(routes, 'create_event_request', return_value=stored) as create:
        response, status = routes.create()
    assert status == 201
    assert response.get_json() == {
        'message': 'Event request submitted successfully.', 'event_request': stored,
    }
    create.assert_called_once_with(valid_payload(), submit=True)


# AC 11: failed persistence must never yield a success result.
def test_service_rejects_empty_database_result():
    with patch.object(service, '_execute', return_value=[]), \
         pytest.raises(service.EventRequestError) as caught:
        service.create_event_request(valid_payload())
    assert caught.value.status_code == 502
    assert 'could not be created' in caught.value.message


def test_service_translates_database_outage_to_readable_error():
    error = service._translate(RuntimeError('offline'), 'create the event request')
    assert error.status_code == 502
    assert 'database is unavailable' in error.message
    assert 'Please try again' in error.message


def test_error_handler_returns_error_without_success_confirmation():
    error = service.EventRequestError('Missing information.', errors={'event_name': 'Event name is required.'})
    with Flask(__name__).app_context():
        response, status = routes.handle_event_request_error(error)
    assert status == 400
    assert response.get_json() == {'error': 'Missing information.', 'errors': error.errors}
    assert 'message' not in response.get_json()


@pytest.mark.parametrize('body', [[], {'save_as_draft': 'false'}])
def test_create_handler_rejects_malformed_body(body):
    with Flask(__name__).test_request_context(json=body), \
         patch.object(routes, 'create_event_request') as create, \
         pytest.raises(service.EventRequestError) as caught:
        routes.create()
    assert caught.value.status_code == 400
    assert caught.value.message
    create.assert_not_called()


