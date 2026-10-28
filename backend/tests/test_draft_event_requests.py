"""Unit tests for the Draft Event Requests user story.

Each schema, service, workflow or route unit is called directly.
Dependencies are mocked. No HTTP client or database is used.
Browser save/reopen behaviour requires separate acceptance checks.
"""
import pytest
from app.schemas import event_request as schema
from test_create_submit_event_request import valid_payload
from unittest.mock import Mock, patch
from app.services import event_request_service as service
from app.services import event_request_workflow as workflow
from app.routes import event_requests as routes
from flask import Flask


def test_draft_with_no_event_details_can_be_saved():
    organiser = valid_payload()['event_organiser_id']
    table = Mock()
    table.insert.return_value.execute.return_value.data = [{'event_request_id': 42, 'status': 'draft'}]
    with patch.object(service, '_execute', side_effect=lambda operation, **kwargs: operation(table).data):
        service.create_event_request({'event_organiser_id': organiser}, submit=False)
    assert table.insert.call_args.args[0] == {
        'event_organiser_id': organiser, 'status': 'draft',
        'need_wheelchair_accessibility': False, 'need_blind_accessibility': False,
    }


# AC 2: retrieve saved drafts, then edit only the fields supplied.
def test_list_drafts_filters_by_organiser_and_draft_status():
    organiser = valid_payload()['event_organiser_id']
    stored = [{'event_request_id': 42, 'status': 'draft', 'event_name': 'Draft'}]
    table = Mock()
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.execute.return_value.data = stored
    with patch.object(service, '_execute', side_effect=lambda operation, **kwargs: operation(table).data):
        assert service.list_event_requests(organiser, 'draft') == stored
    assert table.eq.call_args_list[0].args == ('event_organiser_id', organiser)
    assert table.eq.call_args_list[1].args == ('status', 'draft')
    table.order.assert_called_once_with('updated_at', desc=True)


@pytest.mark.parametrize('new_value', ['New name', None])
def test_saving_partial_edit_does_not_overwrite_other_draft_fields(new_value):
    existing = {**valid_payload(), 'event_request_id': 42, 'status': 'draft'}
    original = dict(existing)
    table = Mock()
    table.update.return_value.eq.return_value.execute.return_value.data = [{**existing, 'event_name': new_value}]
    with patch.object(service, '_execute', side_effect=lambda operation, **kwargs: operation(table).data), \
         patch.object(service, '_now', return_value='2026-10-05T01:00:00+00:00'):
        row, changes = service.apply_edit(existing, {'event_name': new_value})
    assert table.update.call_args.args[0] == {
        'event_name': new_value, 'updated_at': '2026-10-05T01:00:00+00:00',
    }
    assert changes == {'event_name': {'from': existing['event_name'], 'to': new_value}}
    assert existing == original
    assert row['purpose'] == existing['purpose']
    assert row['status'] == 'draft'
    table.update.return_value.eq.assert_called_once_with('event_request_id', 42)


def test_invalid_draft_edit_never_writes():
    with patch.object(service, '_execute') as write, \
         pytest.raises(service.EventRequestError) as caught:
        service.apply_edit({'event_request_id': 42}, {'capacity_needed': -1})
    assert 'capacity_needed' in caught.value.errors
    write.assert_not_called()


def test_completed_draft_can_proceed_to_submission():
    draft = {**valid_payload(), 'event_request_id': 42, 'status': 'draft'}
    assert service.find_blocking_errors(draft) == {}
    submitted = {**draft, 'status': 'submitted'}
    with patch.object(service, 'require_event_request', return_value=draft), \
         patch.object(service, 'find_blocking_errors', return_value={}), \
         patch.object(service, 'mark_submitted', return_value=submitted) as submit:
        assert workflow.send_for_review(42) == (submitted, False)
    submit.assert_called_once_with(42)


# AC 4: route handlers return a draft-specific confirmation after saving.
def test_create_draft_handler_returns_confirmation():
    payload = {'event_name': 'Draft', 'save_as_draft': True}
    saved = {'event_request_id': 42, 'event_name': 'Draft', 'status': 'draft'}
    with Flask(__name__).test_request_context(json=payload), \
         patch.object(routes, 'create_event_request', return_value=saved) as create:
        response, status = routes.create()
    assert status == 201
    assert response.get_json() == {'message': 'Draft event request saved.', 'event_request': saved}
    create.assert_called_once_with({'event_name': 'Draft'}, submit=False)


def test_edit_draft_handler_returns_confirmation():
    saved = {'event_request_id': 42, 'event_name': 'Updated', 'status': 'draft'}
    with Flask(__name__).test_request_context(json={'event_name': 'Updated'}), \
         patch.object(routes, 'edit_event_request', return_value=(saved, None)) as edit:
        response = routes.edit(42)
    assert response.get_json() == {'message': 'Draft event request saved.', 'event_request': saved}
    edit.assert_called_once_with(42, {'event_name': 'Updated'})


def test_failed_draft_creation_does_not_return_success():
    error = service.EventRequestError('Draft could not be saved.', 502)
    with Flask(__name__).test_request_context(json={'save_as_draft': True}), \
         patch.object(routes, 'create_event_request', side_effect=error), \
         pytest.raises(service.EventRequestError) as caught:
        routes.create()
    assert caught.value is error


def test_a_partially_filled_draft_produces_no_format_errors():
    """Saving a draft should not complain about fields the user has not reached yet."""
    record, errors = schema.parse_payload({"event_name": "Untitled", "purpose": ""})

    assert errors == {}
    assert record == {"event_name": "Untitled", "purpose": None}


# --- Draft Event Requests -------------------------------------------------
# AC: The system allows users to return to and edit their saved drafts.


@pytest.mark.parametrize(
    "field",
    [
        "event_name",
        "purpose",
        "description",
        "start_datetime",
        "end_datetime",
        "capacity_needed",
        "room_layout",
        "registration_needs",
    ],
)
def test_any_optional_field_can_be_cleared_with_null(field):
    """Editing a draft includes removing something entered earlier."""
    record, errors = schema.parse_payload({field: None})

    assert errors == {}
    assert record[field] is None


def test_clearing_the_room_layout_produces_null_not_an_empty_string():
    """room_layout is a PostgreSQL enum, which would reject ""."""
    record, errors = schema.parse_payload({"room_layout": ""})

    assert errors == {}
    assert record["room_layout"] is None


def test_a_cleared_field_still_counts_as_missing_at_submission():
    record, _ = schema.parse_payload(valid_payload(event_name=None))

    assert "event_name" in schema.find_missing(record)


def test_the_organiser_cannot_be_cleared():
    """event_organiser_id is NOT NULL in the database."""
    _, errors = schema.parse_payload({"event_organiser_id": None})

    assert "event_organiser_id" in errors


@pytest.mark.parametrize(
    "field", ["need_wheelchair_accessibility", "need_blind_accessibility"]
)
def test_accessibility_flags_cannot_be_cleared(field):
    """Both are NOT NULL in the database, so null is not a valid answer."""
    _, errors = schema.parse_payload({field: None})

    assert field in errors


