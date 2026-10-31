"""Approving an event request assigns its staff, against the real test project.

Requires 043_auto_assign_event_staff.sql to have been run in the test project,
and at least one user holding each of Venue Staff, Technical Support Staff and
Safety Officer there (the INTEGRATION_* accounts are enough).

The Organiser submits a request through the API, the Event Coordinator
reviews it through the API, and the result is read back both through the API
and, for the row counts, with the secret key so Row Level Security cannot hide
a duplicate. The secret key is used only to arrange and clean up.

Each test is labelled with its test case ID and the acceptance criterion it
covers from the user story "As an authorised user, I want the system to
automatically assign Venue Staff, Technical Support Staff, and a Safety
Officer to an approved event so that the relevant staff can manage venue
arrangements, technical requirements, and operational safety":

  AC1  The system automatically and randomly assigns the relevant Venue Staff,
       Technical Support Staff, and Safety Officer when an event request is
       approved.
  AC2  The system records the assigned staff members and updates the event
       information accordingly.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.supabase_admin import admin_request, user_id_for

# The events column each role is assigned to, and the role names that count
# (compared like has_booking_role(): lower case, spaces as underscores).
STAFF = {
    "venue_staff_id": {"venue_staff"},
    "technical_support_id": {"technical_support_staff", "technical_support"},
    "safety_officer_id": {"safety_officer"},
}


def _role_key(name):
    return name.strip().lower().replace(" ", "_")


def _role_holders():
    """{role key: set of user ids} for every role in the test project."""
    holders = {}
    for row in admin_request("/rest/v1/user_roles?select=user_id,roles(role_name)"):
        name = (row.get("roles") or {}).get("role_name")
        if name:
            holders.setdefault(_role_key(name), set()).add(row["user_id"])
    return holders


def _events_for(request_id):
    return admin_request(f"/rest/v1/events?select=*&event_request_id=eq.{request_id}")


def _submit_request(client, sign_in, label):
    """Submit a complete request as the Organiser, reviewed by our Coordinator."""
    starts = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=60)
    response = client.post("/api/event-requests", headers=sign_in("Event Organiser"), json={
        "event_name": f"ITEST auto-assign {label} {uuid.uuid4().hex[:8]}",
        "purpose": "Integration test",
        "description": "Created by test_auto_assign_event_staff.py; removed afterwards.",
        "event_organiser_id": user_id_for("Event Organiser"),
        "start_datetime": starts.isoformat(),
        "end_datetime": (starts + timedelta(hours=3)).isoformat(),
        "capacity_needed": 40,
        "room_layout": "theatre",
        "required_facilities": ["projector"],
        "equipment_requirements": [],
    })
    assert response.status_code == 201, response.get_json()
    request_id = response.get_json()["event_request"]["event_request_id"]

    # Arrange: a coordinator is picked at random on insert; hand the request
    # to the test Coordinator so that account can review it.
    admin_request(
        f"/rest/v1/event_request?event_request_id=eq.{request_id}",
        payload={"event_coordinator_id": user_id_for("Event Coordinator")}, method="PATCH",
    )
    return request_id


def _review(client, sign_in, request_id, outcome, comments=None):
    body = {"outcome": outcome, **({"comments": comments} if comments else {})}
    return client.post(f"/api/event-requests/{request_id}/review",
                       headers=sign_in("Event Coordinator"), json=body)


def _remove(request_id):
    # Reviews, notifications and amendments cascade from the request; the
    # event's history, registrations and change requests from the event.
    admin_request(f"/rest/v1/events?event_request_id=eq.{request_id}", method="DELETE")
    admin_request(f"/rest/v1/event_request?event_request_id=eq.{request_id}", method="DELETE")


@pytest.fixture
def new_request(client, sign_in):
    """Submit requests for one test, and remove them and their events after."""
    created = []

    def _new(label):
        request_id = _submit_request(client, sign_in, label)
        created.append(request_id)
        return request_id

    yield _new
    for request_id in created:
        _remove(request_id)


@pytest.fixture
def approved(client, sign_in, new_request):
    """An approved request and the one event approval created for it."""
    request_id = new_request("approved")
    response = _review(client, sign_in, request_id, "approved")
    assert response.status_code == 200, response.get_json()
    events = _events_for(request_id)
    assert len(events) == 1, events
    return request_id, events[0]


# TC-AAS-001 (AC1): approving the request creates exactly one event, and it is
# given a Venue Staff, a Technical Support Staff and a Safety Officer, each a
# user who holds that role.
def test_approval_assigns_one_user_of_each_staff_role(approved):
    _, event = approved
    holders = _role_holders()

    for column, roles in STAFF.items():
        candidates = set().union(*(holders.get(role, set()) for role in roles))
        if not candidates:
            pytest.skip(f"No user holds {' or '.join(sorted(roles))} in the test project.")
        assert event[column] in candidates, f"{column}={event[column]!r} does not hold {roles}"


# TC-AAS-002 (AC1): the assignment happens on approval, without anyone
# choosing the staff: the reviewer only sends the outcome.
def test_staff_are_assigned_by_the_system_not_the_reviewer(approved):
    request_id, event = approved

    request = admin_request(f"/rest/v1/event_request?select=status&event_request_id=eq.{request_id}")
    assert request[0]["status"] == "planning"
    assert all(event[column] for column in STAFF), {column: event[column] for column in STAFF}


# TC-AAS-003 (AC2): the assigned staff are recorded on the event, and the
# event information the Coordinator opens shows them.
def test_event_information_shows_the_assigned_staff(client, sign_in, approved):
    _, event = approved

    response = client.get(f"/api/events/{event['event_id']}", headers=sign_in("Event Coordinator"))

    assert response.status_code == 200, response.get_json()
    shown = response.get_json()["event"]
    for column in STAFF:
        assert shown[column] == event[column]




