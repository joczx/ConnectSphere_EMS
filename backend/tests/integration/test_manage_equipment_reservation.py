"""SCRUM-17: view, resize and cancel real equipment reservations.

The tests use authenticated HTTP endpoints. Admin access creates isolated
events/inventory, verifies database state and cleans up. Availability checks
confirm that reductions and cancellation return stock for overlapping windows.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.supabase_admin import admin_request, user_id_for


@pytest.fixture(scope="module")
def managed_reservations(client, sign_in):
    marker = f"ITEST-SCRUM-17-{uuid.uuid4().hex[:12]}"
    starts = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=60)
    tech_id = user_id_for("Technical Support Staff")
    coordinator_id = user_id_for("Event Coordinator")
    events, items = {}, {}

    def event(label):
        created = client.post("/api/event-requests", headers=sign_in("Event Organiser"), json={
            "event_name": f"{marker}-{label}", "purpose": "Manage reservation test",
            "description": marker, "event_organiser_id": user_id_for("Event Organiser"),
            "start_datetime": starts.isoformat(), "end_datetime": (starts + timedelta(hours=2)).isoformat(),
            "capacity_needed": 30, "room_layout": "theatre", "required_facilities": [],
            "equipment_requirements": [],
        })
        assert created.status_code == 201, created.get_json()
        request_id = created.get_json()["event_request"]["event_request_id"]
        admin_request(f"/rest/v1/event_request?event_request_id=eq.{request_id}",
                      {"event_coordinator_id": coordinator_id}, "PATCH")
        approved = client.post(f"/api/event-requests/{request_id}/review",
                               headers=sign_in("Event Coordinator"), json={"outcome": "approved"})
        assert approved.status_code == 200, approved.get_json()
        row, = admin_request(f"/rest/v1/events?event_request_id=eq.{request_id}")
        admin_request(f"/rest/v1/events?event_id=eq.{row['event_id']}",
                      {"technical_support_id": tech_id}, "PATCH")
        return {**row, "technical_support_id": tech_id}

    headers = sign_in("Technical Support Staff")
    try:
        for label in ("managed", "competing", "cancelled"):
            events[label] = event(label)
        for label in ("resize", "cancel"):
            item, = admin_request("/rest/v1/equipment", {
                "equipment_type": f"{marker}-{label}", "equipment_model": label,
                "total_quantity": 10})
            items[label] = item

        def reserve(event_label, item_label, quantity):
            response = client.post("/api/equipment/reservations", headers=headers, json={
                "event_id": str(events[event_label]["event_id"]),
                "equipment_id": str(items[item_label]["equipment_id"]), "quantity": quantity})
            assert response.status_code == 201, response.get_json()
            return response.get_json()["reservation"]

        reservations = {
            "managed": reserve("managed", "resize", 3),
            "competing": reserve("competing", "resize", 4),
            "cancelled": reserve("cancelled", "cancel", 6),
        }
        yield events, items, reservations, headers
    finally:
        for item in items.values():
            admin_request(f"/rest/v1/equipment_reservations?equipment_id=eq.{item['equipment_id']}", method="DELETE")
        for request in admin_request(f"/rest/v1/event_request?description=eq.{marker}"):
            admin_request(f"/rest/v1/events?event_request_id=eq.{request['event_request_id']}", method="DELETE")
            admin_request(f"/rest/v1/event_request?event_request_id=eq.{request['event_request_id']}", method="DELETE")
        for item in items.values():
            admin_request(f"/rest/v1/equipment?equipment_id=eq.{item['equipment_id']}", method="DELETE")


def _stored(reservation_id):
    rows = admin_request(f"/rest/v1/equipment_reservations?reservation_id=eq.{reservation_id}")
    return rows[0] if rows else None


def _availability(client, headers, event, item):
    response = client.get("/api/equipment-availability", headers=headers, query_string={
        "equipment_type": item["equipment_type"], "quantity": "1",
        "start_datetime": event["start_datetime"], "end_datetime": event["end_datetime"]})
    assert response.status_code == 200, response.get_json()
    rows = [row for row in response.get_json()["results"]
            if row["equipment_id"] == item["equipment_id"]]
    return rows[0]["available_quantity"] if rows else 0


# TC-MER-IT-001 (AC1): owner-scoped list contains full reservation information.
def test_staff_can_view_their_reservations(client, managed_reservations):
    events, items, reservations, headers = managed_reservations
    response = client.get("/api/equipment/reservations", headers=headers)
    assert response.status_code == 200, response.get_json()
    listed = {row["reservation_id"]: row for row in response.get_json()["reservations"]}
    for reservation in reservations.values():
        shown = listed[reservation["reservation_id"]]
        assert shown["event_id"] == reservation["event_id"]
        assert shown["quantity"] == reservation["quantity"]
        assert shown["maximum_quantity"] >= shown["quantity"]
    assert listed[reservations["managed"]["reservation_id"]]["event_name"] == events["managed"]["event_name"]
    assert listed[reservations["managed"]["reservation_id"]]["name"].endswith(items["resize"]["equipment_model"])


# TC-MER-IT-002/003/004 (AC2,4): increase, reject excess, then reduce and return stock.
def test_quantity_changes_obey_availability_and_return_inventory(client, managed_reservations):
    events, items, reservations, headers = managed_reservations
    reservation = reservations["managed"]
    path = f"/api/equipment/reservations/{reservation['reservation_id']}"
    # 3 + competing 4 leaves 3 free; this reservation may grow to 6.
    assert _availability(client, headers, events["managed"], items["resize"]) == 3
    increased = client.patch(path, headers=headers, json={"quantity": 6})
    assert increased.status_code == 200, increased.get_json()
    assert increased.get_json()["reservation"]["quantity"] == 6
    assert _stored(reservation["reservation_id"])["quantity"] == 6
    assert _availability(client, headers, events["managed"], items["resize"]) == 0

    before = _stored(reservation["reservation_id"])
    excessive = client.patch(path, headers=headers, json={"quantity": 7})
    assert excessive.status_code == 409, excessive.get_json()
    assert excessive.get_json()["error"] == (
        "Insufficient equipment: you can reserve at most 6 for this event.")
    assert excessive.get_json()["maximum_quantity"] == 6
    assert _stored(reservation["reservation_id"]) == before

    reduced = client.patch(path, headers=headers, json={"quantity": 2})
    assert reduced.status_code == 200, reduced.get_json()
    assert reduced.get_json()["reservation"]["quantity"] == 2
    assert _stored(reservation["reservation_id"])["quantity"] == 2
    assert _availability(client, headers, events["managed"], items["resize"]) == 4


# TC-MER-IT-005 (AC3,4): cancellation deletes the allocation and restores stock.
def test_cancellation_returns_all_inventory(client, managed_reservations):
    events, items, reservations, headers = managed_reservations
    reservation = reservations["cancelled"]
    assert _availability(client, headers, events["cancelled"], items["cancel"]) == 4
    response = client.delete(f"/api/equipment/reservations/{reservation['reservation_id']}",
                             headers=headers)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["cancelled"] is True
    assert response.get_json()["reservation_id"] == reservation["reservation_id"]
    assert _stored(reservation["reservation_id"]) is None
    assert _availability(client, headers, events["cancelled"], items["cancel"]) == 10


# TC-MER-IT-006: malformed replacement quantities cannot change the row.
@pytest.mark.parametrize("quantity", [0, -1, 1.5, "2", True, None])
def test_invalid_replacement_quantity_is_rejected(client, managed_reservations, quantity):
    _, _, reservations, headers = managed_reservations
    reservation_id = reservations["competing"]["reservation_id"]
    before = _stored(reservation_id)
    response = client.patch(f"/api/equipment/reservations/{reservation_id}",
                            headers=headers, json={"quantity": quantity})
    assert response.status_code == 400, response.get_json()
    assert response.get_json()["error"] == "Quantity must be a positive whole number."
    assert _stored(reservation_id) == before


# TC-MER-IT-007 (AC1-3): non-owners cannot see, modify or cancel the reservation.
@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
@pytest.mark.parametrize("role", ["Event Organiser", "Event Coordinator", "Venue Staff"])
def test_other_users_cannot_manage_reservation(client, sign_in, managed_reservations, role, method):
    _, _, reservations, _ = managed_reservations
    reservation_id = reservations["competing"]["reservation_id"]
    before = _stored(reservation_id)
    response = client.open(f"/api/equipment/reservations/{reservation_id}", method=method,
                           headers=sign_in(role), json={"quantity": 1})
    assert response.status_code == 404, response.get_json()
    assert response.get_json()["error"] == "Reservation not found or access unavailable."
    assert _stored(reservation_id) == before


# TC-MER-IT-008: unknown reservation IDs and authentication are handled safely.
@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
def test_unknown_reservation_is_not_found(client, managed_reservations, method):
    _, _, _, headers = managed_reservations
    response = client.open("/api/equipment/reservations/00000000-0000-0000-0000-000000000000",
                           method=method, headers=headers, json={"quantity": 1})
    assert response.status_code == 404, response.get_json()
    assert response.get_json()["error"] == "Reservation not found or access unavailable."


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/equipment/reservations"),
    ("PATCH", "/api/equipment/reservations/00000000-0000-0000-0000-000000000000"),
    ("DELETE", "/api/equipment/reservations/00000000-0000-0000-0000-000000000000"),
])
def test_management_requires_authentication(client, method, path):
    response = client.open(path, method=method, json={"quantity": 1})
    assert response.status_code == 401, response.get_json()
    assert response.get_json()["error"]
