"""SCRUM-29 venue-request workflow against the isolated Supabase project."""

import pytest

from tests.integration.supabase_admin import create_event_assigned_to
from tests.integration.venue_helpers import (
    create_venue_for_setup, future_window, remove_venue_scenario, venue_payload,
)


@pytest.fixture
def booking_scenario(client, sign_in):
    events, venues = [], []
    yield events, venues
    remove_venue_scenario(events, venues)


# TC-RBV-057 (AC1-AC6): a Coordinator submits a complete request for each of
# two venues, then the assigned Venue Staff can list both pending requests.
def test_coordinator_can_submit_multiple_complete_venue_booking_requests(
    client, sign_in, booking_scenario,
):
    events, venues = booking_scenario
    starts_at, ends_at = future_window()
    event = create_event_assigned_to(
        client, sign_in, "venue booking", starts_at, ends_at, "Venue Staff",
        purpose="Venue booking integration test",
    )
    events.append(event)
    venues.extend([create_venue_for_setup(venue_payload(capacity=100)), create_venue_for_setup(venue_payload(capacity=100))])
    payload = {
        "event_id": event["event_id"], "event_name": None,
        "starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat(),
        "attendance": 40, "venue_requirements": "Theatre layout with projector",
    }
    headers = sign_in("Event Coordinator")

    created = []
    for venue in venues:
        response = client.post("/api/venue-bookings", headers=headers, json={
            **payload, "event_name": f"ITEST venue booking", "venue_id": venue["venue_id"],
        })
        assert response.status_code == 201, response.get_json()
        assert response.get_json()["message"] == "Booking request submitted. Venue Staff can now review it."
        created.append(response.get_json()["booking"])

    listed = client.get("/api/venue-bookings", headers=sign_in("Venue Staff"))
    assert listed.status_code == 200, listed.get_json()
    listed_ids = {booking["booking_id"] for booking in listed.get_json()["bookings"]}
    assert {booking["booking_id"] for booking in created} <= listed_ids
