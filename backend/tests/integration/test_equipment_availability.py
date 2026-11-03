"""SCRUM-15: real inventory, overlapping allocations and role restrictions.

AC1-5 exercise authenticated availability HTTP responses against isolated
inventory/reservations. AC6 checks availability and the equipment-type catalogue.
Messages are checked in API responses; browser rendering requires UI tests.
Admin access only arranges fixtures and cleans up, never performs tested reads.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.supabase_admin import admin_request, user_id_for


@pytest.fixture(scope="module")
def inventory(client, sign_in):
    marker = f"ITEST-SCRUM-15-{uuid.uuid4().hex[:12]}"
    starts = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=60)
    items = {}
    try:
        created = client.post("/api/event-requests", headers=sign_in("Event Organiser"), json={
            "event_name": marker, "purpose": "Availability test", "description": marker,
            "event_organiser_id": user_id_for("Event Organiser"),
            "start_datetime": starts.isoformat(), "end_datetime": (starts + timedelta(hours=6)).isoformat(),
            "capacity_needed": 40, "room_layout": "theatre", "required_facilities": [],
            "equipment_requirements": [],
        })
        assert created.status_code == 201, created.get_json()
        request_id = created.get_json()["event_request"]["event_request_id"]
        admin_request(f"/rest/v1/event_request?event_request_id=eq.{request_id}",
                      {"event_coordinator_id": user_id_for("Event Coordinator")}, "PATCH")
        approved = client.post(f"/api/event-requests/{request_id}/review",
                               headers=sign_in("Event Coordinator"), json={"outcome": "approved"})
        assert approved.status_code == 200, approved.get_json()
        event, = admin_request(f"/rest/v1/events?event_request_id=eq.{request_id}")
        for model, total in {"partial": 5, "full": 5, "free": 7, "zero": 0, "other": 9}.items():
            item, = admin_request("/rest/v1/equipment", {
                "equipment_type": marker if model != "other" else marker + "-other",
                "equipment_model": model, "total_quantity": total})
            items[model] = item
        for model, quantity in (("partial", 2), ("full", 5)):
            admin_request("/rest/v1/equipment_reservations", {
                "event_id": event["event_id"], "equipment_id": items[model]["equipment_id"],
                "quantity": quantity, "starts_at": (starts + timedelta(hours=1)).isoformat(),
                "ends_at": (starts + timedelta(hours=3)).isoformat(),
                "created_by": user_id_for("Technical Support Staff"),
            })
        yield marker, starts, items
    finally:
        for request in admin_request(f"/rest/v1/event_request?event_name=eq.{marker}"):
            for event in admin_request(f"/rest/v1/events?event_request_id=eq.{request['event_request_id']}"):
                admin_request(f"/rest/v1/equipment_reservations?event_id=eq.{event['event_id']}", method="DELETE")
                admin_request(f"/rest/v1/events?event_id=eq.{event['event_id']}", method="DELETE")
            admin_request(f"/rest/v1/event_request?event_request_id=eq.{request['event_request_id']}", method="DELETE")
        for item in items.values():
            admin_request(f"/rest/v1/equipment?equipment_id=eq.{item['equipment_id']}", method="DELETE")


def _criteria(inventory, **changes):
    marker, starts, _ = inventory
    return {"equipment_type": marker, "quantity": "4",
            "start_datetime": (starts + timedelta(hours=2)).isoformat(),
            "end_datetime": (starts + timedelta(hours=4)).isoformat(), **changes}


def _search(client, sign_in, inventory, **changes):
    response = client.get("/api/equipment-availability", headers=sign_in("Technical Support Staff"),
                          query_string=_criteria(inventory, **changes))
    assert response.status_code == 200, response.get_json()
    assert response.headers["Cache-Control"] == "no-store"
    return response.get_json()


# TC-EAV-IT-001 (AC1-4): full allocations disappear; remaining stock is exact.
def test_overlapping_allocations_reduce_available_quantity(client, sign_in, inventory):
    _, _, items = inventory
    body = _search(client, sign_in, inventory)
    assert body["message"] == "Availability checked successfully."
    rows = {row["equipment_model"]: row for row in body["results"]}
    assert set(rows) == {"partial", "free"}
    for model, quantity, status in (("partial", 3, "partially_available"), ("free", 7, "available")):
        assert rows[model]["equipment_id"] == items[model]["equipment_id"]
        assert rows[model]["available_quantity"] == quantity
        assert rows[model]["requested_quantity"] == 4
        assert rows[model]["fulfillment_status"] == status


# TC-EAV-IT-002 (AC2): adjacent half-open periods do not consume inventory.
@pytest.mark.parametrize("start_hour,end_hour", [(0, 1), (3, 4)], ids=["ends-at-reservation-start", "starts-at-reservation-end"])
def test_adjacent_periods_do_not_overlap(client, sign_in, inventory, start_hour, end_hour):
    _, starts, _ = inventory
    body = _search(client, sign_in, inventory,
                   start_datetime=(starts + timedelta(hours=start_hour)).isoformat(),
                   end_datetime=(starts + timedelta(hours=end_hour)).isoformat())
    assert {row["equipment_model"]: row["available_quantity"] for row in body["results"]} == {
        "partial": 5, "full": 5, "free": 7}


# TC-EAV-IT-003 (AC3,4): quantity equal to available stock is sufficient.
def test_exact_remaining_quantity_is_available(client, sign_in, inventory):
    body = _search(client, sign_in, inventory, quantity="3")
    partial, = [row for row in body["results"] if row["equipment_model"] == "partial"]
    assert partial["available_quantity"] == 3 and partial["fulfillment_status"] == "available"


# TC-EAV-IT-004 (AC5): no matching type gives the actual no-results message.
def test_no_suitable_equipment_returns_message(client, sign_in, inventory):
    body = _search(client, sign_in, inventory, equipment_type=inventory[0] + "-missing")
    assert body == {"results": [], "message": "No suitable equipment is available for the selected criteria."}


# TC-EAV-IT-005 (AC1): type matching is case insensitive and exact, not a prefix.
def test_type_filter_and_catalogue_for_technical_support(client, sign_in, inventory):
    marker, _, _ = inventory
    body = _search(client, sign_in, inventory, equipment_type=marker.lower())
    assert len(body["results"]) == 2
    assert all(row["equipment_type"] == marker for row in body["results"])
    catalogue = client.get("/api/equipment-types", headers=sign_in("Technical Support Staff"))
    assert catalogue.status_code == 200, catalogue.get_json()
    assert marker in catalogue.get_json()["equipment_types"]


# TC-EAV-IT-006 (AC6): both catalogue and availability are Technical Support only.
@pytest.mark.parametrize("role", ["Event Organiser", "Event Coordinator", "Event Coordinator Lead",
                                 "Venue Staff", "Safety Officer", "Attendee"])
@pytest.mark.parametrize("endpoint", ["/api/equipment-types", "/api/equipment-availability"])
def test_other_roles_cannot_view_equipment(client, sign_in, inventory, role, endpoint):
    response = client.get(endpoint, headers=sign_in(role), query_string=_criteria(inventory))
    assert response.status_code == 403, response.get_json()
    assert response.get_json()["error"]
    assert "results" not in response.get_json() and "equipment_types" not in response.get_json()


# TC-EAV-IT-007 (AC1): invalid search criteria return actionable errors.
@pytest.mark.parametrize("changes,field", [
    ({"quantity": "0"}, "quantity"), ({"quantity": "1.5"}, "quantity"),
    ({"equipment_type": ""}, "equipment_type"),
    ({"start_datetime": "invalid"}, "start_datetime"),
    ({"start_datetime": "2030-01-01T09:00:00"}, "start_datetime"),
    ({"end_datetime": "2000-01-01T00:00:00Z"}, "end_datetime"),
])
def test_invalid_search_criteria_are_rejected(client, sign_in, inventory, changes, field):
    response = client.get("/api/equipment-availability", headers=sign_in("Technical Support Staff"),
                          query_string=_criteria(inventory, **changes))
    assert response.status_code == 400, response.get_json()
    assert response.get_json()["error"] and field in response.get_json()["details"]
    assert "results" not in response.get_json()


@pytest.mark.parametrize("endpoint", ["/api/equipment-types", "/api/equipment-availability"])
def test_equipment_read_requires_authentication(client, inventory, endpoint):
    response = client.get(endpoint, query_string=_criteria(inventory))
    assert response.status_code == 401, response.get_json()
    assert "results" not in response.get_json() and "equipment_types" not in response.get_json()
