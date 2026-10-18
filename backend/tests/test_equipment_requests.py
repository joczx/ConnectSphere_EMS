
import unittest
from unittest.mock import patch

from app import create_app
from app.services.equipment_request_service import (
    EquipmentRequestError,
    create_equipment_request,
)


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

    def test_list_equipment_requests_uses_event_access_result_without_treating_it_as_identity(self):
        event = {'event_id': 2, 'event_coordinator_id': 'coordinator-1'}
        with patch(
            'app.routes.equipment_requests.require_event_access',
            return_value=event,
        ) as authorize, patch(
            'app.routes.equipment_requests.list_equipment_requests',
            return_value=[],
        ) as listing:
            response = self.client.get(
                '/api/events/2/equipment-requests',
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'count': 0, 'equipment_requests': []})
        authorize.assert_called_once_with(2)
        listing.assert_called_once_with(2)

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

    def test_create_equipment_request_requires_auth(self):
        response = self.client.post('/api/events/2/equipment-requests', json={})

        self.assertEqual(response.status_code, 401)
        self.assertIn('Authentication required.', response.json['error'])

    def test_store_error_is_returned_by_route(self):
        from app.services.event_store import StoreError

        with patch(
            'app.routes.equipment_requests.list_equipment_requests',
            side_effect=StoreError(503, 'Database unavailable'),
        ):
            response = self.client.get('/api/events/2/equipment-requests', headers=self.headers)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {'error': 'Database unavailable'})

    def test_create_request_rejects_invalid_payload_fields(self):
        invalid_payloads = (
            None,
            [],
            {'equipment_type': 'Projector', 'quantity': 1, 'technical_requirements': 1},
            {'equipment_type': '  ', 'quantity': 1},
        )
        for payload in invalid_payloads:
            responses = [{'id': 'user'}, [{'event_id': 1}]] if isinstance(payload, dict) else []
            with self.subTest(payload=payload), patch(
                'app.services.equipment_request_service.supabase_request', side_effect=responses,
            ):
                with self.assertRaises(EquipmentRequestError):
                    create_equipment_request(1, payload, 'token')

    def test_create_request_rejects_missing_user_or_unavailable_event(self):
        payload = {'equipment_type': 'Projector', 'quantity': 1}
        with patch('app.services.equipment_request_service.supabase_request', return_value={}):
            with self.assertRaises(EquipmentRequestError):
                create_equipment_request(1, payload, 'token')
        with patch('app.services.equipment_request_service.supabase_request', side_effect=[{'id': 'user'}, []]):
            with self.assertRaises(EquipmentRequestError):
                create_equipment_request(1, payload, 'token')

    def test_create_request_keeps_record_when_database_returns_no_representation(self):
        with patch('app.services.equipment_request_service.supabase_request', side_effect=[{'id': 'user'}, [{'event_id': 1}], []]):
            record = create_equipment_request(1, {'equipment_type': ' Projector ', 'quantity': 1}, 'token')
        self.assertEqual(record['equipment_type'], 'Projector')
        self.assertIsNone(record['technical_requirements'])


if __name__ == '__main__':
    unittest.main()
