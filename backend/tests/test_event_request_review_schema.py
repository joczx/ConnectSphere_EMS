"""Unit tests for Event Coordinator review validation.

Traces to the "Event Review and Approval" user story. Each test names the
acceptance criterion it covers. These tests do not touch Supabase.
"""

import pytest

from app.schemas import event_request as request_schema
from app.schemas import event_request_review as review

# Users are managed by Supabase Auth, so ids are UUIDs.
COORDINATOR = "3f1b9c64-7a2e-4d51-9b0f-2c8e5a6d4f10"


# AC: The Event Coordinator can approve, reject, or request clarification.
# TC-RER-007: Check that every supported review outcome is accepted.
@pytest.mark.parametrize("outcome", sorted(review.OUTCOMES))
def test_each_outcome_is_accepted(outcome):
    record, errors = review.parse_payload(
        {"outcome": outcome, "comments": "Looks reasonable."}, COORDINATOR
    )

    assert errors == {}
    assert record["outcome"] == outcome
    assert record["reviewer_id"] == COORDINATOR


# TC-RER-008: Check that an unknown review outcome gives an error.
def test_an_unknown_outcome_is_rejected():
    _, errors = review.parse_payload({"outcome": "maybe"}, COORDINATOR)

    assert "outcome" in errors


# TC-RER-009: Check that a missing review outcome gives an error.
def test_an_outcome_is_required():
    _, errors = review.parse_payload({}, COORDINATOR)

    assert "outcome" in errors


# TC-RER-010: Check that a missing reviewer identity gives an error.
def test_a_reviewer_is_required():
    """No signed-in user means there is nobody to attribute the review to."""
    _, errors = review.parse_payload({"outcome": "approved"}, None)

    assert "reviewer_id" in errors


# TC-RER-011: Check that a malformed reviewer UUID gives an error.
def test_the_reviewer_must_be_a_user_id():
    _, errors = review.parse_payload({"outcome": "approved"}, "seven")

    assert "reviewer_id" in errors


# The identity comes from the session, so a body that tries to name someone
# else is refused outright rather than quietly ignored.
# TC-RER-012: Check that reviewer identity cannot be supplied in the request body.
def test_a_client_cannot_name_the_reviewer():
    _, errors = review.parse_payload(
        {"outcome": "approved", "reviewer_id": COORDINATOR}, COORDINATOR
    )

    assert "_body" in errors
    assert "reviewer_id" in errors["_body"]


# AC: The Event Coordinator can add comments along with the outcome.
# TC-RER-013: Check that review comments are trimmed and saved.
def test_comments_are_kept_with_the_outcome():
    record, errors = review.parse_payload(
        {"outcome": "approved", "comments": "  Approved for Hall A. "}, COORDINATOR
    )

    assert errors == {}
    assert record["comments"] == "Approved for Hall A."


# TC-RER-014: Check that approval is allowed without a comment.
def test_approving_without_a_comment_is_allowed():
    record, errors = review.parse_payload({"outcome": "approved"}, COORDINATOR)

    assert errors == {}
    assert record["comments"] is None


# TC-RER-015: Check that clarification and rejection require a reason.
@pytest.mark.parametrize("outcome", sorted(review.OUTCOMES_NEEDING_COMMENTS))
def test_a_reason_is_required_when_not_approving(outcome):
    """An Organiser told "rejected" with no reason has nothing to act on."""
    _, errors = review.parse_payload({"outcome": outcome}, COORDINATOR)

    assert "comments" in errors


# TC-RER-016: Check that a whitespace-only reason gives an error.
@pytest.mark.parametrize("outcome", sorted(review.OUTCOMES_NEEDING_COMMENTS))
def test_a_blank_reason_does_not_count(outcome):
    _, errors = review.parse_payload(
        {"outcome": outcome, "comments": "   "}, COORDINATOR
    )

    assert "comments" in errors


# TC-RER-017: Check that a non-text comment gives an error.
def test_comments_must_be_text():
    _, errors = review.parse_payload(
        {"outcome": "approved", "comments": 42}, COORDINATOR
    )

    assert "comments" in errors


# TC-RER-018: Check that an unknown review field gives an error.
def test_unknown_fields_are_rejected():
    _, errors = review.parse_payload(
        {"outcome": "approved", "decision": "yes"}, COORDINATOR
    )

    assert "_body" in errors


# TC-RER-019: Check that a non-object review body gives an error.
def test_a_non_object_body_is_rejected():
    _, errors = review.parse_payload("approved")

    assert "_body" in errors


# AC: The system records the outcome of the review.
# TC-RER-020: Check that approval changes the request status to planning.
def test_approving_moves_the_request_into_planning():
    """Approval starts planning; it is a review outcome, not a status."""
    assert review.OUTCOME_TO_STATUS["approved"] == request_schema.STATUS_PLANNING


# TC-RER-021: Check that rejection changes the request status to rejected.
def test_rejecting_moves_the_request_to_rejected():
    assert review.OUTCOME_TO_STATUS["rejected"] == request_schema.STATUS_REJECTED


# TC-RER-022: Check that clarification keeps the request status as submitted.
def test_requesting_clarification_leaves_the_request_submitted():
    """Clarification is a sub-state, not a status: the decision is still open."""
    assert (
        review.OUTCOME_TO_STATUS["clarification_requested"]
        == request_schema.STATUS_SUBMITTED
    )


# TC-RER-023: Check that every supported outcome has a status mapping.
def test_every_outcome_maps_to_a_status():
    assert set(review.OUTCOME_TO_STATUS) == review.OUTCOMES


# TC-RER-024: Check that every mapped status exists in the database status list.
def test_every_mapped_status_exists_in_the_database_enum():
    assert set(review.OUTCOME_TO_STATUS.values()) <= request_schema.ALL_STATUSES


# AC: The system allows Event Coordinators to view submitted event requests.
# TC-RER-025: Check that only submitted requests can be reviewed.
def test_only_submitted_requests_can_be_reviewed():
    assert review.REVIEWABLE_STATUSES == {request_schema.STATUS_SUBMITTED}
