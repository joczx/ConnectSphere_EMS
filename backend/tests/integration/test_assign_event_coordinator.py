"""SCRUM-219 Assign an Event Coordinator to a Requested Event, on the real test project.

Integration rather than unit tests because these rules live in the database:
the queue and assignment functions and their role checks.
tests/test_event_request_assignment.py already covers the Flask routes with Supabase mocked.

Every action goes through the API as the role that takes it. The secret key is
used only to arrange, to read back what was saved, and to clean up.

  AC1  New requests go to an unassigned queue, not to any Event Coordinator.
  AC2  The Lead can view the queue, including basic event information.
  AC3  The Lead can assign a queued request to an available Event Coordinator.
  AC4  The event is updated, leaves the queue, and a confirmation is given.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.supabase_admin import admin_request, user_id_for


def _starts():
    return datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=60)


def _remove_request(request_id):
    admin_request(f"/rest/v1/events?event_request_id=eq.{request_id}", method="DELETE")
    admin_request(f"/rest/v1/event_request?event_request_id=eq.{request_id}", method="DELETE")


@pytest.fixture
def queued_request(client, sign_in):
    """A request the Organiser has just submitted through the API."""
    starts = _starts()
    response = client.post("/api/event-requests", headers=sign_in("Event Organiser"), json={
        "event_name": f"ITEST coordinator queue {uuid.uuid4().hex[:8]}",
        "purpose": "Integration test",
        "description": "Created by test_coordinator_assignment.py; removed afterwards.",
        "event_organiser_id": user_id_for("Event Organiser"),
        "start_datetime": starts.isoformat(),
        "end_datetime": (starts + timedelta(hours=3)).isoformat(),
        "capacity_needed": 40,
        "room_layout": "theatre",
        "required_facilities": ["projector"],
        "equipment_requirements": [],
    })
    assert response.status_code == 201, response.get_json()
    request = response.get_json()["event_request"]
    yield request
    _remove_request(request["event_request_id"])


def _queue(client, sign_in):
    response = client.get("/api/event-requests/unassigned",
                          headers=sign_in("Event Coordinator Lead"))
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def _queued_ids(client, sign_in):
    return {row["event_request_id"] for row in _queue(client, sign_in)["event_requests"]}


def _assign(client, sign_in, request_id, coordinator_id, role="Event Coordinator Lead"):
    return client.post(f"/api/event-requests/{request_id}/assign-coordinator",
                       headers=sign_in(role), json={"coordinator_id": coordinator_id})


def _saved_coordinator(request_id):
    rows = admin_request("/rest/v1/event_request?select=event_coordinator_id"
                         f"&event_request_id=eq.{request_id}")
    return rows[0]["event_coordinator_id"]


# TC-ECA-001 (AC1, happy): a newly submitted request has no Event Coordinator
# and is placed in the unassigned queue.
def test_new_request_is_unassigned_and_queued(client, sign_in, queued_request):
    request_id = queued_request["event_request_id"]

    assert _saved_coordinator(request_id) is None
    assert request_id in _queued_ids(client, sign_in)


# TC-ECA-002 (AC2, happy): the Lead sees the queued request's basic event
# information, and the Event Coordinators available to choose from.
def test_lead_sees_basic_information_in_the_queue(client, sign_in, queued_request):
    queue = _queue(client, sign_in)

    row = next(item for item in queue["event_requests"]
               if item["event_request_id"] == queued_request["event_request_id"])
    assert row["event_name"] == queued_request["event_name"]
    assert row["capacity_needed"] == 40
    assert row["start_datetime"] and row["end_datetime"]
    assert user_id_for("Event Coordinator") in {item["id"] for item in queue["coordinators"]}


# TC-ECA-003 (AC2, negative): an Event Coordinator cannot open the queue.
def test_coordinator_cannot_view_the_queue(client, sign_in):
    response = client.get("/api/event-requests/unassigned", headers=sign_in("Event Coordinator"))

    assert response.status_code == 403, response.get_json()
    assert "event_requests" not in response.get_json()


# TC-ECA-004 (AC3, AC4, happy): the Lead assigns a queued request: it is
# saved with that Coordinator, leaves the queue, and a confirmation is returned.
def test_lead_assigns_request_and_it_leaves_the_queue(client, sign_in, queued_request):
    request_id = queued_request["event_request_id"]
    coordinator = user_id_for("Event Coordinator")

    response = _assign(client, sign_in, request_id, coordinator)

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["message"] == "Event Coordinator assigned successfully."
    assert _saved_coordinator(request_id) == coordinator
    assert request_id not in _queued_ids(client, sign_in)


# TC-ECA-005 (AC3, negative): an Event Coordinator cannot assign a request,
# even to themselves, and it stays in the queue.
def test_coordinator_cannot_assign_a_request(client, sign_in, queued_request):
    request_id = queued_request["event_request_id"]

    response = _assign(client, sign_in, request_id, user_id_for("Event Coordinator"),
                       role="Event Coordinator")

    assert response.status_code == 403, response.get_json()
    assert _saved_coordinator(request_id) is None
    assert request_id in _queued_ids(client, sign_in)


# TC-ECA-006 (AC3, negative): a request cannot be assigned to someone who is
# not an Event Coordinator.
def test_request_cannot_be_assigned_to_another_role(client, sign_in, queued_request):
    request_id = queued_request["event_request_id"]

    response = _assign(client, sign_in, request_id, user_id_for("Attendee"))

    assert response.status_code == 400, response.get_json()
    assert _saved_coordinator(request_id) is None


# TC-ECA-007 (AC3, negative): a request already assigned is no longer
# available, so assigning it again is refused and changes nothing.
def test_assigned_request_cannot_be_assigned_again(client, sign_in, queued_request):
    request_id = queued_request["event_request_id"]
    coordinator = user_id_for("Event Coordinator")
    first = _assign(client, sign_in, request_id, coordinator)
    assert first.status_code == 200, first.get_json()

    response = _assign(client, sign_in, request_id, coordinator)

    assert response.status_code == 409, response.get_json()
    assert _saved_coordinator(request_id) == coordinator
