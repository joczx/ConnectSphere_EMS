"""SCRUM-16: reserve real inventory for assigned planning events.

All reservation calls use the Technical Support account. Service-role access
only creates isolated fixtures, verifies persistence and performs cleanup.
Event windows are half-open: [start, end), so adjacent events do not overlap.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.supabase_admin import admin_request, user_id_for


@pytest.fixture(scope="module")
def reservation_setup(client, sign_in):
    marker = f"ITEST-SCRUM-16-{uuid.uuid4().hex[:12]}"
    base = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=60)
    tech_id = user_id_for("Technical Support Staff")
    coordinator_id = user_id_for("Event Coordinator")
    events, item = {}, None

    def create_event(label, start, end):
        response = client.post("/api/event-requests", headers=sign_in("Event Organiser"), json={
            "event_name": f"{marker}-{label}", "purpose": "Reservation integration test",
            "description": marker, "event_organiser_id": user_id_for("Event Organiser"),
            "start_datetime": start.isoformat(), "end_datetime": end.isoformat(),
            "capacity_needed": 30, "room_layout": "theatre", "required_facilities": [],
            "equipment_requirements": [],
        })
        assert response.status_code == 201, response.get_json()
        request_id = response.get_json()["event_request"]["event_request_id"]
        admin_request(f"/rest/v1/event_request?event_request_id=eq.{request_id}",
                      {"event_coordinator_id": coordinator_id}, "PATCH")
        approved = client.post(f"/api/event-requests/{request_id}/review",
                               headers=sign_in("Event Coordinator"), json={"outcome": "approved"})
        assert approved.status_code == 200, approved.get_json()
        event, = admin_request(f"/rest/v1/events?event_request_id=eq.{request_id}")
        admin_request(f"/rest/v1/events?event_id=eq.{event['event_id']}",
                      {"technical_support_id": tech_id}, "PATCH")
        return {**event, "technical_support_id": tech_id}

    try:
        events["first"] = create_event("first", base, base + timedelta(hours=2))
        events["overlap"] = create_event("overlap", base + timedelta(hours=1), base + timedelta(hours=3))
        events["adjacent"] = create_event("adjacent", base + timedelta(hours=3), base + timedelta(hours=5))
        events["later"] = create_event("later", base + timedelta(days=1), base + timedelta(days=1, hours=2))
        item, = admin_request("/rest/v1/equipment", {
            "equipment_type": marker, "equipment_model": "Reservation model", "total_quantity": 5})
        yield events, item, sign_in("Technical Support Staff")
    finally:
        if item:
            admin_request(f"/rest/v1/equipment_reservations?equipment_id=eq.{item['equipment_id']}", method="DELETE")
        for request in admin_request(f"/rest/v1/event_request?description=eq.{marker}"):
            admin_request(f"/rest/v1/events?event_request_id=eq.{request['event_request_id']}", method="DELETE")
            admin_request(f"/rest/v1/event_request?event_request_id=eq.{request['event_request_id']}", method="DELETE")
        if item:
            admin_request(f"/rest/v1/equipment?equipment_id=eq.{item['equipment_id']}", method="DELETE")


def _reserve(client, headers, event, item, quantity):
    return client.post("/api/equipment/reservations", headers=headers, json={
        "event_id": str(event["event_id"]), "equipment_id": str(item["equipment_id"]),
        "quantity": quantity,
    })


def _reservations(item):
    return admin_request(
        f"/rest/v1/equipment_reservations?equipment_id=eq.{item['equipment_id']}&order=starts_at.asc")


def _availability(client, headers, event, item, quantity=1):
    response = client.get("/api/equipment-availability", headers=headers, query_string={
        "equipment_type": item["equipment_type"], "quantity": str(quantity),
        "start_datetime": event["start_datetime"], "end_datetime": event["end_datetime"],
    })
    assert response.status_code == 200, response.get_json()
    rows = [row for row in response.get_json()["results"]
            if row["equipment_id"] == item["equipment_id"]]
    return rows[0] if rows else None


# TC-RES-IT-001 (AC1-4): selected equipment and quantity persist on the event.
def test_assigned_staff_can_reserve_available_equipment(client, reservation_setup):
    events, item, headers = reservation_setup
    response = _reserve(client, headers, events["first"], item, 3)
    assert response.status_code == 201, response.get_json()
    body = response.get_json()
    assert body["message"] == "Equipment reserved successfully."
    saved = body["reservation"]
    assert saved["event_id"] == events["first"]["event_id"]
    assert saved["equipment_id"] == item["equipment_id"] and saved["quantity"] == 3
    assert saved["created_by"] == user_id_for("Technical Support Staff")
    stored, = [row for row in _reservations(item) if row["reservation_id"] == saved["reservation_id"]]
    assert stored == saved


# TC-RES-IT-002 (AC4,5,6,7): overlapping stock is deducted and excess rejected.
def test_overlapping_reservation_is_limited_by_remaining_stock(client, reservation_setup):
    events, item, headers = reservation_setup
    before = _reservations(item)
    availability = _availability(client, headers, events["overlap"], item, quantity=3)
    assert availability["available_quantity"] == 2
    assert availability["fulfillment_status"] == "partially_available"
    response = _reserve(client, headers, events["overlap"], item, 3)
    assert response.status_code == 409, response.get_json()
    assert response.get_json()["error"] == "Insufficient equipment: only 2 available for this event."
    assert response.get_json()["available_quantity"] == 2
    assert _reservations(item) == before


# TC-RES-IT-003 (AC2-4,7): exactly the remaining overlapping quantity succeeds.
def test_exact_remaining_quantity_can_be_reserved(client, reservation_setup):
    events, item, headers = reservation_setup
    response = _reserve(client, headers, events["overlap"], item, 2)
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["reservation"]["quantity"] == 2
    # The peak is now full, so zero-availability inventory is omitted.
    assert _availability(client, headers, events["overlap"], item) is None


# TC-RES-IT-004 (AC8): adjacent and later events retain the full stock.
@pytest.mark.parametrize("event_name", ["adjacent", "later"])
def test_non_overlapping_event_can_reserve_full_stock(client, reservation_setup, event_name):
    events, item, headers = reservation_setup
    available = _availability(client, headers, events[event_name], item, quantity=5)
    assert available["available_quantity"] == 5
    assert available["fulfillment_status"] == "available"
    response = _reserve(client, headers, events[event_name], item, 5)
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["reservation"]["event_id"] == events[event_name]["event_id"]


# TC-RES-IT-005 (AC3): one direct reservation per equipment item and event.
def test_duplicate_direct_reservation_is_rejected(client, reservation_setup):
    events, item, headers = reservation_setup
    before = _reservations(item)
    response = _reserve(client, headers, events["first"], item, 1)
    assert response.status_code == 409, response.get_json()
    assert "already reserved" in response.get_json()["error"]
    assert _reservations(item) == before


# TC-RES-IT-006 (AC1,5,6): malformed quantities do not create rows.
@pytest.mark.parametrize("quantity", [0, -1, 1.5, "2", True, None])
def test_invalid_quantity_is_rejected(client, reservation_setup, quantity):
    events, item, headers = reservation_setup
    before = _reservations(item)
    response = _reserve(client, headers, events["first"], item, quantity)
    assert response.status_code == 400, response.get_json()
    assert response.get_json()["error"] == "Quantity must be a positive whole number."
    assert _reservations(item) == before


# TC-RES-IT-007 (AC1): unknown event/equipment identifiers are actionable.
@pytest.mark.parametrize("changes,status", [
    ({"event_id": "999999999"}, 404), ({"equipment_id": "999999999"}, 404),
    ({"event_id": "invalid"}, 404), ({"equipment_id": "invalid"}, 400),
])
def test_invalid_selection_is_rejected(client, reservation_setup, changes, status):
    events, item, headers = reservation_setup
    body = {"event_id": str(events["first"]["event_id"]),
            "equipment_id": str(item["equipment_id"]), "quantity": 1, **changes}
    before = _reservations(item)
    response = client.post("/api/equipment/reservations", headers=headers, json=body)
    assert response.status_code == status, response.get_json()
    assert response.get_json()["error"] and _reservations(item) == before


# TC-RES-IT-008: only assigned Technical Support may reserve for the event.
@pytest.mark.parametrize("role", ["Event Organiser", "Event Coordinator", "Venue Staff", "Safety Officer"])
def test_other_roles_cannot_reserve(client, sign_in, reservation_setup, role):
    events, item, _ = reservation_setup
    before = _reservations(item)
    response = _reserve(client, sign_in(role), events["first"], item, 1)
    assert response.status_code == 403, response.get_json()
    assert response.get_json()["error"] and _reservations(item) == before


def test_reservation_requires_authentication(client, reservation_setup):
    events, item, _ = reservation_setup
    before = _reservations(item)
    response = _reserve(client, {}, events["first"], item, 1)
    assert response.status_code == 401, response.get_json()
    assert response.get_json()["error"] and _reservations(item) == before
