"""SCRUM-7: authenticated API -> real integration-test Supabase database.

AC1-8,10-11 are checked through HTTP responses and persisted rows. The agreed
database status is ``submitted`` (the story calls it Pending). AC9 is covered
only for retrieving a draft before submission; browser preview rendering and
display of confirmation/errors require separate UI tests. No database outage
is induced: failure responses are exercised with rejected submissions.
"""

import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest

from tests.integration.supabase_admin import admin_request, user_id_for


@pytest.fixture
def submission(client, sign_in):
    """Isolate every test by name and clean up even if an assertion fails."""
    name = f"ITEST SCRUM-7 {uuid.uuid4().hex}"
    starts = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=60)
    payload = {
        "event_name": name,
        "purpose": "Integration testing",
        "description": f"{name} removed after the test",
        "event_organiser_id": user_id_for("Event Organiser"),
        "start_datetime": starts.isoformat(),
        "end_datetime": (starts + timedelta(hours=2)).isoformat(),
        "capacity_needed": 40,
        "room_layout": "theatre",
        "required_facilities": ["projector"],
        "equipment_requirements": [
            {"equipment_type": "microphone", "quantity": 2, "notes": "Wireless"},
        ],
        "registration_needs": "Online registration",
        "need_wheelchair_accessibility": True,
        "need_blind_accessibility": False,
    }
    headers = sign_in("Event Organiser")
    description = payload["description"]

    def rows():
        return admin_request(
            f"/rest/v1/event_request?or=(event_name.eq.{quote(name)},"
            f"description.eq.{quote(description)})"
        )

    def post(body):
        return client.post("/api/event-requests", headers=headers, json=body)

    yield payload, post, rows, headers
    # These tests never approve a request, so no operational event is created.
    # Request-linked notifications and history cascade on deletion.
    for row in rows():
        admin_request(
            f"/rest/v1/event_request?event_request_id=eq.{row['event_request_id']}",
            method="DELETE",
        )


def _instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# TC-CER-IT-001: AC1,2,6,7,8,10. Successful submission is actually persisted.
def test_complete_submission_is_persisted_with_confirmation(submission):
    payload, post, rows, _ = submission
    before = datetime.now(timezone.utc)
    response = post(payload)
    after = datetime.now(timezone.utc)

    assert response.status_code == 201, response.get_json()
    body = response.get_json()
    assert body["message"] == "Event request submitted successfully."
    returned = body["event_request"]
    stored, = rows()
    assert returned["event_request_id"] == stored["event_request_id"]
    assert isinstance(stored["event_request_id"], int) and stored["event_request_id"] > 0
    assert returned["status"] == stored["status"] == "submitted"
    assert before <= _instant(stored["submitted_at"]) <= after
    assert _instant(returned["submitted_at"]) == _instant(stored["submitted_at"])
    for field, expected in payload.items():
        if field.endswith("_datetime"):
            assert _instant(stored[field]) == _instant(expected)
        else:
            assert stored[field] == expected, field


# TC-CER-IT-002: AC6. Two real inserts receive different database IDs.
def test_each_submission_receives_a_unique_id(submission):
    payload, post, rows, _ = submission
    responses = [post(payload), post(payload)]
    for response in responses:
        assert response.status_code == 201, response.get_json()
    ids = [response.get_json()["event_request"]["event_request_id"] for response in responses]
    assert len(set(ids)) == 2
    assert {row["event_request_id"] for row in rows()} == set(ids)


# TC-CER-IT-003: AC3,4,11. Every mandatory answer is validated individually.
@pytest.mark.parametrize("field", [
    "event_name", "purpose", "description", "start_datetime", "end_datetime", "capacity_needed",
    "room_layout", "required_facilities", "equipment_requirements", "registration_needs",
    "event_organiser_id",
])
def test_missing_mandatory_field_returns_error_without_creating_row(submission, field):
    payload, post, rows, _ = submission
    del payload[field]
    response = post(payload)
    assert response.status_code == 400, response.get_json()
    body = response.get_json()
    assert body["error"]
    assert field in body["errors"]
    assert "message" not in body and "event_request" not in body
    assert rows() == []


# TC-CER-IT-004: AC5,11. Invalid details cannot produce a stored submission.
@pytest.mark.parametrize("changes,field", [
    ({"capacity_needed": 0}, "capacity_needed"),
    ({"capacity_needed": 1.5}, "capacity_needed"),
    ({"start_datetime": "not-a-date"}, "start_datetime"),
    ({"start_datetime": "2000-01-01T00:00:00Z"}, "start_datetime"),
    ({"end_datetime": "2000-01-01T00:00:00Z"}, "end_datetime"),
    ({"room_layout": "invalid"}, "room_layout"),
    ({"required_facilities": ["invalid"]}, "required_facilities"),
    ({"equipment_requirements": [{"equipment_type": "microphone", "quantity": 0}]},
     "equipment_requirements"),
    ({"status": "planning"}, "_body"),
    ({"event_request_id": 123}, "_body"),
    ({"submitted_at": "2000-01-01T00:00:00Z"}, "_body"),
])
def test_invalid_details_return_error_without_creating_row(submission, changes, field):
    payload, post, rows, _ = submission
    response = post({**payload, **changes})
    assert response.status_code == 400, response.get_json()
    body = response.get_json()
    assert body["error"] and field in body["errors"]
    assert "message" not in body and "event_request" not in body
    assert rows() == []


# TC-CER-IT-005: AC9. Draft details can be read before explicit submission.
def test_organiser_can_read_draft_details_before_submitting(client, submission):
    payload, post, rows, headers = submission
    created = post({**payload, "save_as_draft": True})
    assert created.status_code == 201, created.get_json()
    request_id = created.get_json()["event_request"]["event_request_id"]
    preview = client.get(f"/api/event-requests/{request_id}", headers=headers)
    assert preview.status_code == 200, preview.get_json()
    draft = preview.get_json()
    assert draft["status"] == "draft" and draft["submitted_at"] is None
    for field in ("event_name", "purpose", "description", "capacity_needed",
                  "room_layout", "required_facilities", "equipment_requirements"):
        assert draft[field] == payload[field]
    submitted = client.post(f"/api/event-requests/{request_id}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.get_json()
    stored, = rows()
    assert stored["event_request_id"] == request_id
    assert stored["status"] == "submitted" and stored["submitted_at"]
