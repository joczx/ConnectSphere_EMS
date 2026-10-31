"""Unit tests for amending an event request after it is sent back to the Organiser.

Traces to the "Amend Event Request" user story. These tests do not touch
Supabase.
"""

import pytest
from unittest.mock import Mock, patch
from flask import Flask

from app.schemas import event_request as schema
from app.routes import event_requests as routes
from app.services.event_request_service import EventRequestError
from app.services import event_request_workflow as workflow
from app.services.event_request_workflow import _split_note, can_amend


# AC: The system records the updated information and the amendment.
# TC-AER-001: Check that a changed field records its old and new values.
def test_a_change_records_the_old_and_new_value():
    existing = {"capacity_needed": 300, "event_name": "Hackathon"}

    assert schema.diff(existing, {"capacity_needed": 150}) == {
        "capacity_needed": {"from": 300, "to": 150}
    }


# TC-AER-002: Check that only changed fields are recorded.
def test_only_the_fields_that_changed_are_recorded():
    existing = {"capacity_needed": 300, "purpose": "Original", "event_name": "Hack"}
    record = {"capacity_needed": 150, "purpose": "Original"}

    assert set(schema.diff(existing, record)) == {"capacity_needed"}


# TC-AER-003: Check that clearing a populated field is recorded.
def test_clearing_a_field_is_recorded_as_a_change():
    existing = {"room_layout": "theatre"}

    assert schema.diff(existing, {"room_layout": None}) == {
        "room_layout": {"from": "theatre", "to": None}
    }


# TC-AER-004: Check that filling an empty field is recorded.
def test_filling_a_previously_empty_field_is_recorded():
    assert schema.diff({}, {"purpose": "Now provided"}) == {
        "purpose": {"from": None, "to": "Now provided"}
    }


# The Organiser's reply travels with the edit but is not a request field.
# TC-AER-005: Check that an organiser note is separated from request changes.
def test_a_note_is_separated_from_the_request_fields():
    payload, note = _split_note({"capacity_needed": 150, "note": "Reduced to fit."})

    assert payload == {"capacity_needed": 150}
    assert note == "Reduced to fit."


# TC-AER-006: Check that an amendment can be saved without a note.
def test_a_note_is_optional():
    payload, note = _split_note({"capacity_needed": 150})

    assert payload == {"capacity_needed": 150}
    assert note is None


# TC-AER-007: Check that a blank amendment note is treated as no note.
def test_a_blank_note_is_treated_as_no_note():
    _, note = _split_note({"note": "   "})

    assert note is None


# TC-AER-008: Check that a non-text amendment note gives an error.
def test_a_note_must_be_text():
    with pytest.raises(EventRequestError) as caught:
        _split_note({"note": 42})

    assert "note" in caught.value.errors


# TC-AER-009: Check that extracting a note does not change the original payload.
def test_splitting_a_note_does_not_mutate_the_caller_s_payload():
    original = {"capacity_needed": 150, "note": "Reduced."}
    _split_note(original)

    assert original == {"capacity_needed": 150, "note": "Reduced."}


# AC: a rejected request can be amended and resubmitted; approval is final.
# TC-AER-010: Check which request statuses allow an amendment.
@pytest.mark.parametrize("status, allowed", [
    ("rejected", True), ("planning", False), ("draft", False), ("cancelled", False),
])
def test_only_a_request_sent_back_to_the_organiser_can_be_amended(status, allowed):
    """The customer confirmed rejection "is not necessarily final"."""
    assert can_amend({"event_request_id": 1, "status": status}) is allowed


# "submitted" no longer settles the question on its own. Clarification is a
# sub-state of it, so the latest review decides who holds the request.
# TC-AER-011: Check that a submitted request can be amended only after clarification is requested by an Event Coordinator.
@pytest.mark.parametrize("outcome, allowed", [
    ("clarification_requested", True), ("approved", False), (None, False),
])
def test_a_submitted_request_is_amendable_only_while_clarification_is_outstanding(
    monkeypatch, outcome, allowed
):
    monkeypatch.setattr(
        "app.services.event_request_review_service.latest_review",
        lambda _id: None if outcome is None else {"outcome": outcome},
    )

    assert can_amend({"event_request_id": 1, "status": "submitted"}) is allowed


# TC-AER-012: Check that editing a clarified request saves an amendment record.
def test_clarified_request_edit_records_an_amendment(monkeypatch):
    existing = {
        "event_request_id": 42,
        "event_organiser_id": "organiser-id",
        "status": "submitted",
    }
    updated = {**existing, "event_name": "Updated event"}
    changes = {"event_name": {"from": "Original event", "to": "Updated event"}}
    saved_amendment = {
        "event_request_id": 42,
        "amended_by": "organiser-id",
        "changes": changes,
        "note": "Clarified details.",
    }
    table = Mock()
    table.insert.return_value.execute.return_value = Mock(data=[saved_amendment])

    monkeypatch.setattr(workflow.requests, "require_event_request", lambda _id: existing)
    monkeypatch.setattr(
        workflow.reviews,
        "latest_review",
        lambda _id: {"outcome": "clarification_requested"},
    )
    monkeypatch.setattr(
        workflow.requests, "apply_edit", lambda _existing, _payload: (updated, changes)
    )

    def execute_on(table_name, operation, *, action):
        assert table_name == workflow.AMENDMENT_TABLE
        assert action == "record the amendment"
        return operation(table).data

    monkeypatch.setattr(workflow.reviews, "execute_on", execute_on)

    row, amendment = workflow.edit(
        42, {"event_name": "Updated event", "note": " Clarified details. "}
    )

    assert row == updated
    assert amendment == saved_amendment
    table.insert.assert_called_once_with(saved_amendment)


# AC3: The Event Organiser can review the updated request before resubmission.
# TC-AER-013: Check that updated request details can be retrieved before resubmission.
def test_updated_request_can_be_retrieved_before_resubmission(monkeypatch):
    updated = {
        "event_request_id": 42,
        "event_name": "Updated event",
        "capacity_needed": 150,
        "status": "rejected",
    }
    get_event_request = Mock(return_value=updated)
    monkeypatch.setattr(routes, "get_event_request", get_event_request)
    app = Flask(__name__)
    app.register_blueprint(routes.event_requests_bp)

    response = app.test_client().get("/api/event-requests/42")

    assert response.status_code == 200
    assert response.get_json() == updated
    get_event_request.assert_called_once_with(42)


# AC4: The amended event request can be resubmitted for Coordinator review.
# TC-AER-014: Check that a completed amendment can be resubmitted for review.
def test_amended_request_can_be_resubmitted_for_review(monkeypatch):
    amended = {
        "event_request_id": 42,
        "event_organiser_id": "organiser-id",
        "event_name": "Updated event",
        "status": "rejected",
    }
    resubmitted = {**amended, "status": "submitted"}
    find_blocking_errors = Mock(return_value={})
    mark_submitted = Mock(return_value=resubmitted)
    monkeypatch.setattr(workflow.requests, "require_event_request", lambda _id: amended)
    monkeypatch.setattr(
        workflow.requests, "find_blocking_errors", find_blocking_errors
    )
    monkeypatch.setattr(workflow.requests, "mark_submitted", mark_submitted)

    row, was_resubmission = workflow.send_for_review(42)

    assert row == resubmitted
    assert was_resubmission is True
    find_blocking_errors.assert_called_once_with(amended)
    mark_submitted.assert_called_once_with(42)
