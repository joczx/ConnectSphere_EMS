
import unittest
from unittest.mock import patch

from app import create_app


class EquipmentRequestRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.headers = {'Authorization': 'Bearer user-token'}

    @patch('app.services.equipment_request_service.supabase_request')
    def test_list_equipment_requests_for_event(self, query):
        query.return_value = [
            {
                'equipment_request_id': 15,
                'event_id': 2,
                'equipment_type': 'Projector',
                'quantity': 2,
                'technical_requirements': 'HDMI input required',
                'status': 'pending',
                'requested_by': 'user-1',
            }
        ]

        response = self.client.get('/api/events/2/equipment-requests', headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['count'], 1)
        self.assertEqual(response.json['equipment_requests'][0]['equipment_type'], 'Projector')

    @patch('app.services.equipment_request_service.supabase_request')
    def test_create_equipment_request_success(self, query):
        query.side_effect = [
            {'id': 'user-1'},
            [{'event_id': 2, 'event_coordinator_id': 'coordinator-1'}],
            [{
                'equipment_request_id': 10,
                'event_id': 2,
                'equipment_type': 'Projector',
                'quantity': 2,
                'technical_requirements': 'HDMI and wireless connectivity',
                'status': 'pending',
                'requested_by': 'user-1',
            }],
        ]

        response = self.client.post(
            '/api/events/2/equipment-requests',
            json={
                'equipment_type': 'Projector',
                'quantity': 2,
                'technical_requirements': 'HDMI and wireless connectivity',
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['message'], 'Equipment request submitted successfully.')
        self.assertEqual(response.json['equipment_request']['equipment_type'], 'Projector')

    @patch('app.services.equipment_request_service.supabase_request')
    def test_create_equipment_request_requires_equipment_type(self, query):
        query.side_effect = [
            {'id': 'user-1'},
            [{'event_id': 2, 'event_coordinator_id': 'coordinator-1'}],
        ]

        response = self.client.post(
            '/api/events/2/equipment-requests',
            json={
                'quantity': 2,
                'technical_requirements': 'HDMI',
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Equipment type is required.', response.json['error'])

    @patch('app.services.equipment_request_service.supabase_request')
    def test_create_equipment_request_validates_quantity(self, query):
        query.side_effect = [
            {'id': 'user-1'},
            [{'event_id': 2, 'event_coordinator_id': 'coordinator-1'}],
        ]

        response = self.client.post(
            '/api/events/2/equipment-requests',
            json={
                'equipment_type': 'Projector',
                'quantity': 0,
                'technical_requirements': 'HDMI',
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('quantity', response.json['error'])

    @patch('app.services.equipment_request_service.supabase_request')
    def test_list_equipment_requests_requires_auth(self, query):
        response = self.client.get('/api/events/2/equipment-requests')

        self.assertEqual(response.status_code, 401)
        self.assertIn('Authentication required.', response.json['error'])


if __name__ == '__main__':
    unittest.main()
