"""Confirmed-booking conflict checks against PostgreSQL's overlap constraint."""

import pytest

from tests.integration.supabase_admin import create_event_assigned_to
from tests.integration.venue_helpers import (
    create_venue_for_setup, future_window, remove_venue_scenario, venue_payload,
)


@pytest.fixture
def conflict_scenario(client, sign_in):
    events, venues = [], []
    yield events, venues
    remove_venue_scenario(events, venues)


def _request(client, headers, event, venue, starts_at, ends_at):
    response = client.post("/api/venue-bookings", headers=headers, json={
        "event_id": event["event_id"], "event_name": "ITEST venue conflict",
        "venue_id": venue["venue_id"], "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(), "attendance": 40,
        "venue_requirements": "Theatre layout with projector",
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()["booking"]


# TC-VBC-014 (AC1-AC5): an approved booking makes the venue unavailable to an
# overlapping request, and the reviewer receives the conflicting booking data.
def test_confirmed_booking_blocks_overlapping_booking_approval(client, sign_in, conflict_scenario):
    events, venues = conflict_scenario
    starts_at, ends_at = future_window()
    first = create_event_assigned_to(client, sign_in, "conflict first", starts_at, ends_at, "Venue Staff")
    second = create_event_assigned_to(client, sign_in, "conflict second", starts_at, ends_at, "Venue Staff")
    events.extend([first, second])
    venue = create_venue_for_setup(venue_payload(capacity=100))
    venues.append(venue)
    coordinator = sign_in("Event Coordinator")
    first_booking = _request(client, coordinator, first, venue, starts_at, ends_at)
    second_booking = _request(client, coordinator, second, venue, starts_at, ends_at)
    staff = sign_in("Venue Staff")

    approved = client.post(f"/api/venue-bookings/{first_booking['booking_id']}/review", headers=staff, json={"outcome": "approved"})
    assert approved.status_code == 200, approved.get_json()
    response = client.post(f"/api/venue-bookings/{second_booking['booking_id']}/review", headers=staff, json={"outcome": "approved"})

    assert response.status_code == 409, response.get_json()
    assert response.get_json()["conflicts"]
    assert response.get_json()["conflicts"][0]["booking_id"] == first_booking["booking_id"]
