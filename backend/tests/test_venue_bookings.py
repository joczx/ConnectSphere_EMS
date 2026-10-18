from unittest.mock import patch
import pytest
from app import create_app
from app.schemas.venue_booking import parse_booking
from app.services.event_store import StoreError

VALID = dict(venue_id='b21bdd3b-5fbb-4588-b070-f9a7e923ef02', event_id=4, event_name='Workshop',
             starts_at='2099-01-01T10:00:00+08:00', ends_at='2099-01-01T12:00:00+08:00',
             attendance=40, venue_requirements='Classroom layout and wheelchair access')
HEADERS = {'Authorization': 'Bearer coordinator-token'}


@pytest.mark.parametrize('field', VALID)
def test_every_booking_field_is_required(field):
    body = dict(VALID)
    del body[field]
    assert field in parse_booking(body)[1]


@pytest.mark.parametrize('changes,field', [
    ({'attendance': True}, 'attendance'), ({'attendance': 1.5}, 'attendance'),
    ({'attendance': 0}, 'attendance'), ({'attendance': 2147483648}, 'attendance'),
    ({'event_name': '  '}, 'event_name'), ({'venue_requirements': 'x' * 5001}, 'venue_requirements'),
    ({'venue_id': 'bad'}, 'venue_id'), ({'starts_at': '2099-01-01T10:00'}, 'starts_at'),
    ({'starts_at': '2000-01-01T10:00+08:00'}, 'starts_at'),
    ({'ends_at': VALID['starts_at']}, 'ends_at'),
    ({'event_id': '4'}, 'event_id'), ({'event_id': 0}, 'event_id'),
    ({'event_id': True}, 'event_id'), ({'event_id': 4.0}, 'event_id'),
])
def test_invalid_booking_details(changes, field):
    assert field in parse_booking({**VALID, **changes})[1]


def test_valid_payload_ignores_forged_owner_and_status():
    data, errors = parse_booking({**VALID, 'requested_by': 'another-user', 'status': 'approved'})
    assert not errors
    assert set(data) == set(VALID)


@patch('app.routes.venue_bookings.supabase_request')
def test_authentication_required(query):
    client = create_app().test_client()
    assert client.post('/api/venue-bookings', json=VALID).status_code == 401
    assert client.get('/api/venue-bookings').status_code == 401
    query.assert_not_called()


@patch('app.routes.venue_bookings.supabase_request', return_value={'id': 'coordinator'})
def test_invalid_submission_never_writes(query):
    response = create_app().test_client().post('/api/venue-bookings', json={}, headers=HEADERS)
    assert response.status_code == 400
    assert query.call_count == 1


@patch('app.routes.venue_bookings.supabase_request')
def test_submission_confirms_persisted_request(query):
    query.side_effect = [{'id': 'coordinator'}, {**VALID, 'booking_id': 'saved-id', 'status': 'submitted'}]
    response = create_app().test_client().post('/api/venue-bookings', json=VALID, headers=HEADERS)
    assert response.status_code == 201
    assert response.json['booking']['booking_id'] == 'saved-id'
    assert 'Venue Staff' in response.json['message']
    assert query.call_args.args[0] == '/rest/v1/rpc/submit_venue_booking'
    assert query.call_args.kwargs['token'] == 'coordinator-token'
    assert response.headers['Cache-Control'] == 'no-store'


@patch('app.routes.venue_bookings.supabase_request')
def test_database_role_denial_is_not_success(query):
    query.side_effect = [{'id': 'organiser'}, {'error': 'Only Event Coordinators can submit venue bookings.', 'status': 403}]
    response = create_app().test_client().post('/api/venue-bookings', json=VALID, headers=HEADERS)
    assert response.status_code == 403
    assert 'booking' not in response.json


@patch('app.routes.venue_bookings.supabase_request')
def test_staff_receives_review_details(query):
    query.side_effect = [{'id': 'staff'}, {'bookings': [VALID], 'can_review': True, 'can_submit': False}]
    response = create_app().test_client().get('/api/venue-bookings', headers=HEADERS)
    assert response.status_code == 200
    assert response.json['bookings'][0] == VALID
    assert query.call_args.args[0] == '/rest/v1/rpc/list_venue_bookings'
    assert query.call_args.kwargs['token'] == 'coordinator-token'


@patch('app.routes.venue_bookings.supabase_request')
def test_storage_failure_has_no_confirmation(query):
    query.side_effect = [{'id': 'coordinator'}, StoreError(503)]
    response = create_app().test_client().post('/api/venue-bookings', json=VALID, headers=HEADERS)
    assert response.status_code == 503
    assert 'booking' not in response.json


@patch('app.routes.venue_bookings.supabase_request')
def test_request_names_the_event_it_is_for(query):
    query.side_effect = [{'id': 'coordinator'}, {**VALID, 'booking_id': 'saved-id'}]
    create_app().test_client().post('/api/venue-bookings', json=VALID, headers=HEADERS)
    assert query.call_args.kwargs['payload']['p_booking']['event_id'] == 4


@patch('app.routes.venue_bookings.supabase_request')
def test_unsuitable_venue_is_refused_with_its_shortfalls(query):
    # The search page greys the venue out, but the rule is the database's, so
    # the refusal has to reach the coordinator rather than be swallowed as a
    # generic failure.
    query.side_effect = [{'id': 'coordinator'}, {
        'error': 'This venue does not meet the requirements recorded for this event.',
        'unmet_requirements': ['Holds 80, but 400 are expected.'],
        'status': 409,
    }]
    response = create_app().test_client().post('/api/venue-bookings', json=VALID, headers=HEADERS)
    assert response.status_code == 409
    assert response.json['unmet_requirements'] == ['Holds 80, but 400 are expected.']
    assert 'booking' not in response.json


MODIFY = {'venue_id': VALID['venue_id'], 'venue_requirements': 'Classroom layout'}
BOOKING = '3cf6f106-e05a-45ce-a6e5-825afcbf23cd'


@pytest.mark.parametrize('body', [{}, {**MODIFY, 'venue_id': 'bad'}, {**MODIFY, 'venue_requirements': ' '}])
@patch('app.routes.venue_bookings.supabase_request', return_value={'id': 'coordinator'})
def test_invalid_modification_never_writes(query, body):
    response = create_app().test_client().patch(f'/api/venue-bookings/{BOOKING}', json=body, headers=HEADERS)
    assert response.status_code == 400
    assert query.call_count == 1


@patch('app.routes.venue_bookings.supabase_request')
def test_modification_changes_only_the_chosen_booking(query):
    query.side_effect = [{'id': 'coordinator'}, {'booking': {'booking_id': BOOKING, 'status': 'submitted'}}]
    response = create_app().test_client().patch(f'/api/venue-bookings/{BOOKING}', json=MODIFY, headers=HEADERS)
    assert response.status_code == 200
    assert response.json['booking']['status'] == 'submitted'
    assert query.call_args.args[0] == '/rest/v1/rpc/modify_venue_booking'
    assert query.call_args.kwargs['payload'] == {
        'p_booking_id': BOOKING, 'p_venue_id': MODIFY['venue_id'], 'p_venue_requirements': 'Classroom layout'}


@patch('app.routes.venue_bookings.supabase_request')
def test_a_modification_failing_a_recheck_is_refused(query):
    query.side_effect = [{'id': 'coordinator'}, {
        'error': 'This venue is blocked for part of this event\'s time.', 'status': 409}]
    response = create_app().test_client().patch(f'/api/venue-bookings/{BOOKING}', json=MODIFY, headers=HEADERS)
    assert response.status_code == 409
    assert 'booking' not in response.json


@patch('app.routes.venue_bookings.supabase_request')
def test_cancelling_affects_only_the_chosen_booking(query):
    query.side_effect = [{'id': 'coordinator'}, {'booking': {'booking_id': BOOKING, 'status': 'cancelled'}}]
    response = create_app().test_client().post(f'/api/venue-bookings/{BOOKING}/cancel', headers=HEADERS)
    assert response.status_code == 200
    assert response.json['booking']['status'] == 'cancelled'
    assert query.call_args.args[0] == '/rest/v1/rpc/cancel_venue_booking'
    assert query.call_args.kwargs['payload'] == {'p_booking_id': BOOKING}


@patch('app.routes.venue_bookings.supabase_request')
def test_a_refused_cancellation_is_passed_on(query):
    query.side_effect = [{'id': 'coordinator'}, {'error': 'Only pending or approved bookings can be cancelled.', 'status': 409}]
    response = create_app().test_client().post(f'/api/venue-bookings/{BOOKING}/cancel', headers=HEADERS)
    assert response.status_code == 409
    assert 'booking' not in response.json


@patch('app.routes.venue_bookings.supabase_request', return_value={'id': 'coordinator'})
def test_cancelling_a_malformed_id_is_not_found(query):
    response = create_app().test_client().post('/api/venue-bookings/not-a-uuid/cancel', headers=HEADERS)
    assert response.status_code == 404
    assert query.call_count == 1
