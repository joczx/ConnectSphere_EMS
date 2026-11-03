"""Unit tests for SCRUM-32: attendee catalogue of upcoming events.

The catalogue query and its time-based filtering live in the Supabase
``attendee_registration_events`` function. These tests isolate the Flask route
and verify its complete response contract. The integration counterpart executes
the database rules against real open, closed and cancelled events.
"""
from unittest.mock import patch

import pytest

from app import create_app


HEADERS = {"Authorization": "Bearer verified"}
RPC_PATH = "/rest/v1/rpc/attendee_registration_events"


def client():
    return create_app().test_client()


def catalogue_event(**changes):
    event = {
        "event_id": 41,
        "event_name": "Community Technology Fair",
        "description": "The latest confirmed event description",
        "start_datetime": "2027-01-03T10:00:00+08:00",
        "end_datetime": "2027-01-03T16:00:00+08:00",
        "status": "confirmed",
        "venue_id": "a944ef95-b4df-44b3-a625-c234ef16b9f6",
        "venue_name": "ConnectSphere Convention Hall",
        "registration_opens_at": "2027-01-01T10:00:00+08:00",
        "registration_closes_at": "2027-01-02T10:00:00+08:00",
        "registration_status": "open",
        "waiting_list_enabled": True,
        "capacity": 250,
        "available_capacity": 173,
        "my_registration": None,
    }
    event.update(changes)
    return event


def get_catalogue(result):
    with patch("app.routes.events.supabase_request", return_value={"id": "attendee"}), \
         patch("app.services.registration_service.supabase_request", return_value=result) as rpc:
        response = client().get("/api/registration-events", headers=HEADERS)
    rpc.assert_called_once_with(RPC_PATH, token="verified", payload={}, method="POST")
    return response


# AC1: an Attendee receives the upcoming event catalogue and its open state.
def test_attendee_can_view_upcoming_events_open_for_registration():
    event = catalogue_event()
    response = get_catalogue({"events": [event]})

    assert response.status_code == 200
    assert response.json == {"events": [event]}
    assert response.json["events"][0]["status"] == "confirmed"
    assert response.json["events"][0]["registration_status"] == "open"
    assert response.headers["Cache-Control"] == "no-store"


# AC2: every decision-making event and venue field survives the API boundary.
def test_catalogue_displays_relevant_event_and_venue_information():
    expected = catalogue_event()
    shown = get_catalogue({"events": [expected]}).json["events"][0]

    for field in (
        "event_id", "event_name", "description", "start_datetime",
        "end_datetime", "venue_id", "venue_name", "capacity",
        "available_capacity", "registration_opens_at",
        "registration_closes_at", "waiting_list_enabled",
    ):
        assert shown[field] == expected[field]


# AC3: the route does not cache or replace the latest values returned by the DB.
def test_catalogue_returns_latest_confirmed_event_information_uncached():
    latest = catalogue_event(
        event_name="Updated Technology Fair",
        description="Updated after planning and confirmed",
        start_datetime="2027-01-03T11:00:00+08:00",
        end_datetime="2027-01-03T17:00:00+08:00",
        venue_name="Updated Confirmed Venue",
    )
    response = get_catalogue({"events": [latest]})

    assert response.json["events"] == [latest]
    assert response.headers["Cache-Control"] == "no-store"


# AC4: the database contract represents a fully filtered catalogue as empty;
# the route must not invent stale, cancelled or closed entries.
@pytest.mark.parametrize("excluded_state", ["cancelled", "closed", "not_open"])
def test_unavailable_events_are_absent_from_catalogue(excluded_state):
    response = get_catalogue({"events": []})

    assert response.status_code == 200
    assert response.json == {"events": []}, excluded_state

