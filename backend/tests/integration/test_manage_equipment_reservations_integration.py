"""SCRUM-17 Manage Equipment Reservation integration tests.

The tests use the isolated Supabase project selected by .env.integration-test
and remove every event, reservation, and equipment item created during a run.
"""

from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.supabase_admin import (
    admin_request,
    create_technical_support_event,
    delete_test_event,
)


@pytest.fixture
def reservation_scenario(client, sign_in):
    """Create independent temporary events and a catalogue item for each test."""
    events, equipment = [], []

    def make_event(label, starts_at, ends_at):
        event = create_technical_support_event(client, sign_in, label, starts_at, ends_at)
        events.append(event)
        return event

    def make_equipment(total_quantity=5):
        row = admin_request("/rest/v1/equipment", {
            "equipment_type": "ITEST Projector",
            "equipment_model": "Management integration model",
            "total_quantity": total_quantity,
        })[0]
        equipment.append(row)
        return row

    yield make_event, make_equipment

    for event in events:
        delete_test_event(event)
    for row in equipment:
        admin_request(f"/rest/v1/equipment?equipment_id=eq.{row['equipment_id']}", method="DELETE")


def _window(hours_from_base, duration_hours=1):
    base = (datetime.now(timezone.utc) + timedelta(days=100)).replace(
        minute=0, second=0, microsecond=0,
    )
    starts_at = base + timedelta(hours=hours_from_base)
    return starts_at, starts_at + timedelta(hours=duration_hours)


def _reserve(client, headers, event, equipment, quantity):
    response = client.post("/api/equipment/reservations", headers=headers, json={
        "event_id": str(event["event_id"]),
        "equipment_id": str(equipment["equipment_id"]),
        "quantity": quantity,
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()["reservation"]


def _availability(client, headers, event):
    response = client.get(
        f"/api/equipment/availability?event_id={event['event_id']}", headers=headers,
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()["equipment"]


# TC-EMR-008 (AC1): Technical Support can retrieve only its own reservations.
def test_technical_support_can_view_its_reservations(
    client, sign_in, reservation_scenario,
):
    make_event, make_equipment = reservation_scenario
    starts_at, ends_at = _window(0)
    event, equipment = make_event("list", starts_at, ends_at), make_equipment()
    headers = sign_in("Technical Support Staff")
    reservation = _reserve(client, headers, event, equipment, 2)

    response = client.get("/api/equipment/reservations", headers=headers)

    assert response.status_code == 200, response.get_json()
    assert reservation["reservation_id"] in {
        row["reservation_id"] for row in response.get_json()["reservations"]
    }


# TC-EMR-009 (AC2, AC4): decreasing a reservation succeeds and releases the
# reduced quantity to another event in the same time window.
def test_reducing_a_reservation_returns_stock_to_an_overlapping_event(
    client, sign_in, reservation_scenario,
):
    make_event, make_equipment = reservation_scenario
    starts_at, ends_at = _window(0)
    first = make_event("reduce-first", starts_at, ends_at)
    second = make_event("reduce-second", starts_at, ends_at)
    equipment = make_equipment()
    headers = sign_in("Technical Support Staff")
    reservation = _reserve(client, headers, first, equipment, 5)

    response = client.patch(
        f"/api/equipment/reservations/{reservation['reservation_id']}",
        headers=headers, json={"quantity": 3},
    )

    assert response.status_code == 200, response.get_json()
    available = _availability(client, headers, second)
    item = next(row for row in available if row["equipment_id"] == equipment["equipment_id"])
    assert item["available_quantity"] == 2


# TC-EMR-010 (AC2): increasing a reservation beyond remaining overlapping
# stock is rejected and the original reservation remains unchanged.
def test_increasing_a_reservation_is_blocked_when_stock_is_insufficient(
    client, sign_in, reservation_scenario,
):
    make_event, make_equipment = reservation_scenario
    starts_at, ends_at = _window(0)
    first = make_event("increase-first", starts_at, ends_at)
    second = make_event("increase-second", starts_at, ends_at)
    equipment = make_equipment()
    headers = sign_in("Technical Support Staff")
    first_reservation = _reserve(client, headers, first, equipment, 3)
    _reserve(client, headers, second, equipment, 2)

    response = client.patch(
        f"/api/equipment/reservations/{first_reservation['reservation_id']}",
        headers=headers, json={"quantity": 4},
    )

    assert response.status_code == 409, response.get_json()
    assert "Insufficient equipment" in response.get_json()["error"]
    rows = admin_request(
        f"/rest/v1/equipment_reservations?select=quantity&reservation_id=eq.{first_reservation['reservation_id']}"
    )
    assert rows[0]["quantity"] == 3


# TC-EMR-011 (AC3, AC4): cancelling a reservation removes it and returns its
# stock to another event whose period overlaps.
def test_cancelling_a_reservation_returns_all_stock_to_an_overlapping_event(
    client, sign_in, reservation_scenario,
):
    make_event, make_equipment = reservation_scenario
    starts_at, ends_at = _window(0)
    first = make_event("cancel-first", starts_at, ends_at)
    second = make_event("cancel-second", starts_at, ends_at)
    equipment = make_equipment()
    headers = sign_in("Technical Support Staff")
    reservation = _reserve(client, headers, first, equipment, 5)

    response = client.delete(
        f"/api/equipment/reservations/{reservation['reservation_id']}", headers=headers,
    )

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["cancelled"] is True
    available = _availability(client, headers, second)
    item = next(row for row in available if row["equipment_id"] == equipment["equipment_id"])
    assert item["available_quantity"] == 5
