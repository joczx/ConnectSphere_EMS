"""Unit tests for two people editing the same event at once.

An edit is written with compare-and-swap on updated_at, so the second of two
concurrent saves is refused rather than silently overwriting the first. Without
it the loser's change is lost and their history entry records a before value
that had already moved.

These tests stub the Supabase call rather than reaching it.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.services import event_service as service
from app.services.event_service import EventError

FUTURE = datetime.now(timezone.utc) + timedelta(days=30)
LOADED_AT = "2026-10-06T07:00:00+00:00"
SAVED_SINCE = "2026-10-06T07:05:00+00:00"


def an_event(**overrides):
    event = {
        "event_id": 6,
        "event_name": "Halloween",
        "purpose": "Student social",
        "description": "An evening event.",
        "start_datetime": FUTURE.isoformat(),
        "end_datetime": (FUTURE + timedelta(hours=3)).isoformat(),
        "capacity_needed": 120,
        "status": "planning",
        "updated_at": LOADED_AT,
    }
    event.update(overrides)
    return event


def save(expected, *, rows_written, current=None):
    """Run an edit. `rows_written` is what the conditional PATCH returns."""
    stored = an_event()
    calls = []

    def fake_request(path, token=None, payload=None, method="GET"):
        calls.append(path)
        if method == "PATCH":
            return rows_written
        if "event_activity" in path:
            return [{"activity_id": 1}]
        if path.startswith("/auth/v1/user"):
            return {"id": "44bc334e-0000-0000-0000-000000000000"}
        # Re-read after a failed write, or the initial load.
        return [current if current is not None and calls.count(path) > 1 else stored]

    with patch.object(service, "supabase_request", side_effect=fake_request):
        return service.update_event(
            6, {"purpose": "Updated"}, "token", expected_updated_at=expected
        )


def test_an_edit_on_the_current_version_is_written():
    row, activity = save(LOADED_AT, rows_written=[an_event(purpose="Updated")])

    assert row["purpose"] == "Updated"
    assert activity is not None


def test_an_edit_on_a_stale_version_is_refused():
    """The other person's save must not be silently overwritten."""
    with pytest.raises(EventError) as caught:
        save(LOADED_AT, rows_written=[], current=an_event(updated_at=SAVED_SINCE))

    assert caught.value.status == 409
    assert caught.value.stale is True
    assert "Someone else saved changes" in caught.value.message


def test_a_stale_conflict_is_distinguishable_from_a_refusal():
    """Both are 409 or 403; the client answers them differently."""
    with pytest.raises(EventError) as caught:
        save(LOADED_AT, rows_written=[], current=an_event(updated_at=SAVED_SINCE))

    assert caught.value.to_dict()["stale"] is True


def test_nothing_written_and_nothing_moved_is_a_permission_problem():
    """Zero rows with an unchanged version means the write was not allowed."""
    with pytest.raises(EventError) as caught:
        save(LOADED_AT, rows_written=[], current=an_event())

    assert caught.value.status == 403
    assert caught.value.stale is False


def test_the_write_moves_updated_at():
    """Compare-and-swap needs a value that changes on every write."""
    written = {}

    def fake_request(path, token=None, payload=None, method="GET"):
        if method == "PATCH":
            written.update(payload)
            return [an_event(**payload)]
        if "event_activity" in path:
            return [{"activity_id": 1}]
        if path.startswith("/auth/v1/user"):
            return {"id": "44bc334e-0000-0000-0000-000000000000"}
        return [an_event()]

    with patch.object(service, "supabase_request", side_effect=fake_request):
        service.update_event(6, {"purpose": "Updated"}, "token",
                             expected_updated_at=LOADED_AT)

    assert written["updated_at"] != LOADED_AT
