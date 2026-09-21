"""50 isolated API/client regression cases; no live Supabase credentials needed.

Generated matrix cases have individual names in unittest's verbose report.
These tests verify the API boundary, not deployed RLS or browser rendering.
"""
import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from app import create_app
from app.services.event_store import StoreError, supabase_request

EVENT_ID = 'b21bdd3b-5fbb-4588-b070-f9a7e923ef02'
DETAIL = '/api/events/' + EVENT_ID
EVENT = dict(event_id=EVENT_ID, event_name='Workshop', status='planning',
             start_datetime='2026-10-01T01:00:00Z', end_datetime='2026-10-01T03:00:00Z',
             event_organiser_id='user-a', event_coordinator_id=None,
             technical_support_id=None, venue_staff_id=None)


class EventAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.headers = {'Authorization': 'Bearer user-a-token'}
        self.patcher = patch('app.routes.events.supabase_request')
        self.query = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def get_rows(self, path, rows):
        self.query.side_effect = [{'id': 'user-a'}, rows]
        return self.client.get(path, headers=self.headers)

    def test_25_authorised_list(self):
        response = self.get_rows('/api/events', [EVENT])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'events': [EVENT]})
        self.assertEqual(self.query.call_args.kwargs, {'token': 'user-a-token'})

    def test_26_authorised_detail(self):
        response = self.get_rows(DETAIL, [EVENT])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'event': EVENT})
        self.assertEqual(self.query.call_args.args[0], '/rest/v1/events?select=*&event_id=eq.' + EVENT_ID)
        self.assertEqual(self.query.call_args.kwargs, {'token': 'user-a-token'})

    def test_27_empty_list(self):
        response = self.get_rows('/api/events', [])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'events': []})

    def test_28_unavailable_detail(self):
        response = self.get_rows(DETAIL, [])
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {'error': 'Event not found or access unavailable.'})
        self.assertNotIn(EVENT_ID, response.get_data(as_text=True))

    def test_29_fresh_details_each_request(self):
        first = self.get_rows(DETAIL, [EVENT])
        updated = dict(EVENT, event_name='Updated workshop', status='confirmed')
        second = self.get_rows(DETAIL, [updated])
        self.assertEqual(first.json['event'], EVENT)
        self.assertEqual(second.json['event'], updated)
        self.assertEqual(self.query.call_count, 4)
        self.assertEqual(second.headers['Cache-Control'], 'no-store')

    def test_30_removed_access_clears_details(self):
        self.assertEqual(self.get_rows(DETAIL, [EVENT]).status_code, 200)
        response = self.get_rows(DETAIL, [])
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('event', response.json)

    def test_31_null_fields_preserved(self):
        event = dict(EVENT, start_datetime=None, end_datetime=None, status=None)
        self.assertEqual(self.get_rows(DETAIL, [event]).json['event'], event)

    def test_32_unicode_and_markup_preserved_as_json(self):
        event = dict(EVENT, event_name='\u6d3b\u52a8 Caf\u00e9 <script>alert(1)</script>')
        response = self.get_rows(DETAIL, [event])
        self.assertEqual(response.mimetype, 'application/json')
        self.assertEqual(response.json['event']['event_name'], event['event_name'])

    def test_33_malformed_id_not_queried(self):
        self.query.return_value = {'id': 'user-a'}
        response = self.client.get('/api/events/not-a-uuid', headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.query.assert_called_once_with('/auth/v1/user', token='user-a-token')

    def test_34_failure_is_not_an_empty_list(self):
        self.query.side_effect = [{'id': 'user-a'}, StoreError(503)]
        response = self.client.get('/api/events', headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {'error': 'Event service is temporarily unavailable.'})
        self.assertEqual(response.headers['Cache-Control'], 'no-store')


# 01-16: authenticate both list and direct-detail requests.
def auth_case(path, header, identity):
    def test(self):
        self.query.side_effect = [identity] if not isinstance(identity, Exception) else identity
        headers = {} if header is None else {'Authorization': header}
        response = self.client.get(path, headers=headers)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertNotIn('event', response.json)
        self.assertNotIn('events', response.json)
        if header in (None, '', 'Basic abc', 'Bearer', 'Bearer   '):
            self.query.assert_not_called()
        else:
            self.query.assert_called_once_with('/auth/v1/user', token='bad-token')
    return test

AUTH_CASES = [
    ('missing_header', None, {}), ('empty_header', '', {}),
    ('wrong_scheme', 'Basic abc', {}), ('missing_token', 'Bearer', {}),
    ('blank_token', 'Bearer   ', {}), ('invalid_token', 'Bearer bad-token', StoreError(401)),
    ('missing_user_id', 'Bearer bad-token', {}), ('empty_user_id', 'Bearer bad-token', {'id': ''}),
]
number = 1
for endpoint, path in [('list', '/api/events'), ('detail', DETAIL)]:
    for label, header, identity in AUTH_CASES:
        setattr(EventAcceptanceTests, f'test_{number:02d}_{endpoint}_{label}', auth_case(path, header, identity))
        number += 1

# 17-24: viewing endpoints do not accept writes.
def write_case(path, method):
    def test(self):
        response = self.client.open(path, method=method, headers=self.headers, json={'event_name': 'Changed'})
        self.assertEqual(response.status_code, 405)
        self.query.assert_not_called()
    return test

for endpoint, path in [('list', '/api/events'), ('detail', DETAIL)]:
    for method in ['POST', 'PUT', 'PATCH', 'DELETE']:
        setattr(EventAcceptanceTests, f'test_{number:02d}_{endpoint}_rejects_{method.lower()}', write_case(path, method))
        number += 1


class SupabaseClientTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict('os.environ', {'SUPABASE_URL': 'https://example.invalid/', 'SUPABASE_ANON_KEY': 'test-key'})
        env.start()
        self.addCleanup(env.stop)
        transport = patch('app.services.event_store.urlopen')
        self.transport = transport.start()
        self.addCleanup(transport.stop)

    def test_43_missing_url(self):
        with patch.dict('os.environ', {'SUPABASE_URL': ''}), self.assertRaises(StoreError) as result:
            supabase_request('/rest/v1/events')
        self.assertEqual(result.exception.status, 503)
        self.transport.assert_not_called()

    def test_44_missing_key(self):
        with patch.dict('os.environ', {'SUPABASE_ANON_KEY': ''}), self.assertRaises(StoreError) as result:
            supabase_request('/rest/v1/events')
        self.assertEqual(result.exception.status, 503)
        self.transport.assert_not_called()

    def test_45_network_failure(self):
        self.transport.side_effect = URLError('private network diagnostic')
        with self.assertRaises(StoreError) as result:
            supabase_request('/rest/v1/events')
        self.assertEqual(result.exception.status, 503)
        self.assertNotIn('private', str(result.exception))

    def test_46_timeout(self):
        self.transport.side_effect = TimeoutError()
        with self.assertRaises(StoreError) as result:
            supabase_request('/rest/v1/events')
        self.assertEqual(result.exception.status, 503)

    def test_47_invalid_json(self):
        self.transport.return_value.__enter__.return_value = io.BytesIO(b'<html>Error</html>')
        with self.assertRaises(StoreError) as result:
            supabase_request('/rest/v1/events')
        self.assertEqual(result.exception.status, 503)

    def test_48_get_preserves_user_token_and_timeout(self):
        self.transport.return_value.__enter__.return_value = io.BytesIO(b'[]')
        self.assertEqual(supabase_request('/rest/v1/events', token='user-a-token'), [])
        request = self.transport.call_args.args[0]
        self.assertEqual(request.full_url, 'https://example.invalid/rest/v1/events')
        self.assertEqual(request.get_method(), 'GET')
        self.assertIsNone(request.data)
        self.assertEqual(request.get_header('Authorization'), 'Bearer user-a-token')
        self.assertEqual(request.get_header('Apikey'), 'test-key')
        self.assertEqual(self.transport.call_args.kwargs, {'timeout': 10})

    def test_49_json_object_response(self):
        self.transport.return_value.__enter__.return_value = io.BytesIO(b'{"id":"user-a"}')
        self.assertEqual(supabase_request('/auth/v1/user', token='user-a-token'), {'id': 'user-a'})

    def test_50_no_authorization_header_without_user_token(self):
        self.transport.return_value.__enter__.return_value = io.BytesIO(b'{}')
        supabase_request('/auth/v1/settings')
        self.assertIsNone(self.transport.call_args.args[0].get_header('Authorization'))


# 35-42: upstream failures are converted to the application's error contract.
def http_case(status, expected):
    def test(self):
        self.transport.side_effect = HTTPError('https://example.invalid', status, 'private diagnostic', {}, None)
        with self.assertRaises(StoreError) as result:
            supabase_request('/rest/v1/events', token='user-a-token')
        self.assertEqual(result.exception.status, expected)
        self.assertNotIn('private', str(result.exception))
    return test

for number, (status, expected) in enumerate([(400, 401), (401, 401), (403, 401), (404, 503), (429, 503), (500, 503), (502, 503), (503, 503)], 35):
    setattr(SupabaseClientTests, f'test_{number:02d}_upstream_http_{status}', http_case(status, expected))

if __name__ == '__main__':
    unittest.main()
