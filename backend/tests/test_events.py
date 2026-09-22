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
        self.assertEqual(query.call_args.args[0], '/rest/v1/events?select=event_id,event_name,status,start_datetime,end_datetime&order=start_datetime.asc.nullslast')

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

if __name__ == '__main__':
    unittest.main()
