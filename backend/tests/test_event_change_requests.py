"""API/service boundary tests for event change requests."""

from unittest.mock import patch

import pytest

from app import create_app
from app.services import event_change_request_service as service
from app.services import event_change_request_review_service as review_service
from app.services.event_change_request_service import EventChangeRequestError
from app.services.event_store import StoreError
from app.schemas import event_change_request_review as review_schema

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


def test_review_service_calls_atomic_decision_function():
    result = {"message": "Change request approved and event information updated."}
    with patch.object(service, "supabase_request", return_value=result) as query:
        assert review_service.decide(7, {"decision": "approve", "reason": ""}, "token") == result
    assert query.call_args.args[0] == "/rest/v1/rpc/review_event_change_request"
    assert query.call_args.kwargs["payload"] == {
        "p_request_id": 7, "p_decision": "approve", "p_reason": None,
    }


def test_change_request_error_serialises_every_optional_detail():
    error = EventChangeRequestError(
        "Stale request", status=409, errors={"reason": "Invalid"},
        critical_fields=["Expected attendance"], stale=True,
    )
    assert error.to_dict() == {
        "error": "Stale request", "errors": {"reason": "Invalid"},
        "critical_fields": ["Expected attendance"], "stale": True,
    }
    assert EventChangeRequestError("Plain error").to_dict() == {"error": "Plain error"}


def test_submission_service_lists_eligible_events_and_history():
    with patch.object(service, "supabase_request", side_effect=[
        {"events": [{"event_id": 4}]},
        {"change_requests": [{"event_change_request_id": 8, "status": "approved"}]},
        {"change_requests": [{"event_change_request_id": 7}]},
    ]) as query:
        assert service.list_eligible_events("token") == [{"event_id": 4}]
        assert service.list_my_change_requests("token") == [{"event_change_request_id": 8, "status": "approved"}]
        assert service.list_change_requests("4", "token") == [{"event_change_request_id": 7}]
    assert query.call_args_list[1].args[0] == "/rest/v1/rpc/event_change_requests_for_organiser"
    assert query.call_args_list[2].kwargs["payload"] == {"p_event_id": 4}


def test_submission_service_list_defaults_and_non_object_rpc_result():
    with patch.object(service, "supabase_request", side_effect=[{}, {}, {}, []]):
        assert service.list_eligible_events("token") == []
        assert service.list_my_change_requests("token") == []
        assert service.list_change_requests(4, "token") == []
        assert service.call_change_request_rpc("anything", "token", {}) == []


def test_submission_database_error_preserves_errors_and_stale_marker():
    with patch.object(service, "supabase_request", return_value={
        "error": "Event changed.", "errors": {"event": "Reload"}, "stale": True,
    }), pytest.raises(EventChangeRequestError) as caught:
        service.call_change_request_rpc("anything", "token", {})
    assert caught.value.status == 400
    assert caught.value.errors == {"event": "Reload"}
    assert caught.value.stale is True


@pytest.mark.parametrize("payload, field, message", [
    (None, "_body", "Provide a review decision."),
    ({"decision": "wait"}, "decision", "Choose Approve or Reject."),
    ({"decision": "approve", "reason": 4}, "reason", "The decision reason must be text."),
    ({"decision": "approve", "reason": "x" * 2001}, "reason", "The decision reason must be 2000 characters or fewer."),
    ({"decision": "reject", "reason": " "}, "reason", "Please provide a reason for rejecting this change request."),
])
def test_review_decision_rejects_each_invalid_shape(payload, field, message):
    parsed, errors = review_schema.parse_decision(payload)
    assert parsed == {}
    assert errors[field] == message


def test_review_decision_accepts_optional_approval_and_reasoned_rejection():
    assert review_schema.parse_decision({"decision": "approve"}) == (
        {"decision": "approve", "reason": None}, {},
    )
    assert review_schema.parse_decision({"decision": "reject", "reason": "  Not feasible  "}) == (
        {"decision": "reject", "reason": "Not feasible"}, {},
    )


def test_review_service_lists_filters_and_loads_details():
    with patch.object(service, "supabase_request", side_effect=[
        {"change_requests": [{"event_change_request_id": 7}]},
        {},
        {"change_request": {"event_change_request_id": 7}},
    ]) as query:
        assert review_service.list_for_coordinator("token", status="pending_review") == [{"event_change_request_id": 7}]
        assert review_service.list_for_coordinator("token") == []
        assert review_service.get_for_review("7", "token")["change_request"]["event_change_request_id"] == 7
    assert query.call_args_list[0].kwargs["payload"] == {"p_status": "pending_review"}
    assert query.call_args_list[2].kwargs["payload"] == {"p_request_id": 7}


def test_review_service_rejects_invalid_filter_and_decision_before_database():
    with patch.object(service, "supabase_request") as query:
        with pytest.raises(EventChangeRequestError) as status_error:
            review_service.list_for_coordinator("token", status="unknown")
        with pytest.raises(EventChangeRequestError) as decision_error:
            review_service.decide(7, {"decision": "reject", "reason": ""}, "token")
    assert status_error.value.errors == {"status": "Invalid status."}
    assert "reason" in decision_error.value.errors
    query.assert_not_called()


def test_review_database_error_preserves_details_and_default_status():
    with patch.object(service, "supabase_request", return_value={
        "error": "Stale request", "errors": {"event": "Reload"}, "stale": True,
    }), pytest.raises(EventChangeRequestError) as caught:
        review_service.get_for_review(7, "token")
    assert caught.value.status == 400
    assert caught.value.errors == {"event": "Reload"}
    assert caught.value.stale is True


@pytest.mark.parametrize("route, expected", [
    ("/api/event-change-requests/eligible-events", {"events": [{"event_id": 4}]}),
    ("/api/event-change-requests/mine", {"change_requests": [{"event_change_request_id": 8}]}),
    ("/api/events/4/change-requests", {"change_requests": [{"event_change_request_id": 7}]}),
])
def test_submission_get_routes_return_service_results(route, expected):
    service_name = "list_eligible_events" if "eligible-events" in route else "list_my_change_requests" if route.endswith("/mine") else "list_change_requests"
    returned = next(iter(expected.values()))
    with patch("app.routes.event_change_requests.supabase_request", return_value={"id": "user-id"}), \
         patch(f"app.routes.event_change_requests.{service_name}", return_value=returned):
        response = create_app().test_client().get(route, headers=HEADERS)
    assert response.status_code == 200
    assert response.json == expected
    assert response.headers["Cache-Control"] == "no-store"


def test_submission_post_route_returns_created_result():
    result = {"message": "Submitted", "change_request": {"event_change_request_id": 7}}
    with patch("app.routes.event_change_requests.supabase_request", return_value={"id": "user-id"}), \
         patch("app.routes.event_change_requests.submit_change_request", return_value=result):
        response = create_app().test_client().post(
            "/api/events/4/change-requests", headers=HEADERS, json=VALID_BODY,
        )
    assert response.status_code == 201
    assert response.json == result


@pytest.mark.parametrize("status, expected_message", [
    (401, "Please sign in again."),
    (503, "Event change requests are temporarily unavailable."),
])
def test_submission_routes_translate_store_errors(status, expected_message):
    with patch("app.routes.event_change_requests.supabase_request", side_effect=StoreError(status)):
        response = create_app().test_client().get(
            "/api/event-change-requests/eligible-events", headers=HEADERS,
        )
    assert response.status_code == status
    assert response.json == {"error": expected_message}


def test_submission_route_serialises_application_error():
    error = EventChangeRequestError("Cannot submit", status=409, stale=True)
    with patch("app.routes.event_change_requests.supabase_request", return_value={"id": "user-id"}), \
         patch("app.routes.event_change_requests.submit_change_request", side_effect=error):
        response = create_app().test_client().post(
            "/api/events/4/change-requests", headers=HEADERS, json=VALID_BODY,
        )
    assert response.status_code == 409
    assert response.json == {"error": "Cannot submit", "stale": True}


def test_review_routes_return_queue_detail_and_decision():
    auth = patch("app.routes.event_change_request_reviews.supabase_request", return_value={"id": "coordinator-id"})
    with auth, \
         patch("app.routes.event_change_request_reviews.list_for_coordinator", return_value=[{"event_change_request_id": 7}]) as listing, \
         patch("app.routes.event_change_request_reviews.get_for_review", return_value={"change_request": {"event_change_request_id": 7}}), \
         patch("app.routes.event_change_request_reviews.decide", return_value={"message": "Approved"}):
        client = create_app().test_client()
        queue = client.get("/api/event-change-requests?status=pending_review", headers=HEADERS)
        detail = client.get("/api/event-change-requests/7", headers=HEADERS)
        decision = client.post("/api/event-change-requests/7/decision", headers=HEADERS, json={"decision": "approve"})
    assert queue.json == {"change_requests": [{"event_change_request_id": 7}]}
    listing.assert_called_once_with("organiser-token", status="pending_review")
    assert detail.json["change_request"]["event_change_request_id"] == 7
    assert decision.json == {"message": "Approved"}
    assert all(response.headers["Cache-Control"] == "no-store" for response in (queue, detail, decision))


@pytest.mark.parametrize("status, expected_message", [
    (401, "Please sign in again."),
    (503, "Event change requests are temporarily unavailable."),
])
def test_review_routes_translate_store_errors(status, expected_message):
    with patch("app.routes.event_change_request_reviews.supabase_request", side_effect=StoreError(status)):
        response = create_app().test_client().get("/api/event-change-requests", headers=HEADERS)
    assert response.status_code == status
    assert response.json == {"error": expected_message}


def test_review_route_serialises_application_error():
    error = EventChangeRequestError("Cannot review", status=409, errors={"decision": "Already decided"})
    with patch("app.routes.event_change_request_reviews.supabase_request", return_value={"id": "coordinator-id"}), \
         patch("app.routes.event_change_request_reviews.list_for_coordinator", side_effect=error):
        response = create_app().test_client().get("/api/event-change-requests", headers=HEADERS)
    assert response.status_code == 409
    assert response.json == {"error": "Cannot review", "errors": {"decision": "Already decided"}}

