"""Unit tests for amending an event request after it is sent back to the Organiser.

Traces to the "Amend Event Request" user story. These tests do not touch
Supabase.
"""

import pytest

from app.schemas import event_request as schema
from app.services.event_request_service import EventRequestError
from app.services.event_request_workflow import _split_note, can_amend


# AC: The system records the updated information and the amendment.
def test_a_change_records_the_old_and_new_value():
    existing = {"capacity_needed": 300, "event_name": "Hackathon"}

    assert schema.diff(existing, {"capacity_needed": 150}) == {
        "capacity_needed": {"from": 300, "to": 150}
    }


def test_setting_a_field_to_what_it_already_is_is_not_a_change():
    existing = {"capacity_needed": 150}

    assert schema.diff(existing, {"capacity_needed": 150}) == {}


def test_only_the_fields_that_changed_are_recorded():
    existing = {"capacity_needed": 300, "purpose": "Original", "event_name": "Hack"}
    record = {"capacity_needed": 150, "purpose": "Original"}

    assert set(schema.diff(existing, record)) == {"capacity_needed"}


def test_clearing_a_field_is_recorded_as_a_change():
    existing = {"room_layout": "theatre"}

    assert schema.diff(existing, {"room_layout": None}) == {
        "room_layout": {"from": "theatre", "to": None}
    }


def test_filling_a_previously_empty_field_is_recorded():
    assert schema.diff({}, {"purpose": "Now provided"}) == {
        "purpose": {"from": None, "to": "Now provided"}
    }


# The Organiser's reply travels with the edit but is not a request field.
def test_a_note_is_separated_from_the_request_fields():
    payload, note = _split_note({"capacity_needed": 150, "note": "Reduced to fit."})

    assert payload == {"capacity_needed": 150}
    assert note == "Reduced to fit."


def test_a_note_is_optional():
    payload, note = _split_note({"capacity_needed": 150})

    assert payload == {"capacity_needed": 150}
    assert note is None


def test_a_blank_note_is_treated_as_no_note():
    _, note = _split_note({"note": "   "})

    assert note is None


def test_a_note_must_be_text():
    with pytest.raises(EventRequestError) as caught:
        _split_note({"note": 42})

    assert "note" in caught.value.errors


def test_splitting_a_note_does_not_mutate_the_caller_s_payload():
    original = {"capacity_needed": 150, "note": "Reduced."}
    _split_note(original)

    assert original == {"capacity_needed": 150, "note": "Reduced."}


# AC: a rejected request can be amended and resubmitted; approval is final.
@pytest.mark.parametrize("status, allowed", [
    ("rejected", True), ("approved", False), ("submitted", False), ("draft", False),
])
def test_only_a_request_sent_back_to_the_organiser_can_be_amended(status, allowed):
    """The customer confirmed rejection "is not necessarily final"."""
    assert can_amend({"event_request_id": 1, "status": status}) is allowed
