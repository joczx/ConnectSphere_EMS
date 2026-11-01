import unittest
from unittest.mock import patch

from app import create_app
from app.services.equipment_availability_service import (
    EquipmentAvailabilityError,
    check_equipment_availability,
)


class EquipmentAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.headers = {'Authorization': 'Bearer user-token'}

    @patch('app.services.equipment_availability_service.supabase_request')
    # Returns available equipment when an authorized Technical Support user supplies valid criteria.
    def test_technical_support_can_check_equipment_availability(self, query):
        query.side_effect = [
            {'id': 'tech-user'},
            True,
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
    # Marks equipment as partially available when stock is below the requested quantity.
    def test_partial_availability_uses_shared_database_calculation(self, query):
        query.side_effect = [
            {'id': 'tech-user'},
            True,
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
    # Returns a clear no-results message when no matching equipment is available.
    def test_check_equipment_availability_returns_no_suitable_equipment_message(self, query):
        query.side_effect = [
            {'id': 'tech-user'},
            True,
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
    # Rejects a zero quantity before querying equipment availability.
    def test_rejects_invalid_quantity(self, query):
        response = self.client.get(
            '/api/equipment-availability?equipment_type=Projector&quantity=0&start_datetime=2026-10-01T09:00:00Z&end_datetime=2026-10-01T12:00:00Z',
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('quantity must be a whole number greater than zero.', response.json['error'])
        query.assert_not_called()

    @patch('app.services.equipment_availability_service.supabase_request')
    # Rejects availability periods whose end is not later than their start.
    def test_rejects_end_before_start(self, query):
        response = self.client.get(
            '/api/equipment-availability?equipment_type=Projector&quantity=2&start_datetime=2026-10-01T13:00:00Z&end_datetime=2026-10-01T12:00:00Z',
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Required end date and time must be later than the start date and time.', response.json['error'])
        query.assert_not_called()

    @patch('app.services.equipment_availability_service.supabase_request')
    # Requires a verified user identity before checking availability.
    def test_requires_authenticated_user(self, query):
        query.return_value = {}

        response = self.client.get(
            '/api/equipment-availability?equipment_type=Projector&quantity=2&start_datetime=2026-10-01T09:00:00Z&end_datetime=2026-10-01T12:00:00Z',
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json['error'], 'Authentication required.')

    @patch('app.services.equipment_availability_service.supabase_request')
    # Prevents a non-Technical Support user from checking the equipment catalogue.
    def test_non_technical_user_cannot_check_equipment_availability(self, query):
        query.side_effect = [{'id': 'coordinator-user'}, False]

        response = self.client.get(
            '/api/equipment-availability?equipment_type=Projector&quantity=2&start_datetime=2026-10-01T09:00:00Z&end_datetime=2026-10-01T12:00:00Z',
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn('Only Technical Support Staff', response.json['error'])
        self.assertEqual(query.call_count, 2)

    # Rejects non-object requests and missing or blank equipment types.
    def test_availability_rejects_non_object_or_missing_equipment_type(self):
        for payload in (None, [], {'equipment_type': None}, {'equipment_type': '  '}):
            with self.subTest(payload=payload):
                with self.assertRaises(EquipmentAvailabilityError):
                    check_equipment_availability(payload, 'token')

    # Rejects malformed quantities and date-time values during availability validation.
    def test_availability_rejects_invalid_quantities_and_datetimes(self):
        valid = {
            'equipment_type': 'Projector', 'quantity': 1,
            'start_datetime': '2026-10-01T09:00:00Z',
            'end_datetime': '2026-10-01T10:00:00Z',
        }
        for payload in (
            {**valid, 'quantity': 'not-a-number'},
            {**valid, 'quantity': None},
            {**valid, 'start_datetime': None},
            {**valid, 'end_datetime': 1},
            {**valid, 'start_datetime': '2026-10-01T09:00:00'},
            {**valid, 'end_datetime': 'not-a-date'},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(EquipmentAvailabilityError):
                    check_equipment_availability(payload, 'token')

    @patch('app.services.equipment_availability_service.supabase_request')
    # Ignores malformed, different-type, and zero-stock catalogue records.
    def test_skips_malformed_unmatched_and_unavailable_catalogue_items(self, query):
        query.side_effect = [
            {'id': 'user'},
            True,
            [None, {'equipment_type': '  '}, {'equipment_type': 'Microphone'}, {
                'equipment_id': 10, 'equipment_type': 'Projector', 'available_quantity': 0,
            }],
        ]
        result = check_equipment_availability({
            'equipment_type': 'Projector', 'quantity': 1,
            'start_datetime': '2026-10-01T09:00:00Z',
            'end_datetime': '2026-10-01T10:00:00Z',
        }, 'token')
        self.assertEqual(result['results'], [])


if __name__ == '__main__':
    unittest.main()
