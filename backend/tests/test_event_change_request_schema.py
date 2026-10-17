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
    assert "event_name" not in schema.PERMITTED_FIELDS
    assert "status" not in schema.PERMITTED_FIELDS


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reason_is_required_with_the_exact_inline_message(reason):
    _, errors = schema.parse_submission(body(reason=reason))
    assert errors["reason"] == "Please provide a reason for this change request"


def test_unpermitted_change_is_rejected():
    _, errors = schema.parse_submission(body(proposed_values={"event_name": "New"}))
    assert "proposed_values" in errors


def test_values_are_cleaned_by_existing_event_rules():
    parsed, errors = schema.parse_submission(body(proposed_values={
        "capacity_needed": "200",
        "start_datetime": FUTURE.isoformat(),
    }))
    assert errors == {}
    assert parsed["proposed_values"]["capacity_needed"] == 200
    assert parsed["proposed_values"]["start_datetime"].endswith("+00:00")


def test_diff_excludes_unchanged_values():
    assert schema.calculate_changes(
        {"capacity_needed": 100}, {"capacity_needed": 100}
    ) == {}


def test_critical_fields_have_readable_names():
    changes = {"capacity_needed": {"from": 100, "to": 200}}
    assert schema.critical_fields(changes) == ["Expected attendance"]

