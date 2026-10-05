"""Shared event request lifecycle schema checks.

Story-specific tests live in test_create_submit_event_request.py and
 test_draft_event_requests.py.
"""
from app.schemas import event_request as schema


def test_every_status_the_database_accepts_is_known_to_the_code():
    assert schema.STATUS_DRAFT in schema.ALL_STATUSES
    assert schema.STATUS_SUBMITTED in schema.ALL_STATUSES
    assert schema.ALL_STATUSES == {
        "draft",
        "submitted",
        "planning",
        "rejected",
        "confirmed",
        "completed",
        "cancelled",
    }
