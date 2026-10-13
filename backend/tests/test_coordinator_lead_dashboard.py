from unittest.mock import patch

import pytest

from app import create_app
from app.services.event_store import StoreError


EVENT_ID = 42
COORDINATOR_ID = "9c2d7e15-4b93-4a06-8f21-6e0b3d9a7c54"


@pytest.fixture
def client():
    return create_app().test_client()


@patch("app.routes.coordinator_lead.authenticated_token", return_value="verified-token")
@patch("app.routes.coordinator_lead.supabase_request")
def test_lead_dashboard_returns_grouped_items_and_coordinators(
    query, _authenticated_token, client
):
    expected = {
        "items": [{"item_type": "event", "status": "planning"}],
        "coordinators": [{"id": COORDINATOR_ID, "name": "Coordinator"}],
    }
    query.return_value = expected

    response = client.get("/api/coordinator-lead/dashboard")

    assert response.status_code == 200
    assert response.json == expected
    assert query.call_args.args[0] == (
        "/rest/v1/rpc/event_coordinator_lead_dashboard"
    )
    assert query.call_args.kwargs["token"] == "verified-token"
    assert response.headers["Cache-Control"] == "no-store"


@patch("app.routes.coordinator_lead.authenticated_token", return_value="verified-token")
@patch("app.routes.coordinator_lead.supabase_request")
def test_non_lead_cannot_load_dashboard(query, _authenticated_token, client):
    query.return_value = {
        "error": "Only Event Coordinator Leads can view this dashboard.",
        "status": 403,
    }

    response = client.get("/api/coordinator-lead/dashboard")

    assert response.status_code == 403
    assert "Only Event Coordinator Leads" in response.json["error"]


@patch("app.routes.coordinator_lead.supabase_request")
def test_dashboard_requires_authentication(query, client):
    response = client.get("/api/coordinator-lead/dashboard")

    assert response.status_code == 401
    query.assert_not_called()


@patch("app.routes.coordinator_lead.authenticated_token", return_value="verified-token")
@patch("app.routes.coordinator_lead.supabase_request")
def test_lead_can_reassign_submitted_request(
    query, _authenticated_token, client
):
    query.return_value = {
        "message": "Event Coordinator reassigned successfully.",
        "event_request": {"event_request_id": 17},
    }

    response = client.patch(
        "/api/coordinator-lead/event-requests/17/coordinator",
        json={"coordinator_id": COORDINATOR_ID},
    )

    assert response.status_code == 200
    assert response.json["message"] == "Event Coordinator reassigned successfully."
    assert query.call_args.kwargs["payload"] == {
        "p_event_request_id": 17,
        "p_coordinator_id": COORDINATOR_ID,
    }


@patch("app.routes.coordinator_lead.authenticated_token", return_value="verified-token")
@patch("app.routes.coordinator_lead.supabase_request")
def test_lead_can_reassign_an_event(query, _authenticated_token, client):
    query.return_value = {
        "message": "Event Coordinator reassigned successfully.",
        "event": {"event_id": EVENT_ID, "event_coordinator_id": COORDINATOR_ID},
    }

    response = client.patch(
        f"/api/coordinator-lead/events/{EVENT_ID}/coordinator",
        json={"coordinator_id": COORDINATOR_ID},
    )

    assert response.status_code == 200
    assert response.json["event"]["event_id"] == EVENT_ID
    assert query.call_args.kwargs["payload"] == {
        "p_event_id": EVENT_ID,
        "p_coordinator_id": COORDINATOR_ID,
    }


@patch("app.routes.coordinator_lead.authenticated_token", return_value="verified-token")
@patch("app.routes.coordinator_lead.supabase_request")
def test_invalid_event_or_coordinator_id_does_not_call_reassignment_rpc(
    query, _authenticated_token, client
):
    invalid_event = client.patch(
        "/api/coordinator-lead/events/not-an-integer/coordinator",
        json={"coordinator_id": COORDINATOR_ID},
    )
    invalid_coordinator = client.patch(
        f"/api/coordinator-lead/events/{EVENT_ID}/coordinator",
        json={"coordinator_id": "not-a-uuid"},
    )

    assert invalid_event.status_code == 404
    assert invalid_coordinator.status_code == 400
    query.assert_not_called()


@patch("app.routes.coordinator_lead.authenticated_token", return_value="verified-token")
@patch("app.routes.coordinator_lead.supabase_request")
def test_rpc_role_denial_is_not_reported_as_success(
    query, _authenticated_token, client
):
    query.return_value = {
        "error": "Only Event Coordinator Leads can reassign events.",
        "status": 403,
    }

    response = client.patch(
        f"/api/coordinator-lead/events/{EVENT_ID}/coordinator",
        json={"coordinator_id": COORDINATOR_ID},
    )

    assert response.status_code == 403
    assert response.json == {
        "error": "Only Event Coordinator Leads can reassign events."
    }


@patch("app.routes.coordinator_lead.authenticated_token", return_value="verified-token")
@patch(
    "app.routes.coordinator_lead.supabase_request",
    side_effect=StoreError(503, "Event service is temporarily unavailable."),
)
def test_dashboard_upstream_failure_is_reported(
    _query, _authenticated_token, client
):
    response = client.get("/api/coordinator-lead/dashboard")

    assert response.status_code == 503
    assert response.json == {"error": "Event service is temporarily unavailable."}


@patch("app.routes.coordinator_lead.authenticated_token", return_value="verified-token")
@patch(
    "app.routes.coordinator_lead.supabase_request",
    side_effect=StoreError(503, code="PGRST202"),
)
def test_missing_dashboard_rpc_returns_migration_guidance(
    _query, _authenticated_token, client
):
    response = client.get("/api/coordinator-lead/dashboard")

    assert response.status_code == 503
    assert "030_coordinator_lead_dashboard.sql" in response.json["error"]
    assert "schema cache" in response.json["error"]
