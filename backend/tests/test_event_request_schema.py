"""Unit tests for event request validation.

Traces to the "Create and Submit Event Request" user story. Each test names
the acceptance criterion it covers so the mapping stays visible in the sprint
evidence. These tests do not touch Supabase.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.schemas import event_request as schema

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


# AC: The user can review the entered details before submitting the request.
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


def test_a_partially_filled_draft_produces_no_format_errors():
    """Saving a draft should not complain about fields the user has not reached yet."""
    record, errors = schema.parse_payload({"event_name": "Untitled", "purpose": ""})

    assert errors == {}
    assert record == {"event_name": "Untitled", "purpose": None}


# --- Draft Event Requests -------------------------------------------------
# AC: The system allows users to return to and edit their saved drafts.


@pytest.mark.parametrize(
    "field",
    [
        "event_name",
        "purpose",
        "description",
        "start_datetime",
        "end_datetime",
        "capacity_needed",
        "room_layout",
        "registration_needs",
    ],
)
def test_any_optional_field_can_be_cleared_with_null(field):
    """Editing a draft includes removing something entered earlier."""
    record, errors = schema.parse_payload({field: None})

    assert errors == {}
    assert record[field] is None


def test_clearing_the_room_layout_produces_null_not_an_empty_string():
    """room_layout is a PostgreSQL enum, which would reject ""."""
    record, errors = schema.parse_payload({"room_layout": ""})

    assert errors == {}
    assert record["room_layout"] is None


def test_clearing_the_attendance_is_allowed_on_a_draft():
    record, errors = schema.parse_payload({"capacity_needed": None})

    assert errors == {}
    assert record["capacity_needed"] is None


def test_a_cleared_field_still_counts_as_missing_at_submission():
    record, _ = schema.parse_payload(valid_payload(event_name=None))

    assert "event_name" in schema.find_missing(record)


def test_editing_one_field_leaves_the_others_untouched():
    """A partial edit must not blank out fields the body did not mention."""
    record, errors = schema.parse_payload({"capacity_needed": 200})

    assert errors == {}
    assert record == {"capacity_needed": 200}


def test_an_invalid_value_is_still_rejected_while_editing_a_draft():
    _, errors = schema.parse_payload({"room_layout": "igloo"})

    assert "room_layout" in errors


def test_the_organiser_cannot_be_cleared():
    """event_organiser_id is NOT NULL in the database."""
    _, errors = schema.parse_payload({"event_organiser_id": None})

    assert "event_organiser_id" in errors


def test_accessibility_flags_cannot_be_cleared():
    """Both are NOT NULL in the database, so null is not a valid answer."""
    _, errors = schema.parse_payload({"need_wheelchair_accessibility": None})

    assert "need_wheelchair_accessibility" in errors


def test_every_status_the_database_accepts_is_known_to_the_code():
    assert schema.STATUS_DRAFT in schema.ALL_STATUSES
    assert schema.STATUS_SUBMITTED in schema.ALL_STATUSES
    assert schema.ALL_STATUSES == {
        "draft",
        "submitted",
        "under_review",
        "approved",
        "rejected",
    }
