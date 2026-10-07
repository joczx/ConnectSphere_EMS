import unittest
from unittest.mock import patch

from app import create_app
from app.services.event_store import StoreError


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_login_requires_credentials(self):
        for body in [
            {},
            [],
            {'email': 'a', 'password': 2},
            {'email': '', 'password': 'password'},
            {'email': 'user@example.com', 'password': ''},
            {'email': '   ', 'password': 'password'},
        ]:
            response = self.client.post('/api/login', json=body)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json['error'], 'Email and password are required.')

    @patch('app.routes.login.supabase_request')
    def test_login_invalid_email_uses_generic_credentials_error(self, query):
        for email in ['username', 'user@', 'user@example', 'user name@example.com']:
            response = self.client.post('/api/login', json={'email': email, 'password': 'password'})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json['error'], 'Incorrect email or password. Please try again.')
        query.assert_not_called()

    @patch('app.routes.login.supabase_request', return_value={
        'access_token': 'access', 'refresh_token': 'refresh',
    })
    def test_login_uses_post_for_supabase_auth(self, query):
        response = self.client.post(
            '/api/login', json={'email': 'user@example.com', 'password': 'password'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(query.call_args.kwargs['method'], 'POST')

    @patch('app.routes.login.supabase_request', return_value={
        'access_token': 'access', 'refresh_token': 'refresh',
    })
    def test_refresh_uses_post_for_supabase_auth(self, query):
        response = self.client.post('/api/refresh', json={'refresh_token': 'refresh'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(query.call_args.kwargs['method'], 'POST')

    @patch('app.routes.login.supabase_request', side_effect=StoreError(401))
    def test_login_wrong_password_returns_readable_error(self, query):
        response = self.client.post('/api/login', json={'email': 'user@example.com', 'password': 'wrong'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json['error'], 'Incorrect email or password. Please try again.')

    @patch('app.routes.login.supabase_request', side_effect=StoreError(503))
    def test_login_service_failure_returns_json(self, query):
        response = self.client.post('/api/login', json={'email': 'user@example.com', 'password': 'password'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['error'], 'Unable to sign in right now. Please try again.')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
