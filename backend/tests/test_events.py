import unittest
import io
from urllib.error import HTTPError
from unittest.mock import patch

from app import create_app
from app.services.event_store import StoreError
from app.services.event_store import supabase_request

EVENT_ID = 'b21bdd3b-5fbb-4588-b070-f9a7e923ef02'


class EventViewTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.headers = {'Authorization': 'Bearer user-token'}

    @patch('app.routes.events.supabase_request')
    def test_unauthenticated_access_does_not_query_database(self, query):
        for path in ['/api/events', '/api/events/' + EVENT_ID]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        query.assert_not_called()

    @patch('app.routes.events.supabase_request', side_effect=StoreError(401))
    def test_invalid_session_is_rejected(self, query):
        self.assertEqual(self.client.get('/api/events', headers=self.headers).status_code, 401)
        self.assertEqual(query.call_count, 1)

    @patch('app.routes.events.supabase_request')
    def test_inaccessible_event_is_not_disclosed(self, query):
        query.side_effect = [{'id': 'user'}, []]
        response = self.client.get('/api/events/' + EVENT_ID, headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(EVENT_ID, response.get_data(as_text=True))

    @patch('app.routes.events.supabase_request')
    def test_list_uses_verified_user_token_for_rls(self, query):
        query.side_effect = [{'id': 'user'}, [{'event_id': EVENT_ID}]]
        response = self.client.get('/api/events', headers=self.headers)
        self.assertEqual(response.json['events'], [{'event_id': EVENT_ID}])
        self.assertEqual(query.call_args.kwargs['token'], 'user-token')
        self.assertEqual(query.call_args.args[0], '/rest/v1/events?select=*&order=start_datetime.asc.nullslast')

    @patch('app.routes.events.supabase_request')
    def test_repeated_reads_return_latest_event_fields(self, query):
        event = dict(event_id=EVENT_ID, event_name='Workshop', status='planning',
                     start_datetime=None, end_datetime=None,
                     event_organiser_id='organiser', event_coordinator_id=None,
                     technical_support_id=None, venue_staff_id=None)
        updated = dict(event, status='confirmed')
        query.side_effect = [{'id': 'user'}, [event], {'id': 'user'}, [updated]]
        first = self.client.get('/api/events/' + EVENT_ID, headers=self.headers)
        second = self.client.get('/api/events/' + EVENT_ID, headers=self.headers)
        self.assertEqual(first.json['event'], event)
        self.assertEqual(second.json['event'], updated)
        self.assertEqual(second.headers['Cache-Control'], 'no-store')

    @patch('app.routes.events.supabase_request', return_value={'id': 'user'})
    def test_malformed_identifier_never_reaches_database(self, query):
        response = self.client.get('/api/events/invalid', headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(query.call_count, 1)

    @patch('app.routes.events.supabase_request', side_effect=StoreError(503))
    def test_service_failure_is_sanitized(self, query):
        response = self.client.get('/api/events', headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {'error': 'Event service is temporarily unavailable.'})

    @patch('app.routes.events.supabase_request')
    def test_current_coordinator_can_reassign_to_another_coordinator(self, query):
        query.side_effect = [
            {'id': 'current-coordinator'},
            [{'event_id': EVENT_ID, 'event_coordinator_id': 'current-coordinator'}],
            [{'event_id': EVENT_ID, 'event_coordinator_id': 'new-coordinator'}],
        ]

        response = self.client.patch(
            '/api/events/' + EVENT_ID + '/coordinator',
            headers=self.headers,
            json={'event_coordinator_id': 'new-coordinator'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['event']['event_coordinator_id'], 'new-coordinator')
        self.assertEqual(query.call_args.kwargs['token'], 'user-token')

    @patch('app.routes.events.supabase_request')
    def test_authenticated_non_coordinator_can_reassign(self, query):
        query.side_effect = [
            {'id': 'other-user'},
            [{'event_id': EVENT_ID, 'event_coordinator_id': 'current-coordinator'}],
            [{'event_id': EVENT_ID, 'event_coordinator_id': 'new-coordinator'}],
        ]

        response = self.client.patch(
            '/api/events/' + EVENT_ID + '/coordinator',
            headers=self.headers,
            json={'event_coordinator_id': 'new-coordinator'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['event']['event_coordinator_id'], 'new-coordinator')

    @patch('app.routes.events.supabase_request')
    def test_empty_update_result_is_reported_as_permission_error(self, query):
        query.side_effect = [
            {'id': 'other-user'},
            [{'event_id': EVENT_ID, 'event_coordinator_id': 'current-coordinator'}],
            [],
        ]

        response = self.client.patch(
            '/api/events/' + EVENT_ID + '/coordinator',
            headers=self.headers,
            json={'event_coordinator_id': 'new-coordinator'},
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn('permission to reassign', response.json['error'])

SUPABASE_ENV = {'SUPABASE_URL': 'https://example.test', 'SUPABASE_ANON_KEY': 'test-key'}


class EventInformationTests(unittest.TestCase):
    """View Event Information During Planning (SCRUM-10)."""

    def setUp(self):
        self.client = create_app().test_client()
        self.headers = {'Authorization': 'Bearer user-token'}

    # TC-VEI-034 (AC1, AC2): the event list can be narrowed to confirmed events.
    @patch('app.routes.events.supabase_request')
    def test_event_list_can_be_narrowed_to_confirmed_events(self, query):
        planning = {'event_id': EVENT_ID, 'status': 'planning'}
        confirmed = {'event_id': '7c1d2e3f-4a5b-4c6d-8e7f-9a0b1c2d3e4f', 'status': 'confirmed'}
        query.side_effect = [{'id': 'user'}, [planning, confirmed]]

        response = self.client.get('/api/events?status=confirmed', headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['events'], [confirmed])

    # TC-VEI-035 (AC4): a session that Supabase Auth refuses with 400 or 403 has to sign in again.
    def test_session_refused_by_supabase_auth_has_to_sign_in_again(self):
        for status in (400, 403):
            with self.subTest(status=status):
                refusal = HTTPError('https://example.test/auth/v1/user', status, 'Refused', {}, io.BytesIO(b''))
                with patch.dict('os.environ', SUPABASE_ENV), \
                        patch('app.services.event_store.urlopen', side_effect=refusal):
                    response = self.client.get('/api/events', headers=self.headers)

                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json, {'error': 'Please sign in again.'})

    # TC-VEI-036 (AC1): an event store error carries a message the event page can show.
    def test_event_store_errors_carry_a_message_the_page_can_show(self):
        self.assertEqual(StoreError(401).to_dict(), {'error': 'Please sign in again.'})
        self.assertEqual(StoreError(503).to_dict(), {'error': 'Event service is temporarily unavailable.'})
        self.assertEqual(StoreError(403, 'Not your event.').to_dict(), {'error': 'Not your event.'})

    # TC-VEI-037 (AC3): a write names its method and asks for the saved row back, so the latest version is shown.
    def test_event_write_returns_the_saved_row(self):
        with patch.dict('os.environ', SUPABASE_ENV), patch('app.services.event_store.urlopen') as send:
            send.return_value.__enter__.return_value = io.BytesIO(b'[{"event_id": 7, "event_name": "Renamed"}]')
            rows = supabase_request('/rest/v1/events?event_id=eq.7', token='user-token',
                                    payload={'event_name': 'Renamed'}, method='PATCH')

        self.assertEqual(rows, [{'event_id': 7, 'event_name': 'Renamed'}])
        sent = send.call_args.args[0]
        self.assertEqual(sent.get_method(), 'PATCH')
        self.assertEqual(sent.get_header('Prefer'), 'return=representation')
        self.assertEqual(sent.get_header('Authorization'), 'Bearer user-token')


class EventCoordinatorReassignmentTests(unittest.TestCase):
    """Re-assign another Event Coordinator to an Event (SCRUM-158)."""

    def setUp(self):
        self.client = create_app().test_client()
        self.headers = {'Authorization': 'Bearer user-token'}

    # TC-RAEC-007 (AC1, AC2): the event, the replacement coordinator and the event's existence are checked
    # before anything is written.
    @patch('app.routes.events.supabase_request')
    def test_reassignment_is_checked_before_anything_is_written(self, query):
        query.return_value = {'id': 'current-coordinator'}
        for path, body, status, error in (
            ('/api/events/not-an-event/coordinator', {'event_coordinator_id': 'new-coordinator'}, 404,
             'Event not found or access unavailable.'),
            (f'/api/events/{EVENT_ID}/coordinator', {}, 400, 'Please choose a replacement Event Coordinator.'),
            (f'/api/events/{EVENT_ID}/coordinator', {'event_coordinator_id': '   '}, 400,
             'Please choose a replacement Event Coordinator.'),
        ):
            with self.subTest(path=path, body=body):
                response = self.client.patch(path, headers=self.headers, json=body)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json, {'error': error})

        query.side_effect = [{'id': 'current-coordinator'}, []]
        response = self.client.patch(f'/api/events/{EVENT_ID}/coordinator', headers=self.headers,
                                     json={'event_coordinator_id': 'new-coordinator'})

        self.assertEqual(response.status_code, 404)
        self.assertNotIn('PATCH', [call.kwargs.get('method') for call in query.call_args_list])


if __name__ == '__main__':
    unittest.main()
