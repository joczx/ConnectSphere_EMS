"""Unit tests for who may review an event request.

Covers "each event request, once submitted, is received by a single
coordinator": row level security keeps a request out of anyone else's listing,
but a request id is guessable, so the rule is enforced in the service too.

These tests do not touch Supabase.
"""

from unittest.mock import patch

import pytest

from app.services import event_request_review_service as service
from app.services.event_request_service import EventRequestError

COORDINATOR = "3f1b9c64-7a2e-4d51-9b0f-2c8e5a6d4f10"
ANOTHER_COORDINATOR = "9a2c7d31-5e84-4b02-8c6f-1d3b7e9a5c42"


def a_request(**overrides):
    record = {
        "event_request_id": 1,
        "event_name": "Orientation Night",
        "status": "submitted",
        "event_coordinator_id": COORDINATOR,
    }
    record.update(overrides)
    return record


def review_as(reviewer_id, existing):
    """Run a review, with everything past the authorisation check stubbed."""
    with patch.object(service, "get_event_request", return_value=existing), \
         patch.object(service, "_record_review", return_value={"outcome": "approved"}), \
         patch.object(service, "_apply_outcome", return_value=existing), \
         patch.object(service, "_notify", return_value=[]):
        return service.review_event_request(
            1, {"outcome": "approved"}, reviewer_id
        )


def test_the_assigned_coordinator_may_review():
    _, recorded, _ = review_as(COORDINATOR, a_request())

    assert recorded["outcome"] == "approved"


def test_another_coordinator_may_not_review():
    """A guessed request id must not be enough to decide someone else's work."""
    with pytest.raises(EventRequestError) as caught:
        review_as(ANOTHER_COORDINATOR, a_request())

    assert caught.value.status_code == 403
    assert "another Event Coordinator" in caught.value.message


def test_an_unassigned_request_cannot_be_reviewed():
    """A missing assignment is a data fault, not permission for anyone.

    The Organiser can see their own request, so allowing an unassigned one to
    be reviewed by whoever can reach it would let them approve it themselves.
    """
    with pytest.raises(EventRequestError) as caught:
        review_as(COORDINATOR, a_request(event_coordinator_id=None))

    assert caught.value.status_code == 409
    assert "no Event Coordinator assigned" in caught.value.message


def test_an_organiser_cannot_approve_their_own_unassigned_request():
    organiser = "5d7e2a18-3c94-4f60-b2a1-8e4c6d0f9b73"

    with pytest.raises(EventRequestError):
        review_as(organiser, a_request(event_coordinator_id=None))


def test_the_status_rule_still_applies_to_the_assigned_coordinator():
    """Being assigned does not let someone review a draft."""
    with pytest.raises(EventRequestError) as caught:
        review_as(COORDINATOR, a_request(status="draft"))

    assert caught.value.status_code == 409
