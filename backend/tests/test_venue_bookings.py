from unittest.mock import patch
import pytest
from app import create_app
from app.schemas.venue_booking import parse_booking
from app.services.event_store import StoreError

VALID = dict(venue_id='b21bdd3b-5fbb-4588-b070-f9a7e923ef02', event_id=4, event_name='Workshop',
             starts_at='2099-01-01T10:00:00+08:00', ends_at='2099-01-01T12:00:00+08:00',
             attendance=40, venue_requirements='Classroom layout and wheelchair access')
HEADERS = {'Authorization': 'Bearer coordinator-token'}
BOOKINGS_URL = '/api/venue-bookings'
BOOKING = '3cf6f106-e05a-45ce-a6e5-825afcbf23cd'
MODIFY = {'venue_id': VALID['venue_id'], 'venue_requirements': 'Classroom layout'}
NOT_FOUND = {'error': 'Booking request not found or access unavailable.'}


def client():
    return create_app().test_client()


def assert_missing_booking(response, query):
    assert response.status_code == 404
    assert response.json == NOT_FOUND
    assert query.call_count == 1


# Verifies that every required booking field is reported when omitted.
@pytest.mark.parametrize('field', VALID)
def test_every_booking_field_is_required(field):
    body = dict(VALID)
    del body[field]
    assert field in parse_booking(body)[1]


# Verifies that invalid values for each booking field are rejected by validation.
@pytest.mark.parametrize('changes,field', [
    ({'attendance': True}, 'attendance'),
    ({'attendance': 0}, 'attendance'), ({'attendance': 2147483648}, 'attendance'),
    ({'event_name': '  '}, 'event_name'), ({'venue_requirements': 'x' * 5001}, 'venue_requirements'),
    ({'venue_id': 'bad'}, 'venue_id'), ({'starts_at': '2099-01-01T10:00'}, 'starts_at'),
    ({'starts_at': '2000-01-01T10:00+08:00'}, 'starts_at'),
    ({'ends_at': VALID['starts_at']}, 'ends_at'),
    ({'event_id': '4'}, 'event_id'), ({'event_id': 0}, 'event_id'),
    ({'event_id': True}, 'event_id'),
])
def test_invalid_booking_details(changes, field):
    assert field in parse_booking({**VALID, **changes})[1]


# Ensures client-supplied ownership and status cannot override system-controlled fields.
def test_valid_payload_ignores_forged_owner_and_status():
    data, errors = parse_booking({**VALID, 'requested_by': 'another-user', 'status': 'approved'})
    assert not errors
    assert set(data) == set(VALID)


# Ensures a booking payload must be a JSON object rather than another JSON type.
def test_booking_payload_must_be_an_object():
    data, errors = parse_booking(['not', 'a', 'booking'])
    assert data == {}
    assert errors == {'body': 'Provide a booking request object.'}


# Ensures unauthenticated users cannot submit or list booking requests.
@patch('app.routes.venue_bookings.supabase_request')
def test_authentication_required(query):
    browser = client()
    assert browser.post(BOOKINGS_URL, json=VALID).status_code == 401
    assert browser.get(BOOKINGS_URL).status_code == 401
    query.assert_not_called()


# Ensures invalid input is rejected before a booking-write RPC is made.
@patch('app.routes.venue_bookings.supabase_request', return_value={'id': 'coordinator'})
def test_invalid_submission_never_writes(query):
    response = client().post(BOOKINGS_URL, json={}, headers=HEADERS)
    assert response.status_code == 400
    assert query.call_count == 1


# Verifies a valid submission returns its persisted booking and confirmation message.
@patch('app.routes.venue_bookings.supabase_request')
def test_submission_confirms_persisted_request(query):
    query.side_effect = [{'id': 'coordinator'}, {**VALID, 'booking_id': 'saved-id', 'status': 'submitted'}]
    response = client().post(BOOKINGS_URL, json=VALID, headers=HEADERS)
    assert response.status_code == 201
    assert response.json['booking']['booking_id'] == 'saved-id'
    assert 'Venue Staff' in response.json['message']
    assert query.call_args.args[0] == '/rest/v1/rpc/submit_venue_booking'
    assert query.call_args.kwargs['token'] == 'coordinator-token'
    assert response.headers['Cache-Control'] == 'no-store'


# Ensures a database role refusal is returned to the caller as an error.
@patch('app.routes.venue_bookings.supabase_request')
def test_database_role_denial_is_not_success(query):
    query.side_effect = [{'id': 'organiser'}, {'error': 'Only Event Coordinators can submit venue bookings.', 'status': 403}]
    response = client().post(BOOKINGS_URL, json=VALID, headers=HEADERS)
    assert response.status_code == 403
    assert 'booking' not in response.json


# Verifies Venue Staff receive booking-list data and review permission details.
@patch('app.routes.venue_bookings.supabase_request')
def test_staff_receives_review_details(query):
    query.side_effect = [{'id': 'staff'}, {'bookings': [VALID], 'can_review': True, 'can_submit': False}]
    response = client().get(BOOKINGS_URL, headers=HEADERS)
    assert response.status_code == 200
    assert response.json['bookings'][0] == VALID
    assert query.call_args.args[0] == '/rest/v1/rpc/list_venue_bookings'
    assert query.call_args.kwargs['token'] == 'coordinator-token'


# Ensures a booking-list refusal from the database keeps its error status and message.
@patch('app.routes.venue_bookings.supabase_request')
def test_booking_list_passes_on_a_database_refusal(query):
    query.side_effect = [{'id': 'coordinator'}, {
        'error': 'Venue bookings are unavailable to this account.', 'status': 403,
    }]

    response = client().get(BOOKINGS_URL, headers=HEADERS)

    assert response.status_code == 403
    assert response.json == {'error': 'Venue bookings are unavailable to this account.'}


# Ensures a storage failure cannot be mistaken for a successful booking confirmation.
@patch('app.routes.venue_bookings.supabase_request')
def test_storage_failure_has_no_confirmation(query):
    query.side_effect = [{'id': 'coordinator'}, StoreError(503)]
    response = client().post(BOOKINGS_URL, json=VALID, headers=HEADERS)
    assert response.status_code == 503
    assert 'booking' not in response.json


# Verifies the submitted booking payload is linked to the requested event ID.
@patch('app.routes.venue_bookings.supabase_request')
def test_request_names_the_event_it_is_for(query):
    query.side_effect = [{'id': 'coordinator'}, {**VALID, 'booking_id': 'saved-id'}]
    client().post(BOOKINGS_URL, json=VALID, headers=HEADERS)
    assert query.call_args.kwargs['payload']['p_booking']['event_id'] == 4


# Ensures venue shortfalls supplied by the database remain visible to the coordinator.
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
    response = client().post(BOOKINGS_URL, json=VALID, headers=HEADERS)
    assert response.status_code == 409
    assert response.json['unmet_requirements'] == ['Holds 80, but 400 are expected.']
    assert 'booking' not in response.json


# Verifies an authorised user can retrieve one booking by its ID.
@patch('app.routes.venue_bookings.supabase_request')
def test_one_booking_is_returned_to_an_authorised_viewer(query):
    query.side_effect = [{'id': 'coordinator'}, {'booking': {**VALID, 'booking_id': BOOKING}}]

    response = client().get(f'{BOOKINGS_URL}/{BOOKING}', headers=HEADERS)

    assert response.status_code == 200
    assert response.json['booking']['booking_id'] == BOOKING
    assert query.call_args.args[0] == '/rest/v1/rpc/get_venue_booking'
    assert query.call_args.kwargs['payload'] == {'p_booking_id': BOOKING}


# Ensures an invalid booking ID is rejected before the booking-read RPC is called.
@patch('app.routes.venue_bookings.supabase_request', return_value={'id': 'coordinator'})
def test_viewing_a_booking_with_a_malformed_id_is_not_found(query):
    response = client().get(f'{BOOKINGS_URL}/not-a-uuid', headers=HEADERS)
    assert_missing_booking(response, query)


# Ensures invalid booking modifications are rejected before a write is attempted.
@pytest.mark.parametrize('body', [{}, {**MODIFY, 'venue_id': 'bad'}, {**MODIFY, 'venue_requirements': ' '}])
@patch('app.routes.venue_bookings.supabase_request', return_value={'id': 'coordinator'})
def test_invalid_modification_never_writes(query, body):
    response = client().patch(f'{BOOKINGS_URL}/{BOOKING}', json=body, headers=HEADERS)
    assert response.status_code == 400
    assert query.call_count == 1


# Verifies modification targets only the requested booking and sends the chosen changes.
@patch('app.routes.venue_bookings.supabase_request')
def test_modification_changes_only_the_chosen_booking(query):
    query.side_effect = [{'id': 'coordinator'}, {'booking': {'booking_id': BOOKING, 'status': 'submitted'}}]
    response = client().patch(f'{BOOKINGS_URL}/{BOOKING}', json=MODIFY, headers=HEADERS)
    assert response.status_code == 200
    assert response.json['booking']['status'] == 'submitted'
    assert query.call_args.args[0] == '/rest/v1/rpc/modify_venue_booking'
    assert query.call_args.kwargs['payload'] == {
        'p_booking_id': BOOKING, 'p_venue_id': MODIFY['venue_id'], 'p_venue_requirements': 'Classroom layout'}


# Ensures a venue recheck refusal during modification is returned as an error.
@patch('app.routes.venue_bookings.supabase_request')
def test_a_modification_failing_a_recheck_is_refused(query):
    query.side_effect = [{'id': 'coordinator'}, {
        'error': 'This venue is blocked for part of this event\'s time.', 'status': 409}]
    response = client().patch(f'{BOOKINGS_URL}/{BOOKING}', json=MODIFY, headers=HEADERS)
    assert response.status_code == 409
    assert 'booking' not in response.json


# Verifies cancellation targets only the booking identified in the request path.
@patch('app.routes.venue_bookings.supabase_request')
def test_cancelling_affects_only_the_chosen_booking(query):
    query.side_effect = [{'id': 'coordinator'}, {'booking': {'booking_id': BOOKING, 'status': 'cancelled'}}]
    response = client().post(f'{BOOKINGS_URL}/{BOOKING}/cancel', headers=HEADERS)
    assert response.status_code == 200
    assert response.json['booking']['status'] == 'cancelled'
    assert query.call_args.args[0] == '/rest/v1/rpc/cancel_venue_booking'
    assert query.call_args.kwargs['payload'] == {'p_booking_id': BOOKING}


# Ensures a cancellation refusal from the database is returned to the caller.
@patch('app.routes.venue_bookings.supabase_request')
def test_a_refused_cancellation_is_passed_on(query):
    query.side_effect = [{'id': 'coordinator'}, {'error': 'Only pending or approved bookings can be cancelled.', 'status': 409}]
    response = client().post(f'{BOOKINGS_URL}/{BOOKING}/cancel', headers=HEADERS)
    assert response.status_code == 409
    assert 'booking' not in response.json


# Ensures cancellation rejects an invalid booking ID before a database write.
@patch('app.routes.venue_bookings.supabase_request', return_value={'id': 'coordinator'})
def test_cancelling_a_malformed_id_is_not_found(query):
    response = client().post(f'{BOOKINGS_URL}/not-a-uuid/cancel', headers=HEADERS)
    assert_missing_booking(response, query)


# Ensures missing, malformed, or timezone-free hold expiry values are rejected.
@pytest.mark.parametrize('body', [{}, {'expires_at': None}, {'expires_at': 'tomorrow'}, {'expires_at': '2099-01-01T10:00'}])
@patch('app.routes.venue_bookings.supabase_request', return_value={'id': 'staff'})
def test_a_hold_without_a_valid_expiry_is_refused(query, body):
    response = client().post(f'{BOOKINGS_URL}/{BOOKING}/hold', json=body, headers=HEADERS)
    assert response.status_code == 400
    assert 'expires_at' in response.json['errors']
    assert query.call_count == 1


# Ensures an invalid booking ID cannot be used to place a hold.
@patch('app.routes.venue_bookings.supabase_request', return_value={'id': 'staff'})
def test_a_hold_with_a_malformed_booking_id_is_not_found(query):
    response = client().post(f'{BOOKINGS_URL}/not-a-uuid/hold',
                                               json={'expires_at': '2099-01-01T10:00:00+08:00'}, headers=HEADERS)
    assert_missing_booking(response, query)


# Verifies a valid hold forwards its expiry and booking ID to the hold RPC.
@patch('app.routes.venue_bookings.supabase_request')
def test_a_hold_is_placed_with_its_expiry(query):
    query.side_effect = [{'id': 'staff'}, {'booking': {'booking_id': BOOKING, 'hold_expires_at': '2099-01-01T10:00:00+08:00'}}]
    response = client().post(f'{BOOKINGS_URL}/{BOOKING}/hold',
                                               json={'expires_at': '2099-01-01T10:00:00+08:00'}, headers=HEADERS)
    assert response.status_code == 200
    assert query.call_args.args[0] == '/rest/v1/rpc/hold_venue_booking'
    assert query.call_args.kwargs['payload'] == {'p_booking_id': BOOKING, 'p_expires_at': '2099-01-01T10:00:00+08:00'}


# Ensures a hold conflict returned by the database reaches the Venue Staff member.
@patch('app.routes.venue_bookings.supabase_request')
def test_a_refused_hold_is_passed_on(query):
    query.side_effect = [{'id': 'staff'}, {'error': 'The venue is already booked, held or unavailable at this time.', 'status': 409}]
    response = client().post(f'{BOOKINGS_URL}/{BOOKING}/hold',
                                               json={'expires_at': '2099-01-01T10:00:00+08:00'}, headers=HEADERS)
    assert response.status_code == 409


# Verifies Venue Staff can release an active tentative hold before it expires.
@patch('app.routes.venue_bookings.supabase_request')
def test_a_hold_can_be_released_early(query):
    query.side_effect = [{'id': 'staff'}, {'booking': {'booking_id': BOOKING, 'status': 'submitted', 'hold_expires_at': None}}]
    response = client().delete(f'{BOOKINGS_URL}/{BOOKING}/hold', headers=HEADERS)
    assert response.status_code == 200
    assert response.json['booking']['hold_expires_at'] is None
    assert query.call_args.args[0] == '/rest/v1/rpc/release_venue_hold'


# Ensures releasing a hold rejects an invalid booking ID before an RPC call.
@patch('app.routes.venue_bookings.supabase_request', return_value={'id': 'staff'})
def test_releasing_a_hold_with_a_malformed_booking_id_is_not_found(query):
    response = client().delete(f'{BOOKINGS_URL}/not-a-uuid/hold', headers=HEADERS)
    assert_missing_booking(response, query)


# Ensures the database's no-active-hold refusal is returned to the caller.
@patch('app.routes.venue_bookings.supabase_request')
def test_releasing_without_an_active_hold_is_refused(query):
    query.side_effect = [{'id': 'staff'}, {'error': 'This request has no active hold.', 'status': 409}]
    response = client().delete(f'{BOOKINGS_URL}/{BOOKING}/hold', headers=HEADERS)
    assert response.status_code == 409


# Ensures duplicate active venue requests are converted from database key errors to conflicts.
@pytest.mark.parametrize('method,path,body', [
    ('post', BOOKINGS_URL, VALID),
    ('patch', f'{BOOKINGS_URL}/{BOOKING}', MODIFY),
])
@patch('app.routes.venue_bookings.supabase_request')
def test_a_second_active_request_for_the_same_venue_and_event_is_refused(query, method, path, body):
    query.side_effect = [{'id': 'coordinator'}, StoreError(503, code='23505')]
    response = getattr(client(), method)(path, json=body, headers=HEADERS)
    assert response.status_code == 409
    assert 'already has a pending or approved booking for this venue' in response.json['error']


# Verifies one event can submit separate valid requests for two distinct venues.
@patch('app.routes.venue_bookings.supabase_request')
def test_two_different_venues_can_be_requested_for_one_event(query):
    second_venue = 'd2719aa8-4b3d-4d22-9baa-c52d386104e7'
    second_request = {**VALID, 'venue_id': second_venue}
    query.side_effect = [
        {'id': 'coordinator'}, {**VALID, 'booking_id': 'first-booking'},
        {'id': 'coordinator'}, {**second_request, 'booking_id': 'second-booking'},
    ]

    browser = client()
    first = browser.post(BOOKINGS_URL, json=VALID, headers=HEADERS)
    second = browser.post(BOOKINGS_URL, json=second_request, headers=HEADERS)

    assert first.status_code == second.status_code == 201
    first_payload = query.call_args_list[1].kwargs['payload']['p_booking']
    second_payload = query.call_args_list[3].kwargs['payload']['p_booking']
    assert first_payload['event_id'] == second_payload['event_id'] == VALID['event_id']
    assert {first_payload['venue_id'], second_payload['venue_id']} == {VALID['venue_id'], second_venue}


# Verifies users assigned to an event can view that event's bookings.
@patch('app.routes.venue_bookings.supabase_request')
def test_people_assigned_to_an_event_read_its_bookings(query):
    query.side_effect = [{'id': 'organiser'}, {'bookings': [{'booking_id': 'b1', 'event_id': 4, 'venue_name': 'Hall'}]}]
    response = client().get(f'{BOOKINGS_URL}/events/4', headers=HEADERS)
    assert response.status_code == 200
    assert response.json['bookings'][0]['venue_name'] == 'Hall'
    assert query.call_args.args[0] == '/rest/v1/rpc/event_venue_bookings'
    assert query.call_args.kwargs['payload'] == {'p_event_id': 4}


# Ensures event-booking access refusals are returned without exposing booking data.
@patch('app.routes.venue_bookings.supabase_request')
def test_event_bookings_pass_on_the_database_refusal(query):
    query.side_effect = [{'id': 'stranger'}, {'error': 'Only the people assigned to this event can view its venue bookings.', 'status': 403}]
    response = client().get(f'{BOOKINGS_URL}/events/4', headers=HEADERS)
    assert response.status_code == 403
    assert 'assigned to this event' in response.json['error']


# Ensures event-specific booking reads require authentication.
@patch('app.routes.venue_bookings.supabase_request')
def test_event_bookings_require_sign_in(query):
    assert client().get(f'{BOOKINGS_URL}/events/4').status_code == 401
    query.assert_not_called()
