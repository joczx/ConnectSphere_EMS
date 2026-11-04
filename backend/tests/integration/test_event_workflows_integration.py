"""Twenty-three real-database integration tests for the core event stories.

Together with the two browser-component tests in
``frontend/tests/event-critical-edit.integration.test.mjs``, this is the
recommended set of 25 integration tests.  Every successful workflow action is
made through the Flask API as the responsible role; the service key is used
only to inspect persisted rows and remove test data.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import uuid

import pytest

from tests.integration.supabase_admin import admin_request, user_id_for
from tests.integration.test_notifications import Flow, submit_for_safety


@pytest.fixture
def flow(client, sign_in):
    actions = Flow(client, sign_in)
    yield actions
    actions.clean()


def request_payload(label, **overrides):
    starts = datetime.now(timezone.utc) + timedelta(days=90)
    payload = {
        "event_name": f"ITEST {label} {uuid.uuid4().hex[:8]}",
        "purpose": "Integration test",
        "description": "Removed automatically after the integration test.",
        "event_organiser_id": user_id_for("Event Organiser"),
        "start_datetime": starts.isoformat(),
        "end_datetime": (starts + timedelta(hours=2)).isoformat(),
        "capacity_needed": 40,
        "room_layout": "theatre",
        "required_facilities": ["projector"],
        "equipment_requirements": [],
    }
    payload.update(overrides)
    return payload


def create_tracked(flow, payload, *, draft=False):
    response = flow.client.post(
        "/api/event-requests",
        headers=flow.sign_in("Event Organiser"),
        json={**payload, "save_as_draft": draft},
    )
    if response.status_code == 201:
        flow.requests.append(response.get_json()["event_request"]["event_request_id"])
    return response


def persisted_request(request_id):
    rows = admin_request(
        f"/rest/v1/event_request?select=*&event_request_id=eq.{request_id}"
    )
    assert len(rows) == 1
    return rows[0]


def arrange_clarification(flow):
    request = flow.submit_request()
    flow.assign(request)
    flow.review(request, "clarification_requested", "Please clarify the purpose.")
    return request


# Create and Submit Event Request (4)

def test_create_submit_persists_complete_request_and_returns_confirmation(flow):
    payload = request_payload("submitted")
    response = create_tracked(flow, payload)

    assert response.status_code == 201, response.get_json()
    body = response.get_json()
    saved = persisted_request(body["event_request"]["event_request_id"])
    detail = flow.call(
        "Event Organiser", "get", f"/api/event-requests/{saved['event_request_id']}"
    )
    assert body["message"] == "Event request submitted successfully."
    assert saved["status"] == "submitted"
    assert saved["submitted_at"]
    assert detail["event_name"] == payload["event_name"]
    assert detail["capacity_needed"] == 40


def test_create_submit_rejects_missing_mandatory_fields_without_writing(flow):
    payload = request_payload("missing-fields")
    event_name = payload["event_name"]
    payload.pop("description")
    payload.pop("room_layout")
    response = create_tracked(flow, payload)

    assert response.status_code == 400
    assert {"description", "room_layout"} <= set(response.get_json()["errors"])
    rows = admin_request(
        f"/rest/v1/event_request?select=event_request_id&event_name=eq.{quote(event_name)}"
    )
    assert rows == []


def test_create_submit_rejects_invalid_dates_and_capacity_without_writing(flow):
    starts = datetime.now(timezone.utc) + timedelta(days=90)
    payload = request_payload(
        "invalid-details",
        start_datetime=starts.isoformat(),
        end_datetime=(starts - timedelta(hours=1)).isoformat(),
    )
    response = create_tracked(flow, payload)

    assert response.status_code == 400
    assert "end_datetime" in response.get_json()["errors"]
    rows = admin_request(
        f"/rest/v1/event_request?select=event_request_id&event_name=eq.{quote(payload['event_name'])}"
    )
    assert rows == []


def test_create_submit_translates_database_foreign_key_failure(flow):
    payload = request_payload("database-refusal", event_organiser_id=str(uuid.uuid4()))
    response = create_tracked(flow, payload)

    assert response.status_code == 502
    assert "database" in response.get_json()["error"].lower()
    rows = admin_request(
        f"/rest/v1/event_request?select=event_request_id&event_name=eq.{quote(payload['event_name'])}"
    )
    assert rows == []


# Draft Event Requests (3)

def test_draft_saves_incomplete_request_with_draft_status(flow):
    payload = request_payload("incomplete-draft")
    payload.pop("description")
    response = create_tracked(flow, payload, draft=True)

    assert response.status_code == 201, response.get_json()
    body = response.get_json()
    saved = persisted_request(body["event_request"]["event_request_id"])
    assert body["message"] == "Draft event request saved."
    assert saved["status"] == "draft"
    assert saved["description"] is None
    assert saved["submitted_at"] is None


def test_draft_can_be_listed_edited_and_reviewed_before_submission(flow):
    draft = flow.submit_request(draft=True)
    request_id = draft["event_request_id"]
    before = persisted_request(request_id)
    listed = flow.call(
        "Event Organiser",
        "get",
        f"/api/event-requests?event_organiser_id={before['event_organiser_id']}&status=draft",
    )["event_requests"]
    response = flow.call(
        "Event Organiser",
        "patch",
        f"/api/event-requests/{request_id}",
        {"description": "Updated while still a draft."},
    )
    after = persisted_request(request_id)

    assert request_id in {row["event_request_id"] for row in listed}
    assert response["message"] == "Draft event request saved."
    assert after["description"] == "Updated while still a draft."
    assert after["event_name"] == before["event_name"]
    assert after["status"] == "draft"


def test_incomplete_draft_cannot_be_submitted_and_remains_draft(flow):
    payload = request_payload("blocked-draft")
    payload.pop("description")
    created = create_tracked(flow, payload, draft=True).get_json()["event_request"]
    response = flow.client.post(
        f"/api/event-requests/{created['event_request_id']}/submit",
        headers=flow.sign_in("Event Organiser"),
        json={},
    )

    assert response.status_code == 400
    assert "description" in response.get_json()["errors"]
    assert persisted_request(created["event_request_id"])["status"] == "draft"


# Review and Approve Event Request (2)

def test_assigned_coordinator_can_list_and_open_submitted_request(flow):
    request = flow.submit_request()
    flow.assign(request)
    listed = flow.call(
        "Event Coordinator", "get", "/api/event-requests?status=submitted"
    )["event_requests"]
    detail = flow.call(
        "Event Coordinator",
        "get",
        f"/api/event-requests/{request['event_request_id']}",
    )

    assert request["event_request_id"] in {
        row["event_request_id"] for row in listed
    }
    assert detail["event_name"] == request["event_name"]
    assert detail["event_coordinator_id"] == user_id_for("Event Coordinator")


def test_review_outcomes_persist_status_comments_and_confirmation(flow):
    cases = [
        ("approved", None, "planning", "Event request approved."),
        ("rejected", "Insufficient information.", "rejected", "Event request rejected."),
        (
            "clarification_requested",
            "Please clarify the audience.",
            "submitted",
            "Clarification requested.",
        ),
    ]
    for outcome, comments, status, message in cases:
        request = flow.submit_request()
        flow.assign(request)
        response = flow.call(
            "Event Coordinator",
            "post",
            f"/api/event-requests/{request['event_request_id']}/review",
            {"outcome": outcome, **({"comments": comments} if comments else {})},
        )
        reviews = flow.call(
            "Event Coordinator",
            "get",
            f"/api/event-requests/{request['event_request_id']}/reviews",
        )["reviews"]
        assert response["message"] == message
        assert persisted_request(request["event_request_id"])["status"] == status
        assert reviews[0]["outcome"] == outcome
        assert reviews[0]["comments"] == comments


# Amend Event Request (4)

def test_clarification_allows_organiser_to_update_relevant_details(flow):
    request = arrange_clarification(flow)
    response = flow.call(
        "Event Organiser",
        "patch",
        f"/api/event-requests/{request['event_request_id']}",
        {"description": "Clarified event purpose.", "note": "Updated as requested."},
    )

    assert response["message"] == "Amendment saved. Resubmit the request when you are ready."
    assert response["event_request"]["description"] == "Clarified event purpose."
    assert persisted_request(request["event_request_id"])["status"] == "submitted"


def test_amended_request_can_be_opened_and_reviewed_before_resubmission(flow):
    request = arrange_clarification(flow)
    flow.call(
        "Event Organiser",
        "patch",
        f"/api/event-requests/{request['event_request_id']}",
        {"purpose": "Clarified integration purpose."},
    )
    detail = flow.call(
        "Event Organiser",
        "get",
        f"/api/event-requests/{request['event_request_id']}",
    )

    assert detail["purpose"] == "Clarified integration purpose."
    assert detail["event_name"] == request["event_name"]


def test_amended_request_can_be_resubmitted_for_coordinator_review(flow):
    request = arrange_clarification(flow)
    flow.call(
        "Event Organiser",
        "patch",
        f"/api/event-requests/{request['event_request_id']}",
        {"description": "Clarification supplied."},
    )
    response = flow.call(
        "Event Organiser",
        "post",
        f"/api/event-requests/{request['event_request_id']}/submit",
        {},
    )

    assert response["message"] == "Event request resubmitted successfully."
    assert response["event_request"]["status"] == "submitted"
    assert persisted_request(request["event_request_id"])["status"] == "submitted"


def test_amendment_audit_row_records_actor_note_and_before_after_values(flow):
    request = arrange_clarification(flow)
    old_description = request["description"]
    flow.call(
        "Event Organiser",
        "patch",
        f"/api/event-requests/{request['event_request_id']}",
        {"description": "Audited clarification.", "note": "This answers the question."},
    )
    rows = admin_request(
        "/rest/v1/event_request_amendment?select=*&"
        f"event_request_id=eq.{request['event_request_id']}&order=created_at.desc&limit=1"
    )

    assert len(rows) == 1
    assert rows[0]["amended_by"] == user_id_for("Event Organiser")
    assert rows[0]["note"] == "This answers the question."
    assert rows[0]["changes"]["description"] == {
        "from": old_description,
        "to": "Audited clarification.",
    }


# Submit Event Change Request (3 backend; two frontend tests complete its 5)

def test_important_change_is_pending_review_and_does_not_update_event(flow):
    event = flow.event()
    change = flow.change(event, "Attendance increased.", {"capacity_needed": 55})
    saved_event = admin_request(
        f"/rest/v1/events?select=capacity_needed&event_id=eq.{event['event_id']}"
    )[0]

    assert change["status"] == "pending_review"
    assert change["changes"]["capacity_needed"] == {"from": 40, "to": 55}
    assert saved_event["capacity_needed"] == 40


def test_change_request_rejects_no_op_without_creating_row(flow):
    event = flow.event()
    response = flow.client.post(
        f"/api/events/{event['event_id']}/change-requests",
        headers=flow.sign_in("Event Organiser"),
        json={
            "reason": "No actual difference.",
            "proposed_values": {"event_name": event["event_name"]},
            "expected_event_updated_at": event["updated_at"],
        },
    )

    assert response.status_code == 400
    assert "change" in response.get_json()["error"].lower()
    rows = admin_request(
        f"/rest/v1/event_change_request?select=event_change_request_id&event_id=eq.{event['event_id']}"
    )
    assert rows == []


def test_change_request_rejects_blank_reason_without_creating_row(flow):
    event = flow.event()
    response = flow.client.post(
        f"/api/events/{event['event_id']}/change-requests",
        headers=flow.sign_in("Event Organiser"),
        json={
            "reason": "   ",
            "proposed_values": {"capacity_needed": 55},
            "expected_event_updated_at": event["updated_at"],
        },
    )

    assert response.status_code == 400
    assert "reason" in response.get_json()["errors"]
    rows = admin_request(
        f"/rest/v1/event_change_request?select=event_change_request_id&event_id=eq.{event['event_id']}"
    )
    assert rows == []


# Review Event Change Request (4)

def test_coordinator_queue_and_detail_show_changed_fields_and_impacts(flow):
    event = flow.event()
    change = flow.change(event, "Attendance increased.", {"capacity_needed": 55})
    request_id = change["event_change_request_id"]
    queue = flow.call(
        "Event Coordinator", "get", "/api/event-change-requests?status=pending_review"
    )["change_requests"]
    detail = flow.call(
        "Event Coordinator", "get", f"/api/event-change-requests/{request_id}"
    )

    listed = next(row for row in queue if row["event_change_request_id"] == request_id)
    assert "capacity_needed" in listed["changed_fields"]
    assert listed["preparation_impacts"]
    assert detail["change_request"]["event_change_request_id"] == request_id
    assert "capacity_needed" in detail["change_request"]["changes"]
    assert detail["preparation_impacts"]
    flow.decide_change(change, "reject", "Test cleanup decision.")


def test_non_important_change_is_auto_approved_and_applied(flow):
    event = flow.event()
    new_description = "An updated non-critical description."
    change = flow.change(event, "Improve the description.", {"description": new_description})
    saved_event = admin_request(
        f"/rest/v1/events?select=description&event_id=eq.{event['event_id']}"
    )[0]
    pending = flow.call(
        "Event Coordinator", "get", "/api/event-change-requests?status=pending_review"
    )["change_requests"]

    assert change["status"] == "approved"
    assert saved_event["description"] == new_description
    assert change["event_change_request_id"] not in {
        row["event_change_request_id"] for row in pending
    }


def test_approving_important_change_updates_event_and_records_critical_edit(flow):
    event = flow.event()
    change = flow.change(event, "Attendance increased.", {"capacity_needed": 55})
    flow.decide_change(change, "approve")
    saved_event = admin_request(
        f"/rest/v1/events?select=capacity_needed&event_id=eq.{event['event_id']}"
    )[0]
    saved_change = admin_request(
        "/rest/v1/event_change_request?select=status&"
        f"event_change_request_id=eq.{change['event_change_request_id']}"
    )[0]
    activity = admin_request(
        "/rest/v1/event_activity?select=change_type,changes,event_change_request_id&"
        f"event_change_request_id=eq.{change['event_change_request_id']}"
    )

    assert saved_event["capacity_needed"] == 55
    assert saved_change["status"] == "approved"
    assert activity == [{
        "change_type": "critical_edit",
        "changes": {"capacity_needed": {"from": 40, "to": 55}},
        "event_change_request_id": change["event_change_request_id"],
    }]


def test_rejecting_important_change_requires_reason_and_keeps_event_unchanged(flow):
    event = flow.event()
    change = flow.change(event, "Attendance increased.", {"capacity_needed": 55})
    path = f"/api/event-change-requests/{change['event_change_request_id']}/decision"
    refused = flow.client.post(
        path,
        headers=flow.sign_in("Event Coordinator"),
        json={"decision": "reject", "reason": ""},
    )
    accepted = flow.call(
        "Event Coordinator",
        "post",
        path,
        {"decision": "reject", "reason": "Capacity cannot be supported."},
    )
    saved_event = admin_request(
        f"/rest/v1/events?select=capacity_needed&event_id=eq.{event['event_id']}"
    )[0]

    assert refused.status_code == 400
    assert "reason" in refused.get_json()["errors"]
    assert accepted["change_request"]["status"] == "rejected"
    assert accepted["change_request"]["decision_reason"] == "Capacity cannot be supported."
    assert saved_event["capacity_needed"] == 40


# Event Status Management (3)

def test_review_decisions_transition_submitted_request_to_planning_or_rejected(flow):
    for outcome, expected in (("approved", "planning"), ("rejected", "rejected")):
        request = flow.submit_request()
        flow.assign(request)
        flow.review(
            request,
            outcome,
            None if outcome == "approved" else "Cannot approve this request.",
        )
        assert persisted_request(request["event_request_id"])["status"] == expected
        if outcome == "approved":
            event = admin_request(
                f"/rest/v1/events?select=status&event_request_id=eq.{request['event_request_id']}"
            )
            assert event == [{"status": "planning"}]


def test_safety_approval_transitions_event_to_confirmed_and_api_returns_latest_status(flow):
    event = submit_for_safety(flow)
    response = flow.call(
        "Safety Officer",
        "post",
        f"/api/operational-safety-reviews/{event['event_id']}/decision",
        {"outcome": "approved"},
    )
    detail = flow.call(
        "Event Coordinator", "get", f"/api/events/{event['event_id']}"
    )["event"]

    assert response["event"]["status"] == "confirmed"
    assert detail["status"] == "confirmed"
    assert admin_request(
        f"/rest/v1/events?select=status&event_id=eq.{event['event_id']}"
    ) == [{"status": "confirmed"}]


def test_failed_safety_submission_returns_error_and_retains_previous_status(flow):
    event = flow.event()
    response = flow.client.post(
        f"/api/events/{event['event_id']}/safety-checks",
        headers=flow.sign_in("Event Coordinator"),
        json={},
    )

    assert response.status_code == 409
    assert response.get_json()["error"]
    assert admin_request(
        f"/rest/v1/events?select=status&event_id=eq.{event['event_id']}"
    ) == [{"status": "planning"}]
