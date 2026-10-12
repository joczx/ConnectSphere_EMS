import unittest
from unittest.mock import patch

from app import create_app


class UserRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.headers = {'Authorization': 'Bearer user-token'}

    @patch('app.routes.users.supabase_request')
    def test_current_user_returns_name_and_multiple_roles(self, query):
        query.side_effect = [
            {'id': 'user-id'},
            {'id': 'user-id', 'email': 'casey@example.com'},
            [{'name': 'Casey User', 'email': 'casey@example.com'}],
            [{'role_id': 1}, {'role_id': 2}, {'role_id': 1}],
            [
                {'role_name': 'Event Coordinator'},
                {'role_name': 'Event Organiser'},
            ],
        ]

        response = self.client.get('/api/users/me', headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json['user'],
            {'name': 'Casey User', 'roles': ['Event Coordinator', 'Event Organiser']},
        )
        self.assertEqual(query.call_count, 5)

    @patch('app.routes.users.supabase_request')
    def test_current_user_without_profile_or_roles_uses_auth_email(self, query):
        query.side_effect = [
            {'id': 'user-id'},
            {'id': 'user-id', 'email': 'casey@example.com'},
            [],
            [],
        ]

        response = self.client.get('/api/users/me', headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['user'], {'name': 'casey', 'roles': []})
        self.assertEqual(query.call_count, 4)

    @patch('app.routes.users.supabase_request')
    def test_role_filter_returns_only_event_coordinators(self, query):
        query.side_effect = [
            {'id': 'requesting-user'},
            [
                {'role_id': 1, 'role_name': 'Event Coordinator'},
                {'role_id': 2, 'role_name': 'Event Organiser'},
            ],
            [{'user_id': 'coordinator-id'}],
            [{
                'user_id': 'coordinator-id',
                'name': 'Casey Coordinator',
                'email': 'casey@example.com',
            }],
        ]

        response = self.client.get(
            '/api/users?role=event_coordinator', headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['users'], {'coordinator-id': 'Casey Coordinator'})
        self.assertEqual(
            query.call_args_list[2].args[0],
            '/rest/v1/user_roles?select=user_id&role_id=in.(1)',
        )
        self.assertEqual(query.call_args.args[0],
                         '/rest/v1/users?select=user_id,name,email&user_id=in.(coordinator-id)&order=name.asc')

    @patch('app.routes.users.supabase_request')
    def test_role_filter_returns_empty_list_when_role_is_unassigned(self, query):
        query.side_effect = [
            {'id': 'requesting-user'},
            [{'role_id': 2, 'role_name': 'Event Organiser'}],
        ]

        response = self.client.get(
            '/api/users?role=event_coordinator', headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['users'], {})
        self.assertEqual(query.call_count, 2)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()