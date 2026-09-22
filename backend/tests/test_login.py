import unittest
from unittest.mock import patch

from app import create_app
from app.services.event_store import StoreError


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_login_requires_credentials(self):
        for body in [{}, [], {'email': 'a', 'password': 2}]:
            self.assertEqual(self.client.post('/api/login', json=body).status_code, 400)

    @patch('app.routes.login.supabase_request')
    def test_login_rejects_invalid_email_without_auth_request(self, query):
        for email in ['username', 'user@', 'user@example', 'user name@example.com']:
            response = self.client.post('/api/login', json={'email': email, 'password': 'password'})
            self.assertEqual(response.status_code, 400)
            self.assertIn('Invalid email address', response.json['error'])
        query.assert_not_called()

    @patch('app.routes.login.supabase_request', side_effect=StoreError(401))
    def test_login_wrong_password_returns_readable_error(self, query):
        response = self.client.post('/api/login', json={'email': 'user@example.com', 'password': 'wrong'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json['error'], 'Incorrect email or password. Please try again.')

    @patch('app.routes.login.supabase_request', side_effect=StoreError(503))
    def test_login_service_failure_returns_json(self, query):
        response = self.client.post('/api/login', json={'email': 'user@example.com', 'password': 'password'})
        self.assertEqual(response.status_code, 503)
        self.assertIn('error', response.json)


if __name__ == '__main__':
    unittest.main()
