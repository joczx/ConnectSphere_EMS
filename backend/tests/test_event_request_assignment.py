from unittest.mock import patch

import pytest

from app import create_app
from app.services.event_store import StoreError


COORDINATOR_ID = "9c2d7e15-4b93-4a06-8f21-6e0b3d9a7c54"


@pytest.fixture
def client():
    return create_app().test_client()


@patch("app.routes.event_requests.authenticated_token", return_value="verified-token")
@patch("app.routes.event_requests.supabase_request")
def test_lead_can_load_unassigned_queue(query, _authenticated_token, client):
    queue = {"event_requests": [{"event_request_id": 12}], "coordinators": [{"id": COORDINATOR_ID}]}
    query.return_value = queue

    response = client.get("/api/event-requests/unassigned")

    assert response.status_code == 200
    assert response.json == queue
    assert query.call_args.args[0] == "/rest/v1/rpc/event_request_assignment_queue"
    assert query.call_args.kwargs["token"] == "verified-token"
    assert query.call_args.kwargs["method"] == "POST"
    assert response.headers["Cache-Control"] == "no-store"


@patch("app.routes.event_requests.authenticated_token", return_value="verified-token")
@patch("app.routes.event_requests.supabase_request")
def test_non_lead_cannot_load_unassigned_queue(query, _authenticated_token, client):
    query.return_value = {
        "error": "Only Event Coordinator Leads can view unassigned event requests.",
        "status": 403,
    }

    response = client.get("/api/event-requests/unassigned")

    assert response.status_code == 403
    assert response.json["error"].startswith("Only Event Coordinator Leads")


@patch("app.routes.event_requests.supabase_request")
def test_unassigned_queue_requires_authentication(query, client):
    response = client.get("/api/event-requests/unassigned")

    assert response.status_code == 401
    query.assert_not_called()


@patch("app.routes.event_requests.authenticated_token", return_value="verified-token")
@patch(
    "app.routes.event_requests.supabase_request",
    side_effect=StoreError(503, code="PGRST202"),
)
def test_missing_assignment_rpc_returns_migration_guidance(
    _query, _authenticated_token, client
):
    response = client.get("/api/event-requests/unassigned")

    assert response.status_code == 503
    assert "029_event_coordinator_assignment.sql" in response.json["error"]
    assert "schema cache" in response.json["error"]


@patch("app.routes.event_requests.authenticated_token", return_value="verified-token")
@patch("app.routes.event_requests.supabase_request")
def test_lead_assignment_returns_confirmation_and_event_request(
    query, _authenticated_token, client
):
    expected = {
        "message": "Event Coordinator assigned successfully.",
        "event_request": {"event_request_id": 12, "event_coordinator_id": COORDINATOR_ID},
    }
    query.return_value = expected

    response = client.post(
        "/api/event-requests/12/assign-coordinator",
        json={"coordinator_id": COORDINATOR_ID},
    )

    assert response.status_code == 200
    assert response.json == expected
    assert query.call_args.kwargs["payload"] == {
        "p_event_request_id": 12,
        "p_coordinator_id": COORDINATOR_ID,
    }


@patch("app.routes.event_requests.authenticated_token", return_value="verified-token")
@patch("app.routes.event_requests.supabase_request")
def test_invalid_coordinator_id_is_rejected_without_database_call(
    query, _authenticated_token, client
):
    response = client.post(
        "/api/event-requests/12/assign-coordinator",
        json={"coordinator_id": "not-a-uuid"},
    )

    assert response.status_code == 400
    query.assert_not_called()


@patch("app.routes.event_requests.authenticated_token", return_value="verified-token")
@patch("app.routes.event_requests.supabase_request")
def test_assignment_role_denial_is_not_reported_as_success(
    query, _authenticated_token, client
):
    query.return_value = {
        "error": "Only Event Coordinator Leads can assign event coordinators.",
        "status": 403,
    }

    response = client.post(
        "/api/event-requests/12/assign-coordinator",
        json={"coordinator_id": COORDINATOR_ID},
    )

    assert response.status_code == 403
    assert response.json == {
        "error": "Only Event Coordinator Leads can assign event coordinators."
    }


@patch("app.routes.event_requests.authenticated_token", return_value="verified-token")
@patch("app.routes.event_requests.supabase_request")
def test_request_already_assigned_is_reported_as_conflict(
    query, _authenticated_token, client
):
    query.return_value = {
        "error": "This request is no longer available for assignment. Refresh the queue.",
        "status": 409,
    }

    response = client.post(
        "/api/event-requests/12/assign-coordinator",
        json={"coordinator_id": COORDINATOR_ID},
    )

    assert response.status_code == 409
