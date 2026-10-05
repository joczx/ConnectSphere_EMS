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


# AC: The user can enter the required details for an event request.
def test_a_complete_payload_is_accepted():
    record, errors = schema.parse_payload(valid_payload())

    assert errors == {}
    assert record["event_name"] == "Orientation Night"
    assert record["capacity_needed"] == 120
    assert record["required_facilities"] == ["projector", "sound_system"]


# AC: The system validates that all mandatory fields are completed before submission.
# AC: The system displays an error message when required information is missing.
@pytest.mark.parametrize("field", schema.MANDATORY_FOR_SUBMISSION)
def test_each_mandatory_field_is_reported_when_missing(field):
    payload = valid_payload()
    del payload[field]

    record, _ = schema.parse_payload(payload)
    missing = schema.find_missing(record)

    assert field in missing
    assert "required" in missing[field]


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


def test_the_organiser_is_required_before_submitting():
    payload = valid_payload()
    del payload["event_organiser_id"]

    record, _ = schema.parse_payload(payload)

    assert "event_organiser_id" in schema.find_missing(record)


# AC: The system prevents the user from submitting invalid event details.
def test_an_event_cannot_end_before_it_starts():
    _, errors = schema.parse_payload(
        valid_payload(end_datetime=(FUTURE - timedelta(hours=1)).isoformat())
    )

    assert "end_datetime" in errors


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


def test_expected_attendance_must_be_positive():
    _, errors = schema.parse_payload(valid_payload(capacity_needed=0))

    assert "capacity_needed" in errors


def test_expected_attendance_must_be_a_number():
    _, errors = schema.parse_payload(valid_payload(capacity_needed="a lot"))

    assert "capacity_needed" in errors


def test_room_layout_must_be_one_the_database_recognises():
    _, errors = schema.parse_payload(valid_payload(room_layout="amphitheatre"))

    assert "room_layout" in errors
    assert "theatre" in errors["room_layout"]


@pytest.mark.parametrize("room_layout", ["exhibition", "cabaret"])
def test_new_venue_search_room_layouts_are_accepted(room_layout):
    record, errors = schema.parse_payload(valid_payload(room_layout=room_layout))

    assert errors == {}
    assert record["room_layout"] == room_layout


def test_a_timestamp_without_a_timezone_is_rejected():
    _, errors = schema.parse_payload(valid_payload(start_datetime="2027-01-01T09:00:00"))

    assert "start_datetime" in errors
    assert "timezone" in errors["start_datetime"]


def test_a_malformed_timestamp_is_rejected():
    _, errors = schema.parse_payload(valid_payload(start_datetime="next Tuesday"))

    assert "start_datetime" in errors


def test_facilities_must_be_a_list():
    _, errors = schema.parse_payload(valid_payload(required_facilities="projector"))

    assert "required_facilities" in errors


def test_facilities_must_not_repeat():
    _, errors = schema.parse_payload(
        valid_payload(required_facilities=["projector", "projector"])
    )

    assert "required_facilities" in errors


def test_new_venue_search_facilities_are_accepted():
    facilities = ["parking", "catering_area", "air_conditioning"]

    record, errors = schema.parse_payload(
        valid_payload(required_facilities=facilities)
    )

    assert errors == {}
    assert record["required_facilities"] == facilities


def test_accessibility_flags_must_be_true_or_false():
    _, errors = schema.parse_payload(valid_payload(need_blind_accessibility="yes"))

    assert "need_blind_accessibility" in errors


def test_a_client_cannot_set_the_status_itself():
    """Status is system-controlled, so it is not a writable field."""
    _, errors = schema.parse_payload(valid_payload(status="approved"))

    assert "_body" in errors
    assert "status" in errors["_body"]


def test_a_non_object_body_is_rejected():
    _, errors = schema.parse_payload(["not", "an", "object"])

    assert "_body" in errors


# AC: The system prevents invalid event details.
# Timestamps read back from Supabase arrive as ISO strings, so the timing
# rules must work on a stored row too.
def test_timing_rules_work_on_a_row_read_back_from_the_database():
    stored = {
        "start_datetime": FUTURE.isoformat(),
        "end_datetime": (FUTURE - timedelta(hours=1)).isoformat(),
    }

    assert "end_datetime" in schema.check_timing(stored)


# AC: an event request carries equipment requirements where relevant.
def test_equipment_requirements_are_normalised():
    record, errors = schema.parse_payload(valid_payload())

    assert errors == {}
    assert record["equipment_requirements"] == [
        {"equipment_type": "projector", "quantity": 2, "notes": "HDMI input"},
        {"equipment_type": "microphone", "quantity": 4, "notes": None},
    ]


def test_no_equipment_is_valid():
    """"Where relevant" means an event may need no equipment at all."""
    record, errors = schema.parse_payload(valid_payload(equipment_requirements=[]))

    assert errors == {}
    assert record["equipment_requirements"] == []


# Every field must be answered before submission, but "none" is an answer.
@pytest.mark.parametrize("field", ["required_facilities", "equipment_requirements"])
def test_answering_none_satisfies_a_mandatory_list(field):
    record, _ = schema.parse_payload(valid_payload(**{field: []}))

    assert field not in schema.find_missing(record)


@pytest.mark.parametrize("field", ["required_facilities", "equipment_requirements"])
def test_a_cleared_list_is_unanswered_and_blocks_submission(field):
    record, errors = schema.parse_payload(valid_payload(**{field: None}))

    assert errors == {}
    assert record[field] is None
    assert field in schema.find_missing(record)


def test_equipment_must_be_a_list():
    _, errors = schema.parse_payload(
        valid_payload(equipment_requirements={"projector": 2})
    )

    assert "equipment_requirements" in errors


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


def test_the_same_equipment_cannot_be_listed_twice():
    _, errors = schema.parse_payload(
        valid_payload(
            equipment_requirements=[
                {"equipment_type": "projector", "quantity": 2},
                {"equipment_type": "Projector", "quantity": 1},
            ]
        )
    )

    assert "more than once" in errors["equipment_requirements"]


def test_unknown_fields_on_an_equipment_item_are_rejected():
    _, errors = schema.parse_payload(
        valid_payload(
            equipment_requirements=[
                {"equipment_type": "projector", "quantity": 2, "colour": "black"}
            ]
        )
    )

    assert "colour" in errors["equipment_requirements"]


# AC: an event request carries registration needs where relevant.
def test_registration_needs_are_kept_as_text():
    record, errors = schema.parse_payload(valid_payload())

    assert errors == {}
    assert record["registration_needs"].startswith("Open registration")


def test_blank_registration_needs_are_stored_as_none():
    """No registration needed is recorded as null rather than an empty string."""
    record, errors = schema.parse_payload(valid_payload(registration_needs="   "))

    assert errors == {}
    assert record["registration_needs"] is None


def test_registration_needs_must_be_text():
    _, errors = schema.parse_payload(valid_payload(registration_needs=["a", "b"]))

    assert "registration_needs" in errors


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
    ({'status': 'approved'}, '_body'),
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
    table.select.assert_called_once_with('*')
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


def test_create_handler_propagates_creation_failure():
    error = service.EventRequestError('Creation failed. Please try again.', 502)
    with Flask(__name__).test_request_context(json=valid_payload()), \
         patch.object(routes, 'create_event_request', side_effect=error), \
         pytest.raises(service.EventRequestError) as caught:
        routes.create()
    assert caught.value is error


def test_error_handler_returns_error_without_success_confirmation():
    error = service.EventRequestError('Missing information.', errors={'event_name': 'Event name is required.'})
    with Flask(__name__).app_context():
        response, status = routes.handle_event_request_error(error)
    assert status == 400
    assert response.get_json() == {'error': 'Missing information.', 'errors': error.errors}
    assert 'message' not in response.get_json()


@pytest.mark.parametrize('body', [[], 'text', 123, None, {'save_as_draft': 'false'}])
def test_create_handler_rejects_malformed_body(body):
    with Flask(__name__).test_request_context(json=body), \
         patch.object(routes, 'create_event_request') as create, \
         pytest.raises(service.EventRequestError) as caught:
        routes.create()
    assert caught.value.status_code == 400
    assert caught.value.message
    create.assert_not_called()


