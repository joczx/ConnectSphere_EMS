"""Arrange and clean up integration-test data with the secret key.

The secret key bypasses Row Level Security, so use these only for setting up
and removing test data, never for the request under test.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid

import pytest


def admin_request(path, payload=None, method=None):
    """Call the test project's REST API with the secret key, bypassing RLS.

    For arranging and cleaning up test data only. Never use it for the request
    under test, or Row Level Security is not being tested at all.
    """
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return _rest(path, key, key, payload, method)


def delete_as_user(path, auth_header):
    """DELETE through the REST API as a signed-in user.

    Needed for equipment_request: guard_equipment_request_review() returns NEW
    for a secret-key DELETE, which is NULL there, so Postgres silently skips the
    delete. The requester can still delete their own pending request.
    """
    token = auth_header["Authorization"].removeprefix("Bearer ")
    return _rest(path, os.environ["SUPABASE_ANON_KEY"], token, method="DELETE")


def _rest(path, api_key, token, payload=None, method=None):
    method = method or ("GET" if payload is None else "POST")
    request = urllib.request.Request(
        os.environ["SUPABASE_URL"].rstrip("/") + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"apikey": api_key, "Authorization": f"Bearer {token}",
                 "Content-Type": "application/json", "Prefer": "return=representation"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise AssertionError(f"Test setup failed: {method} {path} -> "
                             f"{error.code} {error.read().decode(errors='replace')}") from None
    return json.loads(body) if body else []


def user_id_for(role):
    """The test-project user ID of `role`'s account in .env.integration-test."""
    email = os.environ.get(f"INTEGRATION_{role.upper().replace(' ', '_')}_EMAIL")
    if not email:
        pytest.skip(f"No test account configured for {role}.")
    rows = admin_request(f"/rest/v1/users?select=user_id&email=eq.{urllib.parse.quote(email)}")
    if not rows:
        pytest.skip(f"{email} has no row in public.users in the test project.")
    return rows[0]["user_id"]


def create_technical_support_event(client, sign_in, label, starts_at, ends_at):
    """Create a planning event assigned to the configured Technical Support user.

    The public API performs the Organiser submission and Coordinator approval;
    the service-role client only assigns the known test Technical Support user.
    Call ``delete_test_event`` during fixture cleanup.
    """
    return create_event_assigned_to(
        client, sign_in, label, starts_at, ends_at, "Technical Support Staff",
        purpose="Equipment integration test",
    )


def create_event_assigned_to(client, sign_in, label, starts_at, ends_at, staff_role, *, purpose="Integration test"):
    """Create a planning event and assign one known test staff member to it.

    Submission and approval deliberately use the public API.  The service-role
    request is limited to deterministic assignment for a test that needs a
    particular reviewer, and ``delete_test_event`` removes the result.
    """
    organiser_id = user_id_for("Event Organiser")
    coordinator_id = user_id_for("Event Coordinator")
    staff_columns = {
        "Venue Staff": "venue_staff_id",
        "Technical Support Staff": "technical_support_id",
        "Safety Officer": "safety_officer_id",
    }
    if staff_role not in staff_columns:
        raise ValueError(f"Unsupported staff role {staff_role!r}")
    staff_id = user_id_for(staff_role)
    suffix = uuid.uuid4().hex[:8]
    response = client.post("/api/event-requests", headers=sign_in("Event Organiser"), json={
        "event_name": f"ITEST {label} {suffix}",
        "purpose": purpose,
        "description": "Created by integration tests; removed during fixture cleanup.",
        "event_organiser_id": organiser_id,
        "start_datetime": starts_at.isoformat(),
        "end_datetime": ends_at.isoformat(),
        "capacity_needed": 40,
        "room_layout": "theatre",
        "required_facilities": ["projector"],
        "equipment_requirements": [],
    })
    assert response.status_code == 201, response.get_json()
    request_id = response.get_json()["event_request"]["event_request_id"]

    admin_request(
        f"/rest/v1/event_request?event_request_id=eq.{request_id}",
        {"event_coordinator_id": coordinator_id}, "PATCH",
    )
    approved = client.post(
        f"/api/event-requests/{request_id}/review",
        headers=sign_in("Event Coordinator"), json={"outcome": "approved"},
    )
    assert approved.status_code == 200, approved.get_json()

    events = admin_request(
        f"/rest/v1/events?select=event_id&event_request_id=eq.{request_id}"
    )
    assert len(events) == 1, events
    event_id = events[0]["event_id"]
    admin_request(
        f"/rest/v1/events?event_id=eq.{event_id}",
        {staff_columns[staff_role]: staff_id}, "PATCH",
    )
    return {"event_id": event_id, "event_request_id": request_id}


def delete_test_event(event):
    """Remove an event and all direct reservations made by an integration test."""
    event_id = event["event_id"]
    admin_request(f"/rest/v1/equipment_reservations?event_id=eq.{event_id}", method="DELETE")
    admin_request(f"/rest/v1/events?event_id=eq.{event_id}", method="DELETE")
    admin_request(
        f"/rest/v1/event_request?event_request_id=eq.{event['event_request_id']}",
        method="DELETE",
    )
