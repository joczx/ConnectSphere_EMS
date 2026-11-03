"""SCRUM-8: drafts through the authenticated API and real test database.

AC1: save incomplete requests. AC2: return to and edit saved drafts.
AC3: block submission until complete. AC4: return creation confirmation.
Browser rendering of the confirmation is outside this API integration suite.
All test requests are uniquely labelled and removed during fixture teardown.
"""

import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest

from tests.integration.supabase_admin import admin_request, user_id_for


@pytest.fixture
def drafts(client, sign_in):
    marker = f"ITEST-SCRUM-8-{uuid.uuid4().hex}"
    organiser = user_id_for("Event Organiser")
    headers = sign_in("Event Organiser")
    starts = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=60)
    complete = {
        "event_name": marker,
        "purpose": "Integration testing",
        "description": marker,
        "event_organiser_id": organiser,
        "start_datetime": starts.isoformat(),
        "end_datetime": (starts + timedelta(hours=2)).isoformat(),
        "capacity_needed": 40,
        "room_layout": "theatre",
        "required_facilities": [],
        "equipment_requirements": [],
    }
    minimal = {"event_name": marker, "event_organiser_id": organiser}

    def create(payload):
        response = client.post("/api/event-requests", headers=headers,
                               json={**payload, "save_as_draft": True})
        assert response.status_code == 201, response.get_json()
        return response.get_json()

    def stored(request_id):
        rows = admin_request(
            f"/rest/v1/event_request?event_request_id=eq.{request_id}")
        row, = rows
        return row

    yield headers, minimal, complete, create, stored
    # Either marker survives when a single mandatory field is omitted.
    rows = admin_request(
        f"/rest/v1/event_request?or=(event_name.eq.{quote(marker)},"
        f"description.eq.{quote(marker)})")
    for row in rows:
        admin_request(f"/rest/v1/event_request?event_request_id=eq.{row['event_request_id']}",
                      method="DELETE")


# TC-DER-IT-001 (AC1): only a name and organiser are enough to save a draft.
def test_incomplete_draft_is_persisted(drafts):
    _, minimal, _, create, stored = drafts
    returned = create(minimal)["event_request"]
    assert isinstance(returned["event_request_id"], int)
    row = stored(returned["event_request_id"])
    assert row["event_name"] == minimal["event_name"]
    assert row["event_organiser_id"] == minimal["event_organiser_id"]
    assert row["status"] == returned["status"] == "draft"
    assert row["submitted_at"] is None
    assert row["description"] is None and row["capacity_needed"] is None


# TC-DER-IT-002 (AC4): API provides the creation confirmation for the UI.
def test_draft_creation_returns_confirmation(drafts):
    _, minimal, _, create, stored = drafts
    body = create(minimal)
    assert body["message"] == "Draft event request saved."
    assert stored(body["event_request"]["event_request_id"])["status"] == "draft"


# TC-DER-IT-003 (AC2): return through the list and then retrieve the saved draft.
def test_saved_draft_can_be_listed_and_reopened(client, drafts):
    headers, minimal, _, create, _ = drafts
    request_id = create(minimal)["event_request"]["event_request_id"]
    listed = client.get("/api/event-requests", headers=headers, query_string={
        "event_organiser_id": minimal["event_organiser_id"], "status": "draft",
    })
    assert listed.status_code == 200, listed.get_json()
    assert request_id in {row["event_request_id"] for row in listed.get_json()["event_requests"]}
    reopened = client.get(f"/api/event-requests/{request_id}", headers=headers)
    assert reopened.status_code == 200, reopened.get_json()
    assert reopened.get_json()["event_name"] == minimal["event_name"]
    assert reopened.get_json()["status"] == "draft"


# TC-DER-IT-004 (AC2): partial changes persist without replacing other fields.
def test_saved_draft_can_be_edited_and_reopened(client, drafts):
    headers, minimal, _, create, stored = drafts
    request_id = create(minimal)["event_request"]["event_request_id"]
    changes = {"description": "Updated draft description", "capacity_needed": 75}
    response = client.patch(f"/api/event-requests/{request_id}", headers=headers, json=changes)
    assert response.status_code == 200, response.get_json()
    reopened = client.get(f"/api/event-requests/{request_id}", headers=headers)
    assert reopened.status_code == 200, reopened.get_json()
    for row in (reopened.get_json(), stored(request_id)):
        assert all(row[field] == value for field, value in changes.items())
        assert row["event_name"] == minimal["event_name"]
        assert row["event_organiser_id"] == minimal["event_organiser_id"]
        assert row["status"] == "draft" and row["submitted_at"] is None


# TC-DER-IT-005 (AC3): a minimal draft cannot be submitted.
def test_incomplete_draft_submission_is_refused(client, drafts):
    headers, minimal, _, create, stored = drafts
    request_id = create(minimal)["event_request"]["event_request_id"]
    before = stored(request_id)
    response = client.post(f"/api/event-requests/{request_id}/submit", headers=headers)
    assert response.status_code == 400, response.get_json()
    assert response.get_json()["error"] and response.get_json()["errors"]
    assert "message" not in response.get_json()
    assert stored(request_id) == before


# TC-DER-IT-006 (AC3): each mandatory answer independently blocks submission.
# Explicit list makes the acceptance contract independent of implementation constants.
@pytest.mark.parametrize("field", [
    "event_name", "purpose", "description", "start_datetime", "end_datetime",
    "capacity_needed", "room_layout", "required_facilities", "equipment_requirements",
])
def test_each_missing_mandatory_answer_blocks_draft_submission(client, drafts, field):
    headers, _, complete, create, stored = drafts
    del complete[field]
    request_id = create(complete)["event_request"]["event_request_id"]
    before = stored(request_id)
    response = client.post(f"/api/event-requests/{request_id}/submit", headers=headers)
    assert response.status_code == 400, response.get_json()
    assert response.get_json()["error"]
    assert field in response.get_json()["errors"]
    assert "message" not in response.get_json()
    assert stored(request_id) == before


# TC-DER-IT-007 (AC2,3): finish a saved draft and submit the same request.
def test_completed_draft_submits_and_leaves_draft_list(client, drafts):
    headers, minimal, complete, create, stored = drafts
    request_id = create(minimal)["event_request"]["event_request_id"]
    updated = client.patch(f"/api/event-requests/{request_id}", headers=headers,
                           json={key: value for key, value in complete.items()
                                 if key not in minimal})
    assert updated.status_code == 200, updated.get_json()
    assert stored(request_id)["status"] == "draft"
    before = datetime.now(timezone.utc)
    response = client.post(f"/api/event-requests/{request_id}/submit", headers=headers)
    after = datetime.now(timezone.utc)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["message"] == "Event request submitted successfully."
    row = stored(request_id)
    assert response.get_json()["event_request"]["event_request_id"] == request_id
    assert row["status"] == "submitted"
    assert before <= datetime.fromisoformat(row["submitted_at"].replace("Z", "+00:00")) <= after

    # TC-DER-IT-008 (AC2): draft filtering retains drafts and excludes submissions.
    remaining = create(minimal)["event_request"]["event_request_id"]
    listed = client.get("/api/event-requests", headers=headers, query_string={
        "event_organiser_id": minimal["event_organiser_id"], "status": "draft",
    })
    assert listed.status_code == 200, listed.get_json()
    ids = {item["event_request_id"] for item in listed.get_json()["event_requests"]}
    assert remaining in ids and request_id not in ids
