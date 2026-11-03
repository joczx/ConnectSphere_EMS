"""SCRUM-214: unit tests for setting and updating registration periods.

Covers setting validation, timezone ordering, waiting-list preference validation,
authentication, verified-token forwarding and attendee-facing period responses.
Database timing gates and real lifecycle permissions are tested separately by
frontend/tests/registration-db.mjs.
AC1--AC7 are mapped to API/schema tests below. Timing outcomes and ownership
are mocked RPC decisions, not SQL clock/permission tests. AC7 checks the API
message; visible catalogue wording is rendered by React and is not tested here.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from app import create_app
from app.schemas.registration import parse_settings
from app.services.event_service import EventError
from app.services.event_store import StoreError
from app.services.registration_service import registration_call


@pytest.fixture(autouse=True)
def catalogue_clock():
    with patch('app.services.registration_service._catalogue_now',
               return_value=datetime(2027, 1, 1, 4, tzinfo=timezone.utc)):
        yield


def settings(**changes):
    return {'registration_opens_at': '2027-01-01T10:00:00+08:00',
            'registration_closes_at': '2027-01-02T10:00:00+08:00',
            'waiting_list_enabled': True, **changes}


@pytest.mark.parametrize('changes', [
    {'registration_closes_at': '2027-01-01T02:00:00Z'},
    {'registration_closes_at': '2026-12-31T00:00:00Z'},
    {'registration_opens_at': '2027-01-01T10:00'},
    {'registration_opens_at': None}, {'registration_closes_at': 'invalid'},
    {'waiting_list_enabled': 'true'}, {'waiting_list_enabled': 1},
    {'status': 'confirmed'},
])
def test_invalid_settings(changes):
    assert parse_settings(settings(**changes))[1]


def test_timezone_and_fractional_second_ordering():
    record, errors = parse_settings(settings(registration_closes_at='2027-01-01T02:00:00.100Z'))
    assert not errors
    assert record['registration_opens_at'] == '2027-01-01T02:00:00+00:00'


@pytest.mark.parametrize('method,path', [
    ('patch', '/api/events/1/registration-period'),
])
def test_registration_requires_authentication(method, path):
    client = create_app().test_client()
    with patch('app.services.registration_service.supabase_request') as rpc:
        assert getattr(client, method)(path).status_code == 401
        rpc.assert_not_called()


@pytest.mark.parametrize('waiting_list_enabled', [True, False], ids=['waiting-list-enabled', 'waiting-list-disabled'])
def test_tc_scrum214_001_004_ac1_ac4_set_dates_and_waiting_list(waiting_list_enabled):
    """AC1/AC4: submit opening, closing and either waiting-list preference."""
    client = create_app().test_client()
    payload = settings(waiting_list_enabled=waiting_list_enabled)
    result = {'event': {'event_id': 1, 'status': 'confirmed', **payload}}
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.routes.events.load_event', return_value={'status': 'confirmed'}) as load, \
         patch('app.services.registration_service.supabase_request', return_value=result) as rpc:
        response = client.patch('/api/events/1/registration-period', json=payload,
                                headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == result
    load.assert_called_once_with(1, 'verified')
    rpc.assert_called_once_with('/rest/v1/rpc/set_event_registration_period', token='verified', method='POST',
        payload={'p_event_id': 1, 'p_registration_opens_at': '2027-01-01T02:00:00+00:00',
                 'p_registration_closes_at': '2027-01-02T02:00:00+00:00',
                 'p_waiting_list_enabled': waiting_list_enabled})


def test_database_refusal_without_status_defaults_to_bad_request():
    with patch('app.services.registration_service.supabase_request', return_value={'error': 'Invalid period.'}):
        with pytest.raises(EventError) as caught:
            registration_call('set_event_registration_period', 'verified', {})
    assert caught.value.status == 400
    assert caught.value.to_dict()['error'] == 'Invalid period.'


def test_registration_period_field_errors_are_returned_to_the_organiser():
    client = create_app().test_client()
    error = {'error': 'Registration must close before the event starts.', 'status': 400,
             'errors': {'registration_closes_at': 'Registration must close before the event starts.'}}
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.routes.events.load_event', return_value={'status': 'confirmed'}), \
         patch('app.services.registration_service.supabase_request', return_value=error):
        response = client.patch('/api/events/1/registration-period', json=settings(),
                                headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 400
    assert response.json['errors'] == error['errors']


@pytest.mark.parametrize('closing', [
    pytest.param('2026-12-31T00:00:00Z', id='closing-before-opening'),
    pytest.param('2027-01-01T02:00:00Z', id='closing-equals-opening-in-another-timezone'),
])
def test_tc_scrum214_002_ac2_invalid_order_is_rejected_before_database_call(closing):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.services.registration_service.supabase_request') as rpc:
        response = client.patch('/api/events/1/registration-period',
                                json=settings(registration_closes_at=closing),
                                headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 400
    assert 'registration_closes_at' in response.json['errors']
    rpc.assert_not_called()


@pytest.mark.parametrize('phase', ['before-opening', 'during-registration'])
def test_tc_scrum214_003_ac3_updates_existing_period_when_store_allows_it(phase):
    """AC3: forward updates in both scenarios; SQL decides timing eligibility."""
    client = create_app().test_client()
    now = datetime.now(timezone.utc)
    old_opening = now + timedelta(days=1) if phase == 'before-opening' else now - timedelta(days=1)
    original = {'event_id': 1, 'status': 'confirmed', 'registration_status': 'open',
                'registration_opens_at': old_opening.isoformat(),
                'registration_closes_at': (now + timedelta(days=3)).isoformat(),
                'waiting_list_enabled': False}
    changes = {'registration_opens_at': (old_opening + timedelta(hours=1)).isoformat(),
               'registration_closes_at': (now + timedelta(days=4)).isoformat(),
               'waiting_list_enabled': True}
    updated = {**original, **changes}
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.routes.events.load_event', return_value=original) as load, \
         patch('app.services.registration_service.supabase_request', return_value={'event': updated}) as rpc:
        response = client.patch('/api/events/1/registration-period', json=changes,
                                headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == {'event': updated}
    assert original['registration_opens_at'] != updated['registration_opens_at']
    assert original['registration_closes_at'] != updated['registration_closes_at']
    load.assert_called_once_with(1, 'verified')
    rpc.assert_called_once_with('/rest/v1/rpc/set_event_registration_period', token='verified', method='POST',
        payload={'p_event_id': 1, **{'p_' + field: value for field, value in changes.items()}})


def test_ac3_update_after_period_closed_returns_refusal():
    """Preserve the store's closed-period refusal without claiming a save."""
    client = create_app().test_client()
    message = 'Registration settings can only change before or during registration.'
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.routes.events.load_event', return_value={'status': 'confirmed'}), \
         patch('app.services.registration_service.supabase_request', return_value={'error': message, 'status': 409}):
        response = client.patch('/api/events/1/registration-period', json=settings(),
                                headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 409
    assert response.json == {'error': message}


def test_ac1_unassigned_organiser_cannot_claim_registration_settings_were_saved():
    client = create_app().test_client()
    message = 'Only the assigned Event Organiser can manage registration.'
    with patch('app.routes.events.supabase_request', return_value={'id': 'unassigned'}), \
         patch('app.routes.events.load_event', return_value={'status': 'confirmed'}), \
         patch('app.services.registration_service.supabase_request', return_value={'error': message, 'status': 403}):
        response = client.patch('/api/events/1/registration-period', json=settings(),
                                headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 403
    assert response.json == {'error': message}


@pytest.mark.parametrize('period_state,message', [
    ('not_open', 'Registration is not yet open.'),
    ('closed', 'Registration has closed.'),
    ('open', None),
])
def test_tc_scrum214_005_007_ac5_ac7_registration_outcomes_and_messages(period_state, message):
    """AC5/AC7: return allowed/refused RPC outcomes and exact error wording.

    The API does not evaluate a clock; SQL period boundaries are not exercised.
    """
    client = create_app().test_client()
    details = {'full_name': 'Alex Tan', 'contact_email': 'alex@example.com', 'contact_phone': '+65 8123 4567'}
    result = {'error': message, 'status': 409} if message else {'registration': {'event_id': 1, 'status': 'registered'}}
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value=result) as rpc:
        response = client.post('/api/events/1/registrations', json=details,
                               headers={'Authorization': 'Bearer verified'})
    rpc.assert_called_once_with('/rest/v1/rpc/register_for_event', token='verified', method='POST',
        payload={'p_event_id': 1, **{'p_' + field: value for field, value in details.items()}})
    if period_state == 'open':
        assert response.status_code == 200
        assert response.json == {**result, 'message': 'You are registered for the event.'}
    else:
        assert response.status_code == 409
        assert response.json == {'error': message}
        assert 'registration' not in response.json


def test_tc_scrum214_006_ac6_attendee_reads_updated_period_after_save():
    """AC6: a later attendee read returns supplied updated dates, uncached."""
    client = create_app().test_client()
    original = {'event_id': 1, 'status': 'confirmed', 'registration_status': 'open',
                'start_datetime': '2027-01-03T10:00:00+08:00',
                'end_datetime': '2027-01-03T17:00:00+08:00', **settings()}
    changes = settings(registration_opens_at='2027-01-01T11:00:00+08:00',
                       registration_closes_at='2027-01-02T11:00:00+08:00',
                       waiting_list_enabled=False)
    updated = {**original, **changes}
    with patch('app.routes.events.supabase_request', side_effect=[{'id': 'attendee'}, {'id': 'organiser'}, {'id': 'attendee'}]), \
         patch('app.routes.events.load_event', return_value=original), \
         patch('app.services.registration_service.supabase_request', side_effect=[
             {'events': [original]}, {'event': updated}, {'events': [updated]},
         ]) as rpc:
        before = client.get('/api/registration-events', headers={'Authorization': 'Bearer attendee-token'})
        saved = client.patch('/api/events/1/registration-period', json=changes,
                             headers={'Authorization': 'Bearer organiser-token'})
        after = client.get('/api/registration-events', headers={'Authorization': 'Bearer attendee-token'})
    assert before.status_code == saved.status_code == after.status_code == 200
    assert before.json == {'events': [original]}
    assert saved.json == {'event': updated}
    assert after.json == {'events': [updated]}
    assert before.headers['Cache-Control'] == after.headers['Cache-Control'] == 'no-store'
    assert rpc.call_count == 3
    assert [call.kwargs['token'] for call in rpc.call_args_list] == ['attendee-token', 'organiser-token', 'attendee-token']


@pytest.mark.parametrize('period_state', ['not_open', 'closed'])
def test_ac7_catalogue_hides_future_and_closed_periods(period_state):
    """Before opening and after closing, the event is hidden."""
    client = create_app().test_client()
    event = {'event_id': 1, 'status': 'confirmed',
             'start_datetime': '2027-01-03T10:00:00+08:00',
             'end_datetime': '2027-01-03T17:00:00+08:00', **settings()}
    if period_state == 'not_open':
        event['registration_opens_at'] = '2027-01-01T05:00:00Z'
    else:
        event['registration_closes_at'] = '2027-01-01T03:00:00Z'
    with patch('app.routes.events.supabase_request', return_value={'id': 'attendee'}), \
         patch('app.services.registration_service.supabase_request', return_value={'events': [event]}):
        response = client.get('/api/registration-events', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == {'events': []}


@pytest.mark.parametrize('status', ['planning', 'pending_safety_checks', 'completed', 'cancelled', None])
def test_registration_settings_require_confirmed_event(status):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.routes.events.load_event', return_value={'status': status}) as load, \
         patch('app.services.registration_service.supabase_request') as rpc:
        response = client.patch('/api/events/1/registration-period', json=settings(),
                                headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 409
    assert 'confirmed' in response.json['error']
    load.assert_called_once_with(1, 'verified')
    rpc.assert_not_called()


@pytest.mark.parametrize('failure,message', [
    pytest.param(StoreError(503, code='PGRST202'), 'Registration is not configured yet.', id='TC-SCRUM214-017'),
    pytest.param(StoreError(503), 'Event service is temporarily unavailable.', id='TC-SCRUM214-018'),
])
def test_registration_period_save_failure_is_reported(failure, message):
    """TC-SCRUM214-017/018 / AC1, AC3: when registration is not set up or the
    database is unavailable, the organiser is told the period was not saved
    rather than shown the event as updated."""
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.routes.events.load_event', return_value={'status': 'confirmed'}), \
         patch('app.services.registration_service.supabase_request', side_effect=failure):
        response = client.patch('/api/events/1/registration-period', json=settings(),
                                headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 503
    assert response.json['error'].startswith(message)
    assert 'event' not in response.json
