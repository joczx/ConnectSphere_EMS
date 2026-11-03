"""Venue catalogue CRUD workflows against the isolated Supabase project."""

import pytest

from tests.integration.supabase_admin import admin_request, create_event_assigned_to
from tests.integration.venue_helpers import future_window, remove_venue_scenario, venue_payload


@pytest.fixture
def created_venues():
    venues = []
    yield venues
    remove_venue_scenario([], venues)


# TC-VCAT-061: Venue Staff can create a complete, unique venue record.
def test_venue_staff_can_create_a_complete_unique_venue(client, sign_in, created_venues):
    staff = sign_in("Venue Staff")
    response = client.post("/api/venues", headers=staff, json=venue_payload())
    assert response.status_code == 201, response.get_json()
    venue = response.get_json()["venue"]
    created_venues.append(venue)

    assert response.get_json()["message"] == "Venue created successfully."


# TC-VCAT-063: a created venue is returned in both the catalogue and detail view.
def test_venue_staff_can_view_a_created_venue(client, sign_in, created_venues):
    staff = sign_in("Venue Staff")
    response = client.post("/api/venues", headers=staff, json=venue_payload())
    assert response.status_code == 201, response.get_json()
    venue = response.get_json()["venue"]
    created_venues.append(venue)

    catalogue = client.get("/api/venues/catalogue", headers=staff)
    assert catalogue.status_code == 200, catalogue.get_json()
    assert venue["venue_id"] in {row["venue_id"] for row in catalogue.get_json()["venues"]}
    detail = client.get(f"/api/venues/{venue['venue_id']}", headers=staff)
    assert detail.status_code == 200, detail.get_json()
    assert detail.get_json()["venue"]["venue_name"] == venue["venue_name"]


# TC-VCAT-066: Venue Staff can filter the real catalogue by venue information.
def test_venue_staff_can_filter_the_catalogue(client, sign_in, created_venues):
    staff = sign_in("Venue Staff")
    payload = venue_payload(capacity=125)
    response = client.post("/api/venues", headers=staff, json=payload)
    assert response.status_code == 201, response.get_json()
    venue = response.get_json()["venue"]
    created_venues.append(venue)

    filtered = client.get(
        f"/api/venues/search?name={venue['venue_name']}&capacity=125&layouts=theatre&facilities=projector",
        headers=staff,
    )

    assert filtered.status_code == 200, filtered.get_json()
    assert venue["venue_id"] in {row["venue_id"] for row in filtered.get_json()["venues"]}


# TC-VCAT-064: a partial edit with the current version persists in the database.
def test_venue_staff_can_update_one_field_of_a_venue(client, sign_in, created_venues):
    staff = sign_in("Venue Staff")
    response = client.post("/api/venues", headers=staff, json=venue_payload())
    assert response.status_code == 201, response.get_json()
    venue = response.get_json()["venue"]
    created_venues.append(venue)

    update = client.patch(f"/api/venues/{venue['venue_id']}", headers=staff, json={"version": venue["version"], "capacity": 120})
    assert update.status_code == 200, update.get_json()
    assert update.get_json()["venue"]["capacity"] == 120


# TC-VCAT-065: a Venue Staff member can remove an unused venue after the delete check.
def test_venue_staff_can_delete_an_unused_venue(client, sign_in, created_venues):
    staff = sign_in("Venue Staff")
    response = client.post("/api/venues", headers=staff, json=venue_payload())
    assert response.status_code == 201, response.get_json()
    venue = response.get_json()["venue"]
    created_venues.append(venue)

    deleted = client.delete(f"/api/venues/{venue['venue_id']}", headers=staff)
    assert deleted.status_code == 200, deleted.get_json()
    created_venues.remove(venue)


# TC-VCAT-062 (AC3): a duplicate name-and-address venue is refused by the database.
def test_venue_staff_cannot_create_a_duplicate_venue(client, sign_in, created_venues):
    staff = sign_in("Venue Staff")
    payload = venue_payload()
    first = client.post("/api/venues", headers=staff, json=payload)
    assert first.status_code == 201, first.get_json()
    created_venues.append(first.get_json()["venue"])
    duplicate = client.post("/api/venues", headers=staff, json=payload)

    assert duplicate.status_code == 409, duplicate.get_json()
    assert "same name and address" in duplicate.get_json()["error"]


# TC-VCAT-067: deletion is refused and lists an event that is still scheduled.
def test_venue_with_an_upcoming_event_cannot_be_deleted(client, sign_in):
    events, venues = [], []
    try:
        staff = sign_in("Venue Staff")
        created = client.post("/api/venues", headers=staff, json=venue_payload())
        assert created.status_code == 201, created.get_json()
        venue = created.get_json()["venue"]
        venues.append(venue)
        starts_at, ends_at = future_window(days=130)
        event = create_event_assigned_to(client, sign_in, "venue deletion", starts_at, ends_at, "Venue Staff")
        events.append(event)
        admin_request(
            f"/rest/v1/events?event_id=eq.{event['event_id']}",
            {"venue_id": venue["venue_id"]}, "PATCH",
        )

        response = client.delete(f"/api/venues/{venue['venue_id']}", headers=staff)

        assert response.status_code == 409, response.get_json()
        assert response.get_json()["events"]
        assert str(event["event_id"]) == str(response.get_json()["events"][0]["event_id"])
    finally:
        remove_venue_scenario(events, venues)
