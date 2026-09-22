import unittest
from unittest.mock import patch

from app import create_app


class EquipmentAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.headers = {'Authorization': 'Bearer user-token'}

    @patch('app.services.equipment_availability_service.supabase_request')
    def test_check_equipment_availability_allows_any_authenticated_user(self, query): #change to only technical support staff in the future.
        query.side_effect = [
            {'id': 'tech-user'},
            [{
                'equipment_id': 10,
                'equipment_type': 'Projector',
                'equipment_model': 'PX-500',
                'total_quantity': 5,
                'available_quantity': 5,
            }],
        ]

        response = self.client.get(
            '/api/equipment-availability?equipment_type=Projector&quantity=2&start_datetime=2026-10-01T09:00:00Z&end_datetime=2026-10-01T12:00:00Z',
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['message'], 'Availability checked successfully.')
        self.assertEqual(response.json['results'][0]['fulfillment_status'], 'available')
        self.assertEqual(response.json['results'][0]['requested_quantity'], 2)

    @patch('app.services.equipment_availability_service.supabase_request')
    def test_partial_availability_uses_shared_database_calculation(self, query):
        query.side_effect = [
            {'id': 'tech-user'},
            [{
                'equipment_id': 10,
                'equipment_type': 'Projector',
                'equipment_model': 'PX-500',
                'available_quantity': 2,
            }],
        ]

        response = self.client.get(
            '/api/equipment-availability?equipment_type=Projector&quantity=3&start_datetime=2026-10-01T10:00:00Z&end_datetime=2026-10-01T12:00:00Z',
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['results'][0]['available_quantity'], 2)
        self.assertEqual(response.json['results'][0]['fulfillment_status'], 'partially_available')
        self.assertEqual(response.json['results'][0]['requested_quantity'], 3)
        self.assertEqual(query.call_args.args[0], '/rest/v1/rpc/equipment_window_availability')
        self.assertEqual(query.call_args.kwargs['payload']['p_start'], '2026-10-01T10:00:00+00:00')
        self.assertEqual(query.call_args.kwargs['payload']['p_end'], '2026-10-01T12:00:00+00:00')

    @patch('app.services.equipment_availability_service.supabase_request')
    def test_check_equipment_availability_returns_no_suitable_equipment_message(self, query):
        query.side_effect = [
            {'id': 'tech-user'},
            [{
                'equipment_id': 11,
                'equipment_type': 'Microphone',
                'equipment_model': 'M-100',
                'total_quantity': 2,
                'available_quantity': 2,
            }],
        ]

        response = self.client.get(
            '/api/equipment-availability?equipment_type=Projector&quantity=2&start_datetime=2026-10-01T09:00:00Z&end_datetime=2026-10-01T12:00:00Z',
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['results'], [])
        self.assertEqual(response.json['message'], 'No suitable equipment is available for the selected criteria.')

    @patch('app.services.equipment_availability_service.supabase_request')
    def test_rejects_invalid_quantity(self, query):
        response = self.client.get(
            '/api/equipment-availability?equipment_type=Projector&quantity=0&start_datetime=2026-10-01T09:00:00Z&end_datetime=2026-10-01T12:00:00Z',
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('quantity must be a whole number greater than zero.', response.json['error'])
        query.assert_not_called()

    @patch('app.services.equipment_availability_service.supabase_request')
    def test_rejects_end_before_start(self, query):
        response = self.client.get(
            '/api/equipment-availability?equipment_type=Projector&quantity=2&start_datetime=2026-10-01T13:00:00Z&end_datetime=2026-10-01T12:00:00Z',
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Required end date and time must be later than the start date and time.', response.json['error'])
        query.assert_not_called()

    @patch('app.services.equipment_availability_service.supabase_request')
    def test_requires_authenticated_user(self, query):
        query.return_value = {}

        response = self.client.get(
            '/api/equipment-availability?equipment_type=Projector&quantity=2&start_datetime=2026-10-01T09:00:00Z&end_datetime=2026-10-01T12:00:00Z',
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json['error'], 'Authentication required.')


if __name__ == '__main__':
    unittest.main()
