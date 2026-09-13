import unittest
from unittest.mock import patch

from app import create_app
from app.services.event_store import StoreError

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

    @patch('app.routes.events.supabase_request')
    def test_repeated_reads_return_latest_version_and_all_fields(self, query):
        event = dict(event_id=EVENT_ID, event_name='Workshop', purpose='Training',
                     description='Team training', starts_at=None, ends_at=None,
                     expected_attendance=0, venue_requirements='Classroom',
                     accessibility_needs='Step-free', equipment_requirements='Projector',
                     registration_required=False, registration_needs=None, version=1)
        updated = dict(event, version=2, expected_attendance=50)
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

    def test_login_requires_credentials(self):
        for body in [{}, [], {'email': 'a', 'password': 2}]:
            self.assertEqual(self.client.post('/api/login', json=body).status_code, 400)


if __name__ == '__main__':
    unittest.main()
