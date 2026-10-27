"""Failure and concurrency cases without a live database."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import db
from app.services import event_request_service as service
from app.services import event_request_workflow as workflow
from app.services import event_request_review_service as reviews


@pytest.fixture
def table(monkeypatch):
    table = Mock()
    for method in ('insert', 'update', 'delete', 'select', 'eq', 'order', 'limit'):
        getattr(table, method).return_value = table
    table.execute.return_value.data = [{'event_request_id': 1}]
    client = Mock()
    client.table.return_value = table
    monkeypatch.setattr(db, 'get_supabase', lambda: client)
    return table


def test_edit_preserves_owner_and_records_only_changed_fields(table):
    owner = '00000000-0000-0000-0000-000000000001'
    existing = dict(event_request_id=1, event_organiser_id=owner, event_name='Old')
    row, changes = service.apply_edit(existing, {'event_organiser_id': owner, 'event_name': 'New'})
    assert row['event_request_id'] == 1
    assert changes == {'event_name': {'from': 'Old', 'to': 'New'}}
    assert 'event_organiser_id' not in table.update.call_args.args[0]
    with pytest.raises(service.EventRequestError) as error:
        service.apply_edit(existing, {'event_organiser_id': '00000000-0000-0000-0000-000000000002'})
    assert 'event_organiser_id' in error.value.errors
    with pytest.raises(service.EventRequestError, match='No changes'):
        service.apply_edit(existing, {})


def test_empty_writes_are_not_reported_as_success(table):
    table.execute.return_value.data = []
    with pytest.raises(service.EventRequestError) as error:
        service.apply_edit({'event_request_id': 1}, {'event_name': 'New'})
    assert error.value.status_code == 502
    with pytest.raises(service.EventRequestError) as error:
        service.mark_submitted(1)
    assert error.value.status_code == 502


def test_submit_fetch_and_missing_request(table):
    assert service.mark_submitted(1)['event_request_id'] == 1
    assert table.update.call_args.args[0]['status'] == 'submitted'
    assert service.require_event_request(1)['event_request_id'] == 1
    table.execute.return_value.data = []
    with pytest.raises(service.EventRequestError) as error:
        service.require_event_request(1)
    assert error.value.status_code == 404


@pytest.mark.parametrize('status,deleted,allowed', [('submitted', [], False), ('draft', [], False), ('draft', [{'id': 1}], True)])
def test_delete_draft_handles_concurrent_submission(monkeypatch, table, status, deleted, allowed):
    monkeypatch.setattr(service, 'require_event_request', lambda _: {'status': status})
    table.execute.return_value.data = deleted
    if allowed:
        assert service.delete_draft(1) is None
        table.eq.assert_any_call('status', 'draft')
    else:
        with pytest.raises(service.EventRequestError) as error:
            service.delete_draft(1)
        assert error.value.status_code == 409


def test_invalid_list_status_is_rejected_before_query(table):
    with pytest.raises(service.EventRequestError, match='Status must'):
        service.list_event_requests(status='unknown')
    table.execute.assert_not_called()


def test_request_database_errors_are_translated():
    error = service._translate(RuntimeError('offline'), 'save')
    assert error.status_code == 502


def test_database_exception_preserves_cause(monkeypatch):
    original = RuntimeError('offline')
    monkeypatch.setattr(db, 'get_supabase', Mock(side_effect=original))
    with pytest.raises(service.EventRequestError) as error:
        service.get_event_request(1)
    assert error.value.status_code == 502
    assert error.value.__cause__ is original


@pytest.mark.parametrize('status', ['submitted', 'planning'])
def test_workflow_refuses_edit_and_resubmit_without_clarification(monkeypatch, status):
    monkeypatch.setattr(service, 'require_event_request', lambda _: {'event_request_id': 1, 'status': status})
    monkeypatch.setattr(reviews, 'latest_review', lambda _: None)
    for action in (lambda: workflow.edit(1, {'event_name': 'New'}), lambda: workflow.send_for_review(1)):
        with pytest.raises(service.EventRequestError) as error:
            action()
        assert error.value.status_code == 409


def test_amend_rejected_request_and_record_amendment(monkeypatch, table):
    existing = {'event_request_id': 1, 'event_organiser_id': 'owner', 'status': 'rejected'}
    monkeypatch.setattr(service, 'require_event_request', lambda _: existing)
    monkeypatch.setattr(service, 'apply_edit', lambda *args: ({'event_name': 'New'}, {'event_name': {'from': 'Old', 'to': 'New'}}))
    row, amendment = workflow.edit(1, {'event_name': 'New', 'note': ' Reply '})
    assert row['event_name'] == 'New'
    assert amendment['event_request_id'] == 1
    assert table.insert.call_args.args[0]['note'] == 'Reply'
    assert table.insert.call_args.args[0]['amended_by'] == 'owner'
    assert workflow._split_note(None) == (None, None)


def test_draft_edits_do_not_create_amendments_and_incomplete_drafts_cannot_submit(monkeypatch):
    row = {'event_request_id': 1, 'status': 'draft'}
    monkeypatch.setattr(service, 'require_event_request', lambda _: row)
    monkeypatch.setattr(service, 'apply_edit', lambda *args: (row, {}))
    assert workflow.edit(1, {'event_name': 'New'}) == (row, None)
    monkeypatch.setattr(service, 'find_blocking_errors', lambda _: {'purpose': 'Required'})
    with pytest.raises(service.EventRequestError) as error:
        workflow.send_for_review(1)
    assert error.value.errors == {'purpose': 'Required'}



def test_review_missing_request_and_history(monkeypatch, table):
    monkeypatch.setattr(reviews, 'get_event_request', lambda _: None)
    with pytest.raises(service.EventRequestError) as error:
        reviews.review_event_request(1, {'outcome': 'approved'}, '00000000-0000-0000-0000-000000000001')
    assert error.value.status_code == 404
    with pytest.raises(service.EventRequestError) as error:
        reviews.list_reviews(1)
    assert error.value.status_code == 404
    assert reviews.latest_review(1) == {'event_request_id': 1}
    table.limit.assert_called_with(1)
    assert 'draft' in reviews._why_not_reviewable('draft')
    assert 'approved' in reviews._why_not_reviewable('planning')
    assert 'rejected' in reviews._why_not_reviewable('rejected')


@pytest.mark.parametrize('code,message,status,field', [
    ('23503', 'unknown', 400, 'reviewer_id'), ('23514', 'reason_required', 400, 'comments'),
    ('23514', 'other', 409, None), ('42501', 'forbidden', 403, None), (None, 'offline', 502, None),
])
def test_review_database_errors(code, message, status, field):
    error = reviews._translate_review_error(SimpleNamespace(code=code, message=message), 'review')
    assert error.status_code == status
    if field:
        assert field in error.errors

