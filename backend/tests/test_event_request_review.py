"""Review and Approve Event Request user-story tests.

Schema tests check validation and mappings; HTTP tests check routes/services
with mocked Supabase. Two strict expected failures document known AC5/AC6 gaps.
Browser rendering and live database delivery require separate acceptance checks.
"""
from unittest.mock import Mock, patch
import pytest
from flask import Flask
from app.schemas import event_request as request_schema
from app.schemas import event_request_review as review
from app.routes.event_requests import event_requests_bp
from app.routes.notifications import notifications_bp
from app.services import db
from app.services import event_request_review_service as review_service
from test_create_submit_event_request import valid_payload

COORDINATOR = '3f1b9c64-7a2e-4d51-9b0f-2c8e5a6d4f10'


# Schema validation and outcome rules

# AC: The Event Coordinator can approve, reject, or request clarification.
@pytest.mark.parametrize("outcome", sorted(review.OUTCOMES))
def test_each_outcome_is_accepted(outcome):
    record, errors = review.parse_payload(
        {"reviewer_id": COORDINATOR, "outcome": outcome, "comments": "Looks reasonable."}
    )

    assert errors == {}
    assert record["outcome"] == outcome
    assert record["reviewer_id"] == COORDINATOR


def test_an_unknown_outcome_is_rejected():
    _, errors = review.parse_payload({"reviewer_id": COORDINATOR, "outcome": "maybe"})

    assert "outcome" in errors


def test_an_outcome_is_required():
    _, errors = review.parse_payload({"reviewer_id": COORDINATOR})

    assert "outcome" in errors


def test_a_reviewer_is_required():
    _, errors = review.parse_payload({"outcome": "approved"})

    assert "reviewer_id" in errors


def test_the_reviewer_must_be_a_user_id():
    _, errors = review.parse_payload({"reviewer_id": "seven", "outcome": "approved"})

    assert "reviewer_id" in errors


# AC: The Event Coordinator can add comments along with the outcome.
def test_comments_are_kept_with_the_outcome():
    record, errors = review.parse_payload(
        {"reviewer_id": COORDINATOR, "outcome": "approved", "comments": "  Approved for Hall A. "}
    )

    assert errors == {}
    assert record["comments"] == "Approved for Hall A."


def test_approving_without_a_comment_is_allowed():
    record, errors = review.parse_payload({"reviewer_id": COORDINATOR, "outcome": "approved"})

    assert errors == {}
    assert record["comments"] is None


@pytest.mark.parametrize("outcome", sorted(review.OUTCOMES_NEEDING_COMMENTS))
def test_a_reason_is_required_when_not_approving(outcome):
    """An Organiser told "rejected" with no reason has nothing to act on."""
    _, errors = review.parse_payload({"reviewer_id": COORDINATOR, "outcome": outcome})

    assert "comments" in errors


@pytest.mark.parametrize("outcome", sorted(review.OUTCOMES_NEEDING_COMMENTS))
def test_a_blank_reason_does_not_count(outcome):
    _, errors = review.parse_payload(
        {"reviewer_id": COORDINATOR, "outcome": outcome, "comments": "   "}
    )

    assert "comments" in errors


def test_comments_must_be_text():
    _, errors = review.parse_payload(
        {"reviewer_id": COORDINATOR, "outcome": "approved", "comments": 42}
    )

    assert "comments" in errors


def test_unknown_fields_are_rejected():
    _, errors = review.parse_payload(
        {"reviewer_id": COORDINATOR, "outcome": "approved", "decision": "yes"}
    )

    assert "_body" in errors


def test_a_non_object_body_is_rejected():
    _, errors = review.parse_payload("approved")

    assert "_body" in errors


# AC: The system records the outcome of the review.
def test_approving_moves_the_request_into_planning():
    """An approved event is one whose arrangements are now being planned."""
    assert review.OUTCOME_TO_STATUS["approved"] == request_schema.STATUS_PLANNING


def test_rejecting_moves_the_request_to_rejected():
    assert review.OUTCOME_TO_STATUS["rejected"] == request_schema.STATUS_REJECTED


def test_requesting_clarification_leaves_the_request_submitted():
    """Clarification is a sub-state, not a status: the decision is still open."""
    assert (
        review.OUTCOME_TO_STATUS["clarification_requested"]
        == request_schema.STATUS_SUBMITTED
    )


def test_every_outcome_maps_to_a_status():
    assert set(review.OUTCOME_TO_STATUS) == review.OUTCOMES


def test_every_mapped_status_exists_in_the_database_enum():
    assert set(review.OUTCOME_TO_STATUS.values()) <= request_schema.ALL_STATUSES


# AC: The system allows Event Coordinators to view submitted event requests.
def test_only_submitted_requests_can_be_reviewed():
    assert review.REVIEWABLE_STATUSES == {request_schema.STATUS_SUBMITTED}


def test_a_draft_is_not_reviewable():
    assert request_schema.STATUS_DRAFT not in review.REVIEWABLE_STATUSES


@pytest.mark.parametrize("status", ["planning", "rejected", "cancelled"])
def test_an_already_decided_request_is_not_reviewable(status):
    assert status not in review.REVIEWABLE_STATUSES


# AC: The Event Organiser should be notified of the outcome.
@pytest.mark.parametrize("outcome", sorted(review.OUTCOMES))
def test_both_parties_get_a_message_for_every_outcome(outcome):
    organiser_text, reviewer_text = review.describe(outcome, "Orientation Night")

    assert "Orientation Night" in organiser_text
    assert "Orientation Night" in reviewer_text
    assert organiser_text != reviewer_text


def test_messages_survive_a_request_with_no_name():
    organiser_text, reviewer_text = review.describe("approved", None)

    assert organiser_text and reviewer_text


# HTTP acceptance checks (AC1-AC6)

@pytest.fixture
def review_http():
    app = Flask(__name__)
    app.register_blueprint(event_requests_bp)
    app.register_blueprint(notifications_bp)
    database = Mock()
    table = database.table.return_value
    for method in ('select', 'eq', 'order', 'limit', 'insert', 'update'):
        getattr(table, method).return_value = table
    table.execute.return_value.data = []
    with patch.object(db, 'get_supabase', return_value=database), \
         patch.object(review_service, 'get_supabase', return_value=database), \
         patch('app.routes.notifications.get_supabase', return_value=database):
        yield app.test_client(), table


def test_ac1_http_lists_submitted_requests(review_http):
    http, table = review_http
    row = {**valid_payload(), 'event_request_id': 42, 'status': 'submitted'}
    table.execute.return_value.data = [row]
    response = http.get('/api/event-requests?status=submitted')
    assert response.status_code == 200
    assert response.json == {'count': 1, 'event_requests': [row]}
    table.eq.assert_called_with('status', 'submitted')


def test_ac2_http_returns_every_event_detail_and_requirement(review_http):
    http, table = review_http
    row = {**valid_payload(), 'event_request_id': 42, 'status': 'submitted'}
    table.execute.return_value.data = [row]
    response = http.get('/api/event-requests/42')
    assert response.status_code == 200
    assert response.json == row
    table.eq.assert_called_with('event_request_id', 42)


@pytest.mark.parametrize('outcome', ['approved', 'rejected'])
def test_ac3_ac4_ac5_ac6_review_persists_decision_and_notifies_organiser(review_http, outcome):
    http, table = review_http
    old = {**valid_payload(), 'event_request_id': 42, 'status': 'submitted'}
    payload = {'reviewer_id': COORDINATOR, 'outcome': outcome, 'comments': 'Reduce attendance.'}
    recorded = {**payload, 'review_id': 7, 'event_request_id': 42, 'created_at': '2026-10-05T00:00:00Z'}
    updated = {**old, 'status': review.OUTCOME_TO_STATUS[outcome]}
    def execute():
        if table.execute.call_count <= 3:
            return Mock(data=[[old], [recorded], [updated]][table.execute.call_count - 1])
        return Mock(data=table.insert.call_args.args[0])
    table.execute.side_effect = execute
    response = http.post('/api/event-requests/42/review', json=payload)
    assert response.status_code == 200
    assert response.json['event_request'] == updated
    assert response.json['review'] == recorded
    assert ('approved' if outcome == 'approved' else 'rejected') in response.json['message']
    assert table.insert.call_args_list[0].args[0] == {**payload, 'event_request_id': 42}
    assert table.update.call_args.args[0]['status'] == updated['status']
    assert table.update.call_args.args[0]['updated_at']
    notification = next(n for n in table.insert.call_args.args[0] if n['recipient_id'] == old['event_organiser_id'])
    assert notification['event_request_id'] == 42
    assert notification['notification_type'] == 'event_request_' + outcome
    assert old['event_name'] in notification['message']
    assert old['event_organiser_id'] in response.json['notified']
    table.execute.side_effect = [Mock(data=[updated]), Mock(data=[recorded])]
    assert http.get('/api/event-requests/42/reviews').json['reviews'] == [recorded]
    table.execute.side_effect = None
    table.execute.return_value.data = [notification]
    response = http.get('/api/notifications?recipient_id=' + old['event_organiser_id'])
    assert response.status_code == 200
    assert response.json['notifications'] == [notification]
    table.eq.assert_called_with('recipient_id', old['event_organiser_id'])


@pytest.mark.parametrize('comments', [None, '', '   '])
def test_ac4_rejection_requires_reason_before_any_write(review_http, comments):
    http, table = review_http
    response = http.post('/api/event-requests/42/review', json={
        'reviewer_id': COORDINATOR, 'outcome': 'rejected', 'comments': comments})
    assert response.status_code == 400
    assert 'comments' in response.json['errors']
    table.execute.assert_not_called()


def test_ac5_failed_review_insert_has_error_and_no_confirmation(review_http):
    http, table = review_http
    table.execute.side_effect = [Mock(data=[{'status': 'submitted'}]), Mock(data=[])]
    response = http.post('/api/event-requests/42/review', json={'reviewer_id': COORDINATOR, 'outcome': 'approved'})
    assert response.status_code == 502
    assert 'error' in response.json and 'message' not in response.json
    table.update.assert_not_called()


@pytest.mark.xfail(strict=True, reason='AC5 gap: empty status update returns success with unchanged status.')
def test_ac5_empty_status_update_must_not_confirm_success(review_http):
    http, table = review_http
    old = {'event_request_id': 42, 'status': 'submitted'}
    table.execute.side_effect = [Mock(data=[old]), Mock(data=[{'outcome': 'approved'}]), Mock(data=[]), Mock(data=[])]
    response = http.post('/api/event-requests/42/review', json={'reviewer_id': COORDINATOR, 'outcome': 'approved'})
    assert response.status_code == 502
    assert 'message' not in response.json


@pytest.mark.xfail(strict=True, reason='AC6 gap: confirmation claims delivery when notification storage fails.')
def test_ac6_failed_notification_must_not_claim_organiser_was_notified(review_http):
    http, table = review_http
    table.execute.side_effect = [Mock(data=[{'status': 'submitted'}]), Mock(data=[{'outcome': 'approved'}]),
        Mock(data=[{'event_request_id': 42, 'status': review.OUTCOME_TO_STATUS['approved']}]), RuntimeError('offline')]
    response = http.post('/api/event-requests/42/review', json={'reviewer_id': COORDINATOR, 'outcome': 'approved'})
    assert response.status_code == 200
    assert response.json['event_request']['status'] == review.OUTCOME_TO_STATUS['approved']
    assert response.json['notified'] == []
    assert 'has been notified' not in response.json['message']
