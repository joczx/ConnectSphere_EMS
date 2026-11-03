"""SCRUM-13: real equipment requests by the assigned Event Coordinator.

AC1/2/3: one event, equipment type, quantity and technical requirements per
request. AC4: confirmation/error responses (browser rendering is separate).
AC5: assignment and authentication. Admin access only arranges/verifies data
and cleans fixtures; all equipment submissions use real user tokens.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.supabase_admin import admin_request, delete_as_user, user_id_for


@pytest.fixture(scope="module")
def equipment_event(client, sign_in):
    marker = f"ITEST-SCRUM-13-{uuid.uuid4().hex[:12]}"
    starts = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=60)
    headers = sign_in("Event Coordinator")
    items = []
    try:
        created = client.post("/api/event-requests", headers=sign_in("Event Organiser"), json={
            "event_name": marker, "purpose": "Equipment integration test", "description": marker,
            "event_organiser_id": user_id_for("Event Organiser"),
            "start_datetime": starts.isoformat(), "end_datetime": (starts + timedelta(hours=2)).isoformat(),
            "capacity_needed": 40, "room_layout": "theatre", "required_facilities": [],
            "equipment_requirements": [],
        })
        assert created.status_code == 201, created.get_json()
        request_id = created.get_json()["event_request"]["event_request_id"]
        admin_request(f"/rest/v1/event_request?event_request_id=eq.{request_id}",
                      {"event_coordinator_id": user_id_for("Event Coordinator")}, "PATCH")
        approved = client.post(f"/api/event-requests/{request_id}/review", headers=headers,
                               json={"outcome": "approved"})
        assert approved.status_code == 200, approved.get_json()
        event, = admin_request(f"/rest/v1/events?event_request_id=eq.{request_id}")
        for label in ("Projector", "Camera", "Microphone"):
            item, = admin_request("/rest/v1/equipment", {
                "equipment_type": f"{marker}-{label}", "equipment_model": "Test", "total_quantity": 10})
            items.append(item)
        yield event, items, headers
    finally:
        for request in admin_request(f"/rest/v1/event_request?event_name=eq.{marker}"):
            for event in admin_request(f"/rest/v1/events?event_request_id=eq.{request['event_request_id']}"):
                # The review trigger skips secret-key DELETE; use the requester.
                delete_as_user(f"/rest/v1/equipment_request?event_id=eq.{event['event_id']}", headers)
                assert _rows(event["event_id"]) == [], "Equipment test cleanup did not remove all requests"
                admin_request(f"/rest/v1/events?event_id=eq.{event['event_id']}", method="DELETE")
            admin_request(f"/rest/v1/event_request?event_request_id=eq.{request['event_request_id']}", method="DELETE")
        for item in items:
            admin_request(f"/rest/v1/equipment?equipment_id=eq.{item['equipment_id']}", method="DELETE")


def _rows(event_id):
    return admin_request(f"/rest/v1/equipment_request?event_id=eq.{event_id}&order=equipment_request_id.asc")


# TC-REQ-IT-001 (AC1,2,3,4): real inserts preserve one scalar type and details.
@pytest.mark.parametrize("item_index", [0, 1, 2], ids=["projector", "camera", "microphone"])
def test_assigned_coordinator_submits_one_equipment_type(client, equipment_event, item_index):
    event, items, headers = equipment_event
    equipment_type = items[item_index]["equipment_type"]
    response = client.post(f"/api/events/{event['event_id']}/equipment-requests", headers=headers,
                           json={"equipment_type": equipment_type, "quantity": 2,
                                 "technical_requirements": "  HDMI connection and spare batteries  "})
    assert response.status_code == 201, response.get_json()
    body = response.get_json()
    assert body["message"] == "Equipment request submitted successfully."
    returned = body["equipment_request"]
    stored, = [row for row in _rows(event["event_id"])
               if row["equipment_request_id"] == returned["equipment_request_id"]]
    assert stored["event_id"] == event["event_id"]
    assert stored["requested_by"] == event["event_coordinator_id"]
    assert stored["equipment_type"] == equipment_type
    assert stored["quantity"] == 2 and stored["status"] == "pending"
    assert stored["technical_requirements"] == "HDMI connection and spare batteries"
    listed = client.get(f"/api/events/{event['event_id']}/equipment-requests", headers=headers)
    assert listed.status_code == 200, listed.get_json()
    assert stored in listed.get_json()["equipment_requests"]


# TC-REQ-IT-002 (AC2): technical notes are optional.
def test_request_without_technical_notes_succeeds(client, equipment_event):
    event, items, headers = equipment_event
    response = client.post(f"/api/events/{event['event_id']}/equipment-requests", headers=headers,
                           json={"equipment_type": items[0]["equipment_type"], "quantity": 1})
    assert response.status_code == 201, response.get_json()
    request_id = response.get_json()["equipment_request"]["equipment_request_id"]
    row, = [row for row in _rows(event["event_id"]) if row["equipment_request_id"] == request_id]
    assert row["technical_requirements"] is None


# TC-REQ-IT-003 (AC2,3,4): invalid input produces an error and no new request.
@pytest.mark.parametrize("changes,field", [
    ({"equipment_type": ""}, "equipment_type"),
    ({"equipment_type": None}, "equipment_type"),
    ({"equipment_type": ["Projector", "Camera"]}, "equipment_type"),
    ({"quantity": 0}, "quantity"),
    ({"quantity": -1}, "quantity"),
    ({"quantity": 1.5}, "quantity"),
    ({"quantity": "2"}, "quantity"),
    ({"quantity": True}, "quantity"),
    ({"quantity": None}, "quantity"),
    ({"technical_requirements": ["HDMI"]}, "technical_requirements"),
])
def test_invalid_equipment_request_does_not_persist(client, equipment_event, changes, field):
    event, items, headers = equipment_event
    before = _rows(event["event_id"])
    response = client.post(f"/api/events/{event['event_id']}/equipment-requests", headers=headers,
                           json={"equipment_type": items[0]["equipment_type"], "quantity": 1, **changes})
    assert response.status_code == 400, response.get_json()
    assert response.get_json()["error"] and field in response.get_json()["errors"]
    assert "message" not in response.get_json() and "equipment_request" not in response.get_json()
    assert _rows(event["event_id"]) == before


# TC-REQ-IT-004 (AC5): event access alone does not permit equipment requests.
@pytest.mark.parametrize("role", ["Event Organiser", "Technical Support Staff", "Event Coordinator Lead"])
def test_other_roles_cannot_create_equipment_requests(client, sign_in, equipment_event, role):
    event, items, _ = equipment_event
    before = _rows(event["event_id"])
    response = client.post(f"/api/events/{event['event_id']}/equipment-requests", headers=sign_in(role),
                           json={"equipment_type": items[0]["equipment_type"], "quantity": 1})
    # RLS may conceal the event entirely; otherwise the service refuses assignment.
    assert response.status_code in (403, 404), response.get_json()
    assert response.get_json()["error"] and "message" not in response.get_json()
    assert _rows(event["event_id"]) == before


# TC-REQ-IT-005 (AC5): an actual coordinator without this assignment is refused.
def test_unassigned_coordinator_cannot_request_equipment(client, equipment_event):
    event, items, headers = equipment_event
    event_id = event["event_id"]
    before = _rows(event_id)
    try:
        admin_request(f"/rest/v1/events?event_id=eq.{event_id}",
                      {"event_coordinator_id": user_id_for("Event Coordinator Lead")}, "PATCH")
        response = client.post(f"/api/events/{event_id}/equipment-requests", headers=headers,
                               json={"equipment_type": items[0]["equipment_type"], "quantity": 1})
        assert response.status_code in (403, 404), response.get_json()
        assert response.get_json()["error"] and "message" not in response.get_json()
        assert _rows(event_id) == before
    finally:
        admin_request(f"/rest/v1/events?event_id=eq.{event_id}",
                      {"event_coordinator_id": event["event_coordinator_id"]}, "PATCH")


# TC-REQ-IT-006 (AC5): authentication is required before any insert.
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}],
                         ids=["missing-token", "invalid-token"])
def test_unauthenticated_submission_is_refused(client, equipment_event, headers):
    event, items, _ = equipment_event
    before = _rows(event["event_id"])
    response = client.post(f"/api/events/{event['event_id']}/equipment-requests", headers=headers,
                           json={"equipment_type": items[0]["equipment_type"], "quantity": 1})
    assert response.status_code == 401, response.get_json()
    assert response.get_json()["error"] and "equipment_request" not in response.get_json()
    assert _rows(event["event_id"]) == before
