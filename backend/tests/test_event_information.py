"""Unit tests for viewing and updating event information.

Traces to the "View Event Information" and "Update Event Information" user
stories. Each test names the acceptance criterion it covers. These tests do not
touch Supabase.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.schemas import event as schema

FUTURE = datetime.now(timezone.utc) + timedelta(days=30)


def an_event(**overrides):
    event = {
        "event_id": 6,
        "event_name": "Halloween",
        "purpose": "Student social",
        "description": "An evening event.",
        "start_datetime": FUTURE.isoformat(),
        "end_datetime": (FUTURE + timedelta(hours=3)).isoformat(),
        "capacity_needed": 120,
        "room_layout": "theatre",
        "required_facilities": ["projector"],
        "need_wheelchair_accessibility": True,
        "need_blind_accessibility": False,
        "equipment_requirements": [{"equipment_type": "projector", "quantity": 2, "notes": None}],
        "registration_needs": "Open registration.",
        "status": "planning",
    }
    event.update(overrides)
    return event


# AC: The system allows authorised users to update event information during
# the "Planning" phase.
def test_an_event_in_planning_can_be_edited():
    assert schema.is_editable(an_event()) is True


@pytest.mark.parametrize("status", ["confirmed", "completed", "cancelled"])
def test_an_event_past_planning_cannot_be_edited(status):
    assert schema.is_editable(an_event(status=status)) is False


def test_a_confirmed_event_says_why_it_cannot_be_edited():
    """The customer was explicit that arrangements are fixed once confirmed."""
    message = schema.why_not_editable(an_event(status="confirmed"))

    assert "confirmed" in message
    assert "no longer be changed" in message


# AC: The system allows normal or less critical updates to be saved without
# additional approval.
@pytest.mark.parametrize(
    "field, value",
    [
        ("event_name", "Halloween Night"),
        ("purpose", "Something else"),
        ("description", "A different evening."),
        ("registration_needs", "Closed registration."),
    ],
)
def test_a_non_critical_change_needs_no_confirmation(field, value):
    changes = schema.diff(an_event(), {field: value})

    assert schema.classify(changes) == schema.CHANGE_EDIT
    assert schema.critical_changes(changes) == ()


# AC: The system triggers a warning modal when critical fields which may affect
# existing arrangements are modified.
@pytest.mark.parametrize(
    "field, value",
    [
        ("start_datetime", (FUTURE + timedelta(days=1)).isoformat()),
        ("end_datetime", (FUTURE + timedelta(hours=5)).isoformat()),
        ("capacity_needed", 300),
        ("room_layout", "banquet"),
        ("required_facilities", ["projector", "stage"]),
        ("need_wheelchair_accessibility", False),
        ("need_blind_accessibility", True),
        ("equipment_requirements", []),
    ],
)
def test_a_critical_change_is_flagged(field, value):
    changes = schema.diff(an_event(), {field: value})

    assert schema.classify(changes) == schema.CHANGE_CRITICAL
    assert field in schema.critical_changes(changes)


def test_every_critical_field_has_a_readable_label():
    """The warning names the fields, so each needs wording a user recognises."""
    for field in schema.CRITICAL_FIELDS:
        assert field in schema.LABELS


def test_a_mixed_edit_counts_as_critical():
    """One critical field among several still has to be confirmed."""
    changes = schema.diff(an_event(), {"event_name": "New name", "capacity_needed": 300})

    assert schema.classify(changes) == schema.CHANGE_CRITICAL
    assert schema.describe_critical(changes) == ["Expected attendance"]


def test_critical_and_non_critical_fields_do_not_overlap():
    assert not set(schema.CRITICAL_FIELDS) & set(schema.NON_CRITICAL_FIELDS)


# AC: The system displays information including ... so every field the story
# lists must be one the user can also maintain.
def test_every_field_the_story_lists_is_writable():
    for field in (
        "event_name", "purpose", "description", "start_datetime", "end_datetime",
        "capacity_needed", "room_layout", "required_facilities",
        "need_wheelchair_accessibility", "need_blind_accessibility",
        "equipment_requirements", "registration_needs",
    ):
        assert field in schema.WRITABLE_FIELDS


def test_system_controlled_fields_are_not_writable():
    """A client must not set the status or reassign the event through an edit."""
    for field in ("status", "event_id", "event_organiser_id", "event_coordinator_id"):
        assert field not in schema.WRITABLE_FIELDS


def test_an_unrecognised_field_is_refused():
    _, errors = schema.parse_payload({"status": "confirmed"})

    assert "_body" in errors
    assert "status" in errors["_body"]


def test_a_non_object_body_is_refused():
    _, errors = schema.parse_payload("Halloween")

    assert "_body" in errors


# Field rules are reused from event_request, so one check that the delegation
# is wired up is enough here.
def test_field_validation_is_applied():
    _, errors = schema.parse_payload({"capacity_needed": 0})

    assert "capacity_needed" in errors


def test_only_the_fields_sent_are_returned():
    """A partial edit must not rewrite fields the user did not touch."""
    record, errors = schema.parse_payload({"purpose": "  Updated  "})

    assert errors == {}
    assert record == {"purpose": "Updated"}


# AC: The system displays the current and latest version of the event
# information, so an edit records what actually moved.
def test_a_diff_records_the_old_and_new_value():
    changes = schema.diff(an_event(), {"capacity_needed": 300})

    assert changes == {"capacity_needed": {"from": 120, "to": 300}}


def test_setting_a_field_to_its_current_value_is_not_a_change():
    assert schema.diff(an_event(), {"capacity_needed": 120}) == {}


# Timing rules span two fields, so a partial edit is checked against the row.
def test_moving_only_the_end_date_is_checked_against_the_stored_start():
    errors = schema.check_timing(
        an_event(), {"end_datetime": (FUTURE - timedelta(hours=1)).isoformat()}
    )

    assert "end_datetime" in errors


def test_an_edit_that_does_not_touch_the_dates_is_not_blocked_by_a_past_start():
    """An event already under way still needs its description fixed."""
    started = datetime.now(timezone.utc) - timedelta(days=1)
    event = an_event(
        start_datetime=started.isoformat(),
        end_datetime=(started + timedelta(hours=2)).isoformat(),
    )

    assert schema.check_timing(event, {"description": "Corrected."}) == {}


def test_moving_the_start_into_the_past_is_refused():
    past = datetime.now(timezone.utc) - timedelta(days=1)

    errors = schema.check_timing(an_event(), {"start_datetime": past.isoformat()})

    assert "start_datetime" in errors
