"""API/service boundary tests for event change requests."""

from unittest.mock import patch

import pytest

from app import create_app
from app.services import event_change_request_service as service
from app.services.event_change_request_service import EventChangeRequestError

HEADERS = {"Authorization": "Bearer organiser-token"}
VALID_BODY = {
    "reason": "More guests are attending.",
    "proposed_values": {"capacity_needed": 200},
    "expected_event_updated_at": "2030-01-01T00:00:00+00:00",
}


def test_submission_calls_the_atomic_database_function():
    response = {
        "message": "Event change request submitted successfully.",
        "change_request": {"event_change_request_id": 7, "status": "pending_review"},
    }
    with patch.object(service, "supabase_request", return_value=response) as query:
        assert service.submit_change_request(4, VALID_BODY, "token") == response
    assert query.call_args.args[0] == "/rest/v1/rpc/submit_event_change_request"
    assert query.call_args.kwargs["payload"]["p_event_id"] == 4
    assert query.call_args.kwargs["payload"]["p_confirm_critical"] is False


def test_database_critical_warning_is_preserved_for_the_modal():
    with patch.object(service, "supabase_request", return_value={
        "error": "Confirm critical changes.", "status": 409,
        "critical_fields": ["Expected attendance"],
    }), pytest.raises(EventChangeRequestError) as caught:
        service.submit_change_request(4, VALID_BODY, "token")
    assert caught.value.status == 409
    assert caught.value.critical_fields == ["Expected attendance"]


def test_invalid_body_never_calls_the_database():
    with patch.object(service, "supabase_request") as query, pytest.raises(EventChangeRequestError) as caught:
        service.submit_change_request(4, {**VALID_BODY, "reason": " "}, "token")
    assert caught.value.errors["reason"] == "Please provide a reason for this change request"
    query.assert_not_called()


def test_submission_endpoint_requires_authentication():
    response = create_app().test_client().post(
        "/api/events/4/change-requests", json=VALID_BODY
    )
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"


def test_organiser_cannot_bypass_requests_with_direct_event_edit():
    stored = {
        "event_id": 4,
        "event_organiser_id": "organiser-id",
        "status": "planning",
        "updated_at": "2030-01-01T00:00:00+00:00",
    }
    with patch("app.routes.events.supabase_request", return_value={"id": "organiser-id"}) as auth_query, \
         patch("app.services.event_service.supabase_request", return_value=[stored]) as event_query:
        response = create_app().test_client().patch(
            "/api/events/4",
            headers=HEADERS,
            json={"capacity_needed": 200},
        )
    assert response.status_code == 403
    assert "change request" in response.json["error"]
    auth_query.assert_called_once()
    event_query.assert_called_once()

