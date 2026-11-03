"""Role-based access checks against the isolated Supabase integration project."""


# TC-AUTH-036 (AC4): an Event Coordinator can use the booking workflow route.
def test_event_coordinator_can_access_venue_booking_workflow(client, sign_in):
    response = client.get("/api/venue-bookings", headers=sign_in("Event Coordinator"))

    assert response.status_code == 200, response.get_json()
    assert "bookings" in response.get_json()


# TC-AUTH-037 (AC5): a non-coordinator is refused from the same restricted route.
def test_event_organiser_cannot_access_venue_booking_workflow(client, sign_in):
    response = client.get("/api/venue-bookings", headers=sign_in("Event Organiser"))

    assert response.status_code == 403, response.get_json()
    assert "Event Coordinators and Venue Staff" in response.get_json()["error"]
