"""Review and Approve Event Request user-story tests.

Schema tests check validation and mappings; HTTP tests check routes/services
with mocked Supabase. One strict expected failure documents the known AC6 gap.
Browser rendering and live database delivery require separate acceptance checks.
"""
from unittest.mock import Mock, patch
import pytest
from flask import Flask
from app.schemas import event_request as request_schema
from app.schemas import event_request_review as review
from app.routes.event_requests import event_requests_bp
from app.services import db
from app.services import event_request_review_service as review_service
from test_create_submit_event_request import valid_payload

COORDINATOR = '3f1b9c64-7a2e-4d51-9b0f-2c8e5a6d4f10'


# HTTP acceptance checks (AC1-AC6)

@pytest.fixture
def review_http():
    app = Flask(__name__)
    app.register_blueprint(event_requests_bp)
    database = Mock()
    table = database.table.return_value
    for method in ('select', 'eq', 'order', 'limit', 'insert', 'update'):
        getattr(table, method).return_value = table
    table.execute.return_value.data = []
    with patch.object(db, 'get_supabase', return_value=database), \
         patch.object(review_service, 'get_supabase', return_value=database), \
         patch('app.routes.event_requests.authenticated_user', return_value=('user-token', COORDINATOR)):
        yield app.test_client(), table


def test_ac1_http_lists_submitted_requests(review_http):
    http, table = review_http
    row = {**valid_payload(), 'event_request_id': 42, 'status': 'submitted'}
    table.execute.return_value.data = [row]
    response = http.get('/api/event-requests?status=submitted')
    assert response.status_code == 200
    assert response.json == {'event_requests': [row]}
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
    old = {**valid_payload(), 'event_request_id': 42, 'status': 'submitted', 'event_coordinator_id': COORDINATOR}
    payload = {'outcome': outcome, 'comments': 'Reduce attendance.'}
    recorded = {**payload, 'reviewer_id': COORDINATOR, 'review_id': 7, 'event_request_id': 42, 'created_at': '2026-10-05T00:00:00Z'}
    updated = {**old, 'status': review.OUTCOME_TO_STATUS[outcome]}
    def execute():
        if table.execute.call_count <= 3:
            return Mock(data=[[old], [recorded], [updated]][table.execute.call_count - 1])
        return Mock(data=table.insert.call_args.args[0])
    table.execute.side_effect = execute
    response = http.post('/api/event-requests/42/review', json=payload)
    assert response.status_code == 200
    assert ('approved' if outcome == 'approved' else 'rejected') in response.json['message']
    assert table.insert.call_args_list[0].args[0] == {**payload, 'reviewer_id': COORDINATOR, 'event_request_id': 42}
    assert table.update.call_args.args[0]['status'] == updated['status']
    assert table.update.call_args.args[0]['updated_at']
    notification = next(n for n in table.insert.call_args.args[0] if n['recipient_id'] == old['event_organiser_id'])
    assert notification['event_request_id'] == 42
    assert notification['notification_type'] == 'event_request_' + outcome
    assert old['event_name'] in notification['message']
    table.execute.side_effect = [Mock(data=[updated]), Mock(data=[recorded])]
    assert http.get('/api/event-requests/42/reviews').json['reviews'] == [recorded]


@pytest.mark.parametrize('comments', [None, '', '   '])
def test_ac4_rejection_requires_reason_before_any_write(review_http, comments):
    http, table = review_http
    response = http.post('/api/event-requests/42/review', json={
        'outcome': 'rejected', 'comments': comments})
    assert response.status_code == 400
    assert 'comments' in response.json['errors']
    table.execute.assert_not_called()


def test_ac5_failed_review_insert_has_error_and_no_confirmation(review_http):
    http, table = review_http
    table.execute.side_effect = [Mock(data=[{'status': 'submitted', 'event_coordinator_id': COORDINATOR}]), Mock(data=[])]
    response = http.post('/api/event-requests/42/review', json={'outcome': 'approved'})
    assert response.status_code == 502
    assert 'error' in response.json and 'message' not in response.json
    table.update.assert_not_called()


def test_ac5_empty_status_update_must_not_confirm_success(review_http):
    http, table = review_http
    old = {'event_request_id': 42, 'status': 'submitted', 'event_coordinator_id': COORDINATOR}
    table.execute.side_effect = [Mock(data=[old]), Mock(data=[{'outcome': 'approved'}]), Mock(data=[]), Mock(data=[])]
    response = http.post('/api/event-requests/42/review', json={'outcome': 'approved'})
    assert response.status_code == 409
    assert 'message' not in response.json


def test_ac6_failed_notification_must_not_claim_organiser_was_notified(review_http):
    http, table = review_http
    table.execute.side_effect = [Mock(data=[{'status': 'submitted', 'event_coordinator_id': COORDINATOR}]), Mock(data=[{'outcome': 'approved'}]),
        Mock(data=[{'event_request_id': 42, 'status': review.OUTCOME_TO_STATUS['approved']}]), RuntimeError('offline')]
    response = http.post('/api/event-requests/42/review', json={'outcome': 'approved'})
    assert response.status_code == 200
    assert table.update.call_args.args[0]['status'] == review.OUTCOME_TO_STATUS['approved']
    assert 'has been notified' not in response.json['message']

