"""SCRUM-10: real planning-event reads, latest values and row-level access.

Requests are submitted and approved through authenticated APIs. Admin access
only assigns fixtures, verifies persistence and cleans up. All reads under test
use user tokens. API coverage does not verify browser rendering.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.supabase_admin import admin_request, user_id_for


@pytest.fixture
def planning_event(client, sign_in):
    marker = f"ITEST-SCRUM-10-{uuid.uuid4().hex}"
    starts = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=60)
    payload = {
        "event_name": marker, "purpose": "Planning integration test", "description": marker,
        "event_organiser_id": user_id_for("Event Organiser"),
        "start_datetime": starts.isoformat(),
        "end_datetime": (starts + timedelta(hours=2)).isoformat(),
        "capacity_needed": 40, "room_layout": "theatre",
        "required_facilities": ["projector", "wifi"],
        "equipment_requirements": [
            {"equipment_type": "microphone", "quantity": 2, "notes": "Wireless"}],
        "need_wheelchair_accessibility": True, "need_blind_accessibility": False,
    }
    try:
        created = client.post("/api/event-requests", headers=sign_in("Event Organiser"), json=payload)
        assert created.status_code == 201, created.get_json()
        request_id = created.get_json()["event_request"]["event_request_id"]
        admin_request(f"/rest/v1/event_request?event_request_id=eq.{request_id}",
                      {"event_coordinator_id": user_id_for("Event Coordinator")}, "PATCH")
        approved = client.post(f"/api/event-requests/{request_id}/review",
                               headers=sign_in("Event Coordinator"), json={"outcome": "approved"})
        assert approved.status_code == 200, approved.get_json()
        event, = admin_request(f"/rest/v1/events?event_request_id=eq.{request_id}")
        assert event["status"] == "planning"
        yield event, payload
    finally:
        for row in admin_request(f"/rest/v1/event_request?event_name=eq.{marker}"):
            request_id = row["event_request_id"]
            admin_request(f"/rest/v1/events?event_request_id=eq.{request_id}", method="DELETE")
            admin_request(f"/rest/v1/event_request?event_request_id=eq.{request_id}", method="DELETE")


def _read(client, sign_in, event_id, role):
    response = client.get(f"/api/events/{event_id}", headers=sign_in(role))
    assert response.status_code == 200, response.get_json()
    assert response.headers["Cache-Control"] == "no-store"
    return response.get_json()["event"]


# TC-VEI-IT-001/002/003 (AC1,2): both authorised roles see every recorded detail.
@pytest.mark.parametrize("role", ["Event Organiser", "Event Coordinator"])
def test_authorised_users_see_complete_event_information(client, sign_in, planning_event, role):
    event, payload = planning_event
    shown = _read(client, sign_in, event["event_id"], role)
    assert shown["event_id"] == event["event_id"] and shown["status"] == "planning"
    for field, expected in payload.items():
        if field.endswith("_datetime"):
            assert datetime.fromisoformat(shown[field].replace("Z", "+00:00")) == datetime.fromisoformat(expected)
        else:
            assert shown[field] == expected, field
    listed = client.get("/api/events", headers=sign_in(role))
    assert listed.status_code == 200, listed.get_json()
    assert event["event_id"] in {row["event_id"] for row in listed.get_json()["events"]}


# TC-VEI-IT-004 (AC2,3): explicitly recorded 'none' values are returned accurately.
def test_no_equipment_is_shown_accurately(client, sign_in, planning_event):
    event, _ = planning_event
    updated = client.patch(f"/api/events/{event['event_id']}", headers=sign_in("Event Coordinator"),
                           json={"equipment_requirements": [],
                                 "confirm_critical": True, "expected_updated_at": event["updated_at"]})
    assert updated.status_code == 200, updated.get_json()
    shown = _read(client, sign_in, event["event_id"], "Event Organiser")
    assert shown["equipment_requirements"] == []
    assert shown["event_name"] == event["event_name"]


# TC-VEI-IT-005 (AC3): reads after an authorised edit return the persisted version.
def test_both_roles_see_latest_coordinator_update(client, sign_in, planning_event):
    event, _ = planning_event
    original = _read(client, sign_in, event["event_id"], "Event Organiser")
    changes = {"purpose": "Updated planning purpose", "description": "Latest approved details"}
    response = client.patch(f"/api/events/{event['event_id']}", headers=sign_in("Event Coordinator"),
                            json={**changes, "expected_updated_at": original["updated_at"]})
    assert response.status_code == 200, response.get_json()
    stored, = admin_request(f"/rest/v1/events?event_id=eq.{event['event_id']}")
    for role in ("Event Organiser", "Event Coordinator"):
        shown = _read(client, sign_in, event["event_id"], role)
        assert shown["updated_at"] == stored["updated_at"] != original["updated_at"]
        assert all(shown[field] == stored[field] == value for field, value in changes.items())


# TC-VEI-IT-006 (AC3): pending proposals do not replace approved information.
def test_pending_change_is_visible_only_after_approval(client, sign_in, planning_event):
    event, _ = planning_event
    # Non-critical changes apply immediately. Attendance requires review.
    proposed = {"capacity_needed": 80}
    created = client.post(f"/api/events/{event['event_id']}/change-requests",
                          headers=sign_in("Event Organiser"), json={
                              "reason": "Update planning information", "proposed_values": proposed,
                              "expected_event_updated_at": event["updated_at"]})
    assert created.status_code == 201, created.get_json()
    change_id = created.get_json()["change_request"]["event_change_request_id"]
    for role in ("Event Organiser", "Event Coordinator"):
        assert _read(client, sign_in, event["event_id"], role)["capacity_needed"] == event["capacity_needed"]
    approved = client.post(f"/api/event-change-requests/{change_id}/decision",
                           headers=sign_in("Event Coordinator"), json={"decision": "approve"})
    assert approved.status_code == 200, approved.get_json()
    for role in ("Event Organiser", "Event Coordinator"):
        shown = _read(client, sign_in, event["event_id"], role)
        assert shown["capacity_needed"] == proposed["capacity_needed"]
        assert shown["event_id"] == event["event_id"]


# TC-VEI-IT-007/008/011 (AC4): remove the caller's relationship to this fixture.
# Other user's ID is arrangement only; the read still uses the original token.
@pytest.mark.parametrize("role,column", [
    ("Event Organiser", "event_organiser_id"),
    ("Event Coordinator", "event_coordinator_id"),
])
def test_unrelated_user_cannot_read_or_list_event(client, sign_in, planning_event, role, column):
    event, _ = planning_event
    other = user_id_for("Event Coordinator Lead")
    # Clear every staff relationship too: the accounts may hold multiple roles.
    admin_request(f"/rest/v1/events?event_id=eq.{event['event_id']}",
                  {column: other, "venue_staff_id": None, "technical_support_id": None,
                   "safety_officer_id": None}, "PATCH")
    stored, = admin_request(f"/rest/v1/events?event_id=eq.{event['event_id']}")
    assert stored[column] == other
    caller = user_id_for(role)
    assert caller not in [stored.get(key) for key in (
        "event_organiser_id", "event_coordinator_id", "venue_staff_id",
        "technical_support_id", "safety_officer_id")]
    response = client.get(f"/api/events/{event['event_id']}", headers=sign_in(role))
    assert response.status_code == 404, response.get_json()
    assert response.get_json() == {"error": "Event not found or access unavailable."}
    listed = client.get("/api/events", headers=sign_in(role))
    assert listed.status_code == 200, listed.get_json()
    assert event["event_id"] not in {row["event_id"] for row in listed.get_json()["events"]}


# TC-VEI-IT-009/010 (AC4): no event data reaches an unauthenticated caller.
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}],
                         ids=["missing-token", "invalid-token"])
def test_unauthenticated_reads_are_refused(client, planning_event, headers):
    event, _ = planning_event
    for url in (f"/api/events/{event['event_id']}", "/api/events"):
        response = client.get(url, headers=headers)
        assert response.status_code == 401, response.get_json()
        assert response.get_json()["error"]
        assert "event" not in response.get_json() and "events" not in response.get_json()
