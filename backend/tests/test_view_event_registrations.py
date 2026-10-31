"""Unit tests for viewing registration information for managed events.

Supabase is mocked here. Actual role/assignment enforcement and status counts
are exercised separately by frontend/tests/registration-db.mjs.
"""
from unittest.mock import patch

import pytest

from app import create_app


def test_event_roster_requires_authentication():
    client = create_app().test_client()
    with patch('app.services.registration_service.supabase_request') as rpc:
        assert client.get('/api/events/1/registrations').status_code == 401
        rpc.assert_not_called()


# AC1-4: verified identity, managed event, contact details, totals and statuses.
def test_event_roster_passes_verified_token_and_event_id_only():
    result = {'event': {'event_id': 1, 'event_name': 'Conference'}, 'total_registered': 1,
              'total_waitlisted': 0, 'total_withdrawn': 0, 'registrations': [{
                  'full_name': 'Alex Tan', 'contact_email': 'alex@example.com',
                  'contact_phone': '+65 8123 4567', 'status': 'registered',
              }]}
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'organiser'}), \
         patch('app.services.registration_service.supabase_request', return_value=result) as rpc:
        response = client.get('/api/events/1/registrations?event_organiser_id=someone-else',
                              headers={'Authorization': 'Bearer verified'})
    assert response.status_code == 200
    assert response.json == result
    assert response.headers['Cache-Control'] == 'no-store'
    rpc.assert_called_once_with('/rest/v1/rpc/event_registration_roster', token='verified',
                               payload={'p_event_id': 1}, method='POST')


# AC5: unauthorised responses must not expose attendee information.
@pytest.mark.parametrize('status', [403, 404])
def test_unauthorised_roster_response_contains_no_attendee_details(status):
    client = create_app().test_client()
    with patch('app.routes.events.supabase_request', return_value={'id': 'unassigned'}), \
         patch('app.services.registration_service.supabase_request', return_value={'error': 'Access unavailable.', 'status': status}):
        response = client.get('/api/events/1/registrations', headers={'Authorization': 'Bearer verified'})
    assert response.status_code == status
    assert response.json == {'error': 'Access unavailable.'}
