"""HTTP boundary tests: malformed IDs, missing bodies and service refusals."""
from unittest.mock import Mock

import pytest
from app import create_app
from app.routes import coordinator_lead, equipment, event_requests, events, login, notifications, users, venue_bookings, venues
from app.services.event_store import StoreError
from app.services.event_service import EventError
from app.services.event_request_service import EventRequestError


@pytest.fixture
def client(monkeypatch):
    for module in (coordinator_lead, equipment, event_requests, events, users, venue_bookings, venues):
        monkeypatch.setattr(module, 'authenticated_token', lambda *args: 'token')
    monkeypatch.setattr(events, 'authenticated_user', lambda *args: ('token', 'actor'))
    monkeypatch.setattr(event_requests, 'authenticated_user', lambda *args: ('token', 'actor'))
    app = create_app()
    app.config['TESTING'] = True
    return app.test_client()


def test_api_home(client):
    assert client.get('/').json == {'message': 'ConnectSphere Flask API is running!'}


def test_lead_rejects_missing_body_and_nonpositive_event_id(client):
    assert client.patch('/api/coordinator-lead/event-requests/1/coordinator').status_code == 400
    assert client.patch('/api/coordinator-lead/events/0/coordinator').status_code == 404


@pytest.mark.parametrize('error,status,text', [
    (StoreError(503, code='23514'), 409, 'Reserve matching'),
    (StoreError(503, code='PGRST202'), 503, '036'),
    (StoreError(403), 403, 'permission'),
])
def test_equipment_reservation_errors_are_actionable(client, monkeypatch, error, status, text):
    monkeypatch.setattr(equipment, 'supabase_request', Mock(side_effect=error))
    response = client.post('/api/equipment-request-reviews/46/reservation', json={'equipment_id': 1, 'quantity': 2})
    assert response.status_code == status
    assert text in response.json['error']


def test_request_cancel_success_and_lifecycle_error(client, monkeypatch):
    call = Mock(return_value={'cancelled': True})
    monkeypatch.setattr(event_requests, 'lifecycle_call', call)
    assert client.post('/api/event-requests/1/cancel').json == {'cancelled': True}
    call.assert_called_with('cancel_event_request', 'token', {'p_request_id': 1})
    call.side_effect = EventError('Cannot cancel', 409)
    assert client.post('/api/event-requests/1/cancel').status_code == 409


def test_request_listing_validates_organiser(client, monkeypatch):
    listing = Mock(return_value=[])
    monkeypatch.setattr(event_requests, 'list_event_requests', listing)
    assert client.get('/api/event-requests?event_organiser_id=invalid').status_code == 400
    owner = '00000000-0000-0000-0000-000000000001'
    assert client.get('/api/event-requests?event_organiser_id=' + owner).status_code == 200
    listing.assert_called_once_with(owner, None)


def test_request_missing_bodies_and_missing_record(client, monkeypatch):
    assert client.patch('/api/event-requests/1').status_code == 400
    assert client.post('/api/event-requests/1/review').status_code == 400
    monkeypatch.setattr(event_requests, 'get_event_request', lambda _: None)
    assert client.get('/api/event-requests/1').status_code == 404


def test_request_amendment_delete_submit_and_history(client, monkeypatch):
    amendment = {'amendment_id': 1}
    monkeypatch.setattr(event_requests, 'edit_event_request', lambda *args: ({'event_request_id': 1}, amendment))
    assert client.patch('/api/event-requests/1', json={'note': 'Reply'}).json['amendment'] == amendment
    delete = Mock()
    monkeypatch.setattr(event_requests, 'delete_draft', delete)
    assert client.delete('/api/event-requests/1').status_code == 200
    delete.assert_called_once_with(1)
    monkeypatch.setattr(event_requests, 'send_for_review', lambda _: ({'event_request_id': 1}, True, [{'recipient_id': 'c'}]))
    response = client.post('/api/event-requests/1/submit')
    assert response.json['notified'] == ['c']
    assert 'resubmitted' in response.json['message']
    monkeypatch.setattr(event_requests, 'list_amendments', lambda _: [amendment])
    assert client.get('/api/event-requests/1/amendments').json == {'count': 1, 'amendments': [amendment]}


@pytest.mark.parametrize('error,status', [(StoreError(503, code='23514'), 409), (StoreError(403), 403)])
def test_event_store_refusals(client, monkeypatch, error, status):
    monkeypatch.setattr(events, 'supabase_request', Mock(side_effect=error))
    assert client.get('/api/events').status_code == status


def test_event_edit_rejects_invalid_id_and_body(client, monkeypatch):
    assert client.patch('/api/events/bad', json={}).status_code == 404
    assert client.patch('/api/events/1').status_code == 400
    update = Mock(return_value=({'event_id': 1}, None))
    monkeypatch.setattr(events, 'update_event', update)
    response = client.patch('/api/events/1', json={'event_name': 'New', 'confirm_critical': True, 'expected_updated_at': 'version'})
    assert response.json['message'] == 'No changes to save.'
    update.assert_called_once_with('1', {'event_name': 'New'}, 'token', True, 'version', 'actor')


def test_event_activity_and_coordinator_validation(client, monkeypatch):
    assert client.get('/api/events/bad/activity').status_code == 404
    monkeypatch.setattr(events, 'list_activity', lambda *args: [{'activity_id': 1}])
    assert client.get('/api/events/1/activity').json['activity'] == [{'activity_id': 1}]
    assert client.patch('/api/events/bad/coordinator', json={}).status_code == 404
    assert client.patch('/api/events/1/coordinator', json={}).status_code == 400
    monkeypatch.setattr(events, 'supabase_request', lambda *args, **kwargs: [])
    assert client.patch('/api/events/1/coordinator', json={'event_coordinator_id': 'someone'}).status_code == 404


def test_refresh_requires_token_and_reports_auth_service_failure(client, monkeypatch):
    assert client.post('/api/refresh', json={}).status_code == 400
    monkeypatch.setattr(login, 'supabase_request', Mock(side_effect=StoreError(503, 'Unavailable')))
    response = client.post('/api/refresh', json={'refresh_token': 'refresh'})
    assert response.status_code == 503 and response.json['error'] == 'Unavailable'


@pytest.mark.parametrize('error,status', [(StoreError(401), 401), (EventRequestError('Invalid recipient'), 400)])
def test_notification_error_responses(client, monkeypatch, error, status):
    monkeypatch.setattr(notifications, 'authenticated_user', Mock(side_effect=error))
    assert client.get('/api/notifications').status_code == status


def test_user_filter_validation_and_query(client, monkeypatch):
    assert client.get('/api/users?ids=1&role=event_coordinator').status_code == 400
    assert client.get('/api/users?role=unsupported').status_code == 400
    query = Mock(return_value=[{'user_id': '1', 'name': 'Alice'}, {'user_id': '2', 'email': '   '}])
    monkeypatch.setattr(users, 'supabase_request', query)
    assert client.get('/api/users?ids=1,,2').json['users'] == {'1': 'Alice'}
    assert 'user_id=in.(1,2)' in query.call_args.args[0]
    assert client.get('/api/users').json['users'] == {'1': 'Alice'}
    assert 'order=name.asc' in query.call_args.args[0]
    query.side_effect = StoreError(503)
    assert client.get('/api/users').status_code == 503


@pytest.mark.parametrize('method,path,body', [
    ('get', '/api/venue-bookings', None), ('get', '/api/venue-bookings/alerts', None),
    ('post', '/api/venue-bookings/alerts/dismiss', {'notification_ids': [1]}),
])
def test_booking_read_and_alert_refusals(client, monkeypatch, method, path, body):
    monkeypatch.setattr(venue_bookings, 'rpc', lambda *args: {'error': 'Not yours', 'status': 403})
    response = getattr(client, method)(path, json=body)
    assert response.status_code == 403 and response.json == {'error': 'Not yours'}


@pytest.mark.parametrize('method,path', [('get', '/api/venue-bookings/bad'), ('post', '/api/venue-bookings/bad/hold'), ('delete', '/api/venue-bookings/bad/hold')])
def test_booking_ids_must_be_uuid(client, method, path):
    assert getattr(client, method)(path).status_code == 404


def test_venue_helpers_and_event_context_errors(client, monkeypatch):
    query = Mock(return_value=[])
    monkeypatch.setattr(venues, 'supabase_request', query)
    assert venues.upcoming_approved_bookings('venue', 'token') == []
    assert query.call_args.kwargs['token'] == 'token'
    venue_id = '00000000-0000-0000-0000-000000000001'
    query.return_value = [{'venue_id': venue_id}]
    assert client.get(f'/api/venues/{venue_id}?event_id=bad').status_code == 404
    monkeypatch.setattr(venues, 'load_event', Mock(side_effect=EventError('Not found', 404)))
    assert client.get(f'/api/venues/{venue_id}?event_id=1').status_code == 404
