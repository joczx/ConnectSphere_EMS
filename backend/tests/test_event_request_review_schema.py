"""Unit tests for Event Coordinator review validation.

Traces to the "Event Review and Approval" user story. Each test names the
acceptance criterion it covers. These tests do not touch Supabase.
"""

import pytest

from app.schemas import event_request as request_schema
from app.schemas import event_request_review as review


# AC: The Event Coordinator can approve, reject, or request clarification.
@pytest.mark.parametrize("outcome", sorted(review.OUTCOMES))
def test_each_outcome_is_accepted(outcome):
    record, errors = review.parse_payload(
        {"reviewer_id": 7, "outcome": outcome, "comments": "Looks reasonable."}
    )

    assert errors == {}
    assert record["outcome"] == outcome
    assert record["reviewer_id"] == 7


def test_an_unknown_outcome_is_rejected():
    _, errors = review.parse_payload({"reviewer_id": 7, "outcome": "maybe"})

    assert "outcome" in errors


def test_an_outcome_is_required():
    _, errors = review.parse_payload({"reviewer_id": 7})

    assert "outcome" in errors


def test_a_reviewer_is_required():
    _, errors = review.parse_payload({"outcome": "approved"})

    assert "reviewer_id" in errors


def test_the_reviewer_must_be_a_user_id():
    _, errors = review.parse_payload({"reviewer_id": "seven", "outcome": "approved"})

    assert "reviewer_id" in errors


# AC: The Event Coordinator can add comments along with the outcome.
def test_comments_are_kept_with_the_outcome():
    record, errors = review.parse_payload(
        {"reviewer_id": 7, "outcome": "approved", "comments": "  Approved for Hall A. "}
    )

    assert errors == {}
    assert record["comments"] == "Approved for Hall A."


def test_approving_without_a_comment_is_allowed():
    record, errors = review.parse_payload({"reviewer_id": 7, "outcome": "approved"})

    assert errors == {}
    assert record["comments"] is None


@pytest.mark.parametrize("outcome", sorted(review.OUTCOMES_NEEDING_COMMENTS))
def test_a_reason_is_required_when_not_approving(outcome):
    """An Organiser told "rejected" with no reason has nothing to act on."""
    _, errors = review.parse_payload({"reviewer_id": 7, "outcome": outcome})

    assert "comments" in errors


@pytest.mark.parametrize("outcome", sorted(review.OUTCOMES_NEEDING_COMMENTS))
def test_a_blank_reason_does_not_count(outcome):
    _, errors = review.parse_payload(
        {"reviewer_id": 7, "outcome": outcome, "comments": "   "}
    )

    assert "comments" in errors


def test_comments_must_be_text():
    _, errors = review.parse_payload(
        {"reviewer_id": 7, "outcome": "approved", "comments": 42}
    )

    assert "comments" in errors


def test_unknown_fields_are_rejected():
    _, errors = review.parse_payload(
        {"reviewer_id": 7, "outcome": "approved", "decision": "yes"}
    )

    assert "_body" in errors


def test_a_non_object_body_is_rejected():
    _, errors = review.parse_payload("approved")

    assert "_body" in errors


# AC: The system records the outcome of the review.
def test_approving_moves_the_request_to_approved():
    assert review.OUTCOME_TO_STATUS["approved"] == request_schema.STATUS_APPROVED


def test_rejecting_moves_the_request_to_rejected():
    assert review.OUTCOME_TO_STATUS["rejected"] == request_schema.STATUS_REJECTED


def test_requesting_clarification_keeps_the_request_under_review():
    """The customer confirmed clarification is a sub-state of under_review."""
    assert (
        review.OUTCOME_TO_STATUS["clarification_requested"]
        == request_schema.STATUS_UNDER_REVIEW
    )


def test_every_outcome_maps_to_a_status():
    assert set(review.OUTCOME_TO_STATUS) == review.OUTCOMES


def test_every_mapped_status_exists_in_the_database_enum():
    assert set(review.OUTCOME_TO_STATUS.values()) <= request_schema.ALL_STATUSES


# AC: The system allows Event Coordinators to view submitted event requests.
def test_only_submitted_or_under_review_requests_can_be_reviewed():
    assert review.REVIEWABLE_STATUSES == {
        request_schema.STATUS_SUBMITTED,
        request_schema.STATUS_UNDER_REVIEW,
    }


def test_a_draft_is_not_reviewable():
    assert request_schema.STATUS_DRAFT not in review.REVIEWABLE_STATUSES


@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_an_already_decided_request_is_not_reviewable(status):
    assert status not in review.REVIEWABLE_STATUSES


# AC: The Event Organiser should be notified of the outcome.
@pytest.mark.parametrize("outcome", sorted(review.OUTCOMES))
def test_both_parties_get_a_message_for_every_outcome(outcome):
    organiser_text, reviewer_text = review.describe(outcome, "Orientation Night")

    assert "Orientation Night" in organiser_text
    assert "Orientation Night" in reviewer_text
    assert organiser_text != reviewer_text


def test_messages_survive_a_request_with_no_name():
    organiser_text, reviewer_text = review.describe("approved", None)

    assert organiser_text and reviewer_text
