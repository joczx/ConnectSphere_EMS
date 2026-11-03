"""SCRUM-9: coordinator review through the API and real test database.

AC1/2: list and read submitted requests and requirements. AC3/4: approve,
reject or request clarification with comments. AC5: persisted outcome and
confirmation response. Browser rendering of messages needs separate UI tests.
Approval moves to planning; clarification keeps submitted with a review row.
Admin access only arranges coordinator assignment and verifies/cleans test data.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.supabase_admin import admin_request, user_id_for


@pytest.fixture
def review_request(client, sign_in):
    marker = f"ITEST-SCRUM-9-{uuid.uuid4().hex}"
    coordinator = user_id_for("Event Coordinator")
    starts = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=60)
    payload = {
        "event_name": marker, "purpose": "Review integration test", "description": marker,
        "event_organiser_id": user_id_for("Event Organiser"),
        "start_datetime": starts.isoformat(),
        "end_datetime": (starts + timedelta(hours=2)).isoformat(),
        "capacity_needed": 40, "room_layout": "theatre",
        "required_facilities": ["projector", "wifi"],
        "equipment_requirements": [
            {"equipment_type": "microphone", "quantity": 2, "notes": "Wireless"}],
        "registration_needs": "Online registration",
        "need_wheelchair_accessibility": True, "need_blind_accessibility": False,
    }
    headers = sign_in("Event Coordinator")
    # Cleanup also runs if setup assertions fail after an unexpected insert.
    try:
        response = client.post("/api/event-requests", headers=sign_in("Event Organiser"),
                               json=payload)
        assert response.status_code == 201, response.get_json()
        request_id = response.get_json()["event_request"]["event_request_id"]
        admin_request(f"/rest/v1/event_request?event_request_id=eq.{request_id}",
                      payload={"event_coordinator_id": coordinator}, method="PATCH")
        yield request_id, payload, headers, coordinator
    finally:
        for row in admin_request(f"/rest/v1/event_request?event_name=eq.{marker}"):
            request_id = row["event_request_id"]
            admin_request(f"/rest/v1/events?event_request_id=eq.{request_id}", method="DELETE")
            admin_request(f"/rest/v1/event_request?event_request_id=eq.{request_id}", method="DELETE")


def _stored(request_id):
    row, = admin_request(f"/rest/v1/event_request?event_request_id=eq.{request_id}")
    return row


def _reviews(request_id):
    return admin_request(f"/rest/v1/event_request_review?event_request_id=eq.{request_id}")


# TC-RER-IT-001 (AC1,2): the assigned coordinator can find and open the request.
def test_coordinator_can_view_submitted_request_and_requirements(client, review_request):
    request_id, payload, headers, _ = review_request
    listed = client.get("/api/event-requests?status=submitted", headers=headers)
    assert listed.status_code == 200, listed.get_json()
    assert request_id in {row["event_request_id"] for row in listed.get_json()["event_requests"]}
    response = client.get(f"/api/event-requests/{request_id}", headers=headers)
    assert response.status_code == 200, response.get_json()
    row = response.get_json()
    assert row["status"] == "submitted"
    for field, expected in payload.items():
        if field.endswith("_datetime"):
            assert datetime.fromisoformat(row[field].replace("Z", "+00:00")) == datetime.fromisoformat(expected)
        else:
            assert row[field] == expected, field


# TC-RER-IT-002..004 (AC3,4,5): each outcome, comment, author and timestamp persist.
@pytest.mark.parametrize("outcome,status,message", [
    ("approved", "planning", "Event request approved."),
    ("rejected", "rejected", "Event request rejected."),
    ("clarification_requested", "submitted", "Clarification requested."),
], ids=["TC-RER-IT-002-approved", "TC-RER-IT-003-rejected", "TC-RER-IT-004-clarification"])
def test_review_outcome_and_comments_are_recorded(client, review_request, outcome, status, message):
    request_id, _, headers, coordinator = review_request
    comment = "Please confirm the equipment and accessibility arrangements."
    before = datetime.now(timezone.utc)
    response = client.post(f"/api/event-requests/{request_id}/review", headers=headers,
                           json={"outcome": outcome, "comments": comment})
    after = datetime.now(timezone.utc)
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == {"message": message}
    assert _stored(request_id)["status"] == status
    recorded, = _reviews(request_id)
    assert recorded["outcome"] == outcome
    assert recorded["comments"] == comment
    assert recorded["reviewer_id"] == coordinator
    assert before <= datetime.fromisoformat(recorded["created_at"].replace("Z", "+00:00")) <= after
    history = client.get(f"/api/event-requests/{request_id}/reviews", headers=headers)
    assert history.status_code == 200, history.get_json()
    assert history.get_json()["reviews"] == [recorded]


# TC-RER-IT-005 (AC3,4): approval does not require an optional comment.
def test_approval_without_comment_succeeds(client, review_request):
    request_id, _, headers, _ = review_request
    response = client.post(f"/api/event-requests/{request_id}/review", headers=headers,
                           json={"outcome": "approved"})
    assert response.status_code == 200, response.get_json()
    assert _stored(request_id)["status"] == "planning"
    recorded, = _reviews(request_id)
    assert recorded["outcome"] == "approved" and recorded["comments"] is None


# TC-RER-IT-006 (AC3,4,5): invalid decisions leave no review or status update.
@pytest.mark.parametrize("body,field", [
    ({"outcome": "rejected"}, "comments"),
    ({"outcome": "clarification_requested", "comments": "   "}, "comments"),
    ({"outcome": "approved", "comments": 42}, "comments"),
    ({"outcome": "unknown"}, "outcome"),
    ({"comments": "No outcome"}, "outcome"),
    ({"outcome": "approved", "reviewer_id": str(uuid.UUID(int=0))}, "_body"),
])
def test_invalid_review_is_refused_without_changes(client, review_request, body, field):
    request_id, _, headers, _ = review_request
    before = _stored(request_id)
    response = client.post(f"/api/event-requests/{request_id}/review", headers=headers, json=body)
    assert response.status_code == 400, response.get_json()
    assert response.get_json()["error"] and field in response.get_json()["errors"]
    assert "message" not in response.get_json()
    assert _stored(request_id) == before
    assert _reviews(request_id) == []


# TC-RER-IT-007 (AC3,5): a final decision cannot be overwritten or duplicated.
@pytest.mark.parametrize("outcome", ["approved", "rejected"])
def test_decided_request_cannot_be_reviewed_again(client, review_request, outcome):
    request_id, _, headers, _ = review_request
    first = client.post(f"/api/event-requests/{request_id}/review", headers=headers,
                        json={"outcome": outcome, "comments": "Decision recorded."})
    assert first.status_code == 200, first.get_json()
    before, history = _stored(request_id), _reviews(request_id)
    second = client.post(f"/api/event-requests/{request_id}/review", headers=headers,
                         json={"outcome": "clarification_requested", "comments": "Another decision"})
    assert second.status_code == 409, second.get_json()
    assert second.get_json()["error"] and "message" not in second.get_json()
    assert _stored(request_id) == before and _reviews(request_id) == history
