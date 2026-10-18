"""Validation tests for submitting an event change request."""

from datetime import datetime, timedelta, timezone

import pytest

from app.schemas import event_change_request as schema

FUTURE = datetime.now(timezone.utc) + timedelta(days=30)
UPDATED_AT = datetime.now(timezone.utc).isoformat()


def body(**overrides):
    value = {
        "reason": "Attendance increased.",
        "proposed_values": {"capacity_needed": 200},
        "expected_event_updated_at": UPDATED_AT,
    }
    value.update(overrides)
    return value


def test_only_story_fields_are_permitted():
    for field in schema.PERMITTED_FIELDS:
        assert field in schema.PERMITTED_FIELDS
    assert "event_name" in schema.PERMITTED_FIELDS
    assert "description" in schema.PERMITTED_FIELDS
    assert "status" not in schema.PERMITTED_FIELDS


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reason_is_required_with_the_exact_inline_message(reason):
    _, errors = schema.parse_submission(body(reason=reason))
    assert errors["reason"] == "Please provide a reason for this change request"


def test_unpermitted_change_is_rejected():
    _, errors = schema.parse_submission(body(proposed_values={"purpose": "New"}))
    assert "proposed_values" in errors


def test_values_are_cleaned_by_existing_event_rules():
    parsed, errors = schema.parse_submission(body(proposed_values={
        "capacity_needed": "200",
        "start_datetime": FUTURE.isoformat(),
    }))
    assert errors == {}
    assert parsed["proposed_values"]["capacity_needed"] == 200
    assert parsed["proposed_values"]["start_datetime"].endswith("+00:00")


def test_non_object_submission_is_rejected():
    parsed, errors = schema.parse_submission(None)
    assert parsed == {}
    assert errors == {"_body": "Expected a JSON object describing the change request."}


def test_unknown_body_field_is_rejected():
    _, errors = schema.parse_submission(body(extra=True))
    assert errors["_body"] == "Unrecognised field(s): extra."


def test_overlong_reason_is_rejected():
    _, errors = schema.parse_submission(body(reason="x" * 2001))
    assert errors["reason"] == "The reason must be 2000 characters or fewer."


@pytest.mark.parametrize("proposed", [None, "capacity_needed=200"])
def test_proposed_values_must_be_an_object(proposed):
    _, errors = schema.parse_submission(body(proposed_values=proposed))
    assert errors["proposed_values"] == "Proposed changes must be a JSON object."


def test_invalid_permitted_value_returns_field_error():
    _, errors = schema.parse_submission(body(proposed_values={"capacity_needed": "many"}))
    assert errors["capacity_needed"] == "Expected attendance must be a whole number."


@pytest.mark.parametrize("updated_at", [None, "", "not-a-date", "2030-01-01T12:00:00"])
def test_event_version_timestamp_must_be_an_aware_iso_datetime(updated_at):
    _, errors = schema.parse_submission(body(expected_event_updated_at=updated_at))
    assert errors["expected_event_updated_at"] == "Reload the event before submitting changes."


def test_confirmation_flag_must_be_boolean():
    _, errors = schema.parse_submission(body(confirm_critical="yes"))
    assert errors["confirm_critical"] == "Confirmation must be true or false."


def test_valid_confirmation_and_whitespace_are_normalised():
    parsed, errors = schema.parse_submission(body(
        reason="  Attendance increased.  ", confirm_critical=True,
    ))
    assert errors == {}
    assert parsed["reason"] == "Attendance increased."
    assert parsed["expected_event_updated_at"] == UPDATED_AT
    assert parsed["confirm_critical"] is True

