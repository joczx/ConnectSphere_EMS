"""SCRUM-16 Reserve Equipment integration tests against the isolated Supabase project.

Run only with ``RUN_INTEGRATION_TESTS=1``. The session integration fixture
refuses to use the development Supabase project. Each test creates and removes
its own events and equipment catalogue item.
"""

from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.supabase_admin import (
    admin_request,
    create_technical_support_event,
    delete_test_event,
)


@pytest.fixture
def equipment_scenario(client, sign_in):
    """Create temporary equipment plus Technical Support-assigned events."""
    events, equipment = [], []

    def make_event(label, starts_at, ends_at):
        event = create_technical_support_event(client, sign_in, label, starts_at, ends_at)
        events.append(event)
        return event

    def make_equipment(total_quantity=5):
        row = admin_request("/rest/v1/equipment", {
            "equipment_type": "ITEST Projector",
            "equipment_model": "Reservation integration model",
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
    base = (datetime.now(timezone.utc) + timedelta(days=90)).replace(
        minute=0, second=0, microsecond=0,
    )
    starts_at = base + timedelta(hours=hours_from_base)
    return starts_at, starts_at + timedelta(hours=duration_hours)


def _reserve(client, headers, event, equipment, quantity):
    return client.post("/api/equipment/reservations", headers=headers, json={
        "event_id": str(event["event_id"]),
        "equipment_id": str(equipment["equipment_id"]),
        "quantity": quantity,
    })


# TC-ERES-010 (AC1-AC4): the assigned Technical Support Staff member can
# reserve sufficient stock, and the reservation is recorded against the event.
def test_technical_support_reserves_sufficient_equipment(
    client, sign_in, equipment_scenario,
):
    make_event, make_equipment = equipment_scenario
    starts_at, ends_at = _window(0)
    event, equipment = make_event("reserve", starts_at, ends_at), make_equipment()

    response = _reserve(client, sign_in("Technical Support Staff"), event, equipment, 3)

    assert response.status_code == 201, response.get_json()
    reservation = response.get_json()["reservation"]
    assert str(reservation["event_id"]) == str(event["event_id"])
    assert reservation["equipment_id"] == equipment["equipment_id"]
    assert reservation["quantity"] == 3


# TC-ERES-011 (AC5, AC6, AC7): all stock reserved during one event is
# unavailable to a second event whose period overlaps.
def test_overlapping_event_cannot_reserve_stock_already_allocated(
    client, sign_in, equipment_scenario,
):
    make_event, make_equipment = equipment_scenario
    starts_at, ends_at = _window(0)
    first = make_event("overlap-first", starts_at, ends_at)
    second = make_event("overlap-second", starts_at, ends_at)
    equipment = make_equipment()
    headers = sign_in("Technical Support Staff")

    assert _reserve(client, headers, first, equipment, 5).status_code == 201
    response = _reserve(client, headers, second, equipment, 1)

    assert response.status_code == 409, response.get_json()
    assert response.get_json()["available_quantity"] == 0
    assert "Insufficient equipment" in response.get_json()["error"]


# TC-ERES-012 (AC8): the same stock can be reserved for an event that starts
# exactly when the earlier reservation ends, because the periods do not overlap.
def test_adjacent_event_can_reuse_equipment_stock(
    client, sign_in, equipment_scenario,
):
    make_event, make_equipment = equipment_scenario
    starts_at, ends_at = _window(0)
    first = make_event("adjacent-first", starts_at, ends_at)
    second = make_event("adjacent-second", ends_at, ends_at + timedelta(hours=1))
    equipment = make_equipment()
    headers = sign_in("Technical Support Staff")

    assert _reserve(client, headers, first, equipment, 5).status_code == 201
    response = _reserve(client, headers, second, equipment, 5)

    assert response.status_code == 201, response.get_json()
    assert response.get_json()["reservation"]["quantity"] == 5
