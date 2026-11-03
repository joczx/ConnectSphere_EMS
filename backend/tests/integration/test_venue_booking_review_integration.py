"""Venue Staff review decisions against real booking data."""

import pytest

from tests.integration.supabase_admin import create_event_assigned_to
from tests.integration.venue_helpers import (
    create_venue_for_setup, future_window, remove_venue_scenario, venue_payload,
)


@pytest.fixture
def review_scenario(client, sign_in):
    events, venues = [], []
    yield events, venues
    remove_venue_scenario(events, venues)


def _submit(client, headers, event, venue, starts_at, ends_at):
    response = client.post("/api/venue-bookings", headers=headers, json={
        "event_id": event["event_id"], "event_name": "ITEST venue review",
        "venue_id": venue["venue_id"], "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(), "attendance": 40,
        "venue_requirements": "Theatre layout with projector",
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()["booking"]


# TC-VBR-021 (AC1-AC3): Venue Staff view a pending request with its
# details, approve it, and the database stores the approved status.
def test_venue_staff_can_view_and_approve_a_pending_booking(client, sign_in, review_scenario):
    events, venues = review_scenario
    starts_at, ends_at = future_window()
    event = create_event_assigned_to(client, sign_in, "venue review", starts_at, ends_at, "Venue Staff")
    events.append(event)
    venue = create_venue_for_setup(venue_payload(capacity=100))
    venues.append(venue)
    booking = _submit(client, sign_in("Event Coordinator"), event, venue, starts_at, ends_at)

    viewed = client.get(f"/api/venue-bookings/{booking['booking_id']}", headers=sign_in("Venue Staff"))
    assert viewed.status_code == 200, viewed.get_json()
    assert {"starts_at", "ends_at", "attendance", "venue_requirements"} <= set(viewed.get_json()["booking"])
    response = client.post(f"/api/venue-bookings/{booking['booking_id']}/review", headers=sign_in("Venue Staff"), json={"outcome": "approved"})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["booking"]["status"] == "approved"


# TC-VBR-022 (AC3): a Venue Staff member can reject a booking with a
# reason, and that decision is persisted by the database.
def test_venue_staff_can_reject_a_booking_with_comments(client, sign_in, review_scenario):
    events, venues = review_scenario
    starts_at, ends_at = future_window(hours=4)
    event = create_event_assigned_to(client, sign_in, "venue rejection", starts_at, ends_at, "Venue Staff")
    events.append(event)
    venue = create_venue_for_setup(venue_payload(capacity=100))
    venues.append(venue)
    booking = _submit(client, sign_in("Event Coordinator"), event, venue, starts_at, ends_at)
    staff = sign_in("Venue Staff")

    response = client.post(f"/api/venue-bookings/{booking['booking_id']}/review", headers=staff, json={"outcome": "rejected", "comments": "The hall is unavailable."})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["booking"]["status"] == "rejected"


# TC-VBR-023 (AC4): the API refuses a rejection that omits the required reason.
def test_venue_staff_rejection_requires_comments(client, sign_in, review_scenario):
    events, venues = review_scenario
    starts_at, ends_at = future_window(hours=8)
    event = create_event_assigned_to(client, sign_in, "venue missing comment", starts_at, ends_at, "Venue Staff")
    events.append(event)
    venue = create_venue_for_setup(venue_payload(capacity=100))
    venues.append(venue)
    booking = _submit(client, sign_in("Event Coordinator"), event, venue, starts_at, ends_at)

    response = client.post(
        f"/api/venue-bookings/{booking['booking_id']}/review",
        headers=sign_in("Venue Staff"), json={"outcome": "rejected", "comments": ""},
    )

    assert response.status_code == 400, response.get_json()
    assert "comments" in response.get_json()["errors"]
