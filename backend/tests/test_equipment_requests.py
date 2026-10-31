
import unittest
from unittest.mock import patch

from app import create_app
from app.services.event_store import StoreError
from app.services.equipment_request_service import (
    EquipmentRequestError,
    create_equipment_request,
)


class EquipmentRequestRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.headers = {'Authorization': 'Bearer user-token'}

    @patch('app.services.equipment_request_service.supabase_request')
    # Lists the equipment requests already submitted for one event.
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
    # Creates a complete equipment request and returns the submission confirmation.
    def test_create_equipment_request_success(self, query):
        query.side_effect = [
            {'id': 'user-1'},
            [{'event_id': 2, 'event_coordinator_id': 'user-1', 'status': 'planning'}],
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
    # Rejects a new request that omits its equipment type.
    def test_create_equipment_request_requires_equipment_type(self, query):
        query.side_effect = [
            {'id': 'user-1'},
            [{'event_id': 2, 'event_coordinator_id': 'user-1', 'status': 'planning'}],
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
    # Rejects a new request with a non-positive quantity.
    def test_create_equipment_request_validates_quantity(self, query):
        query.side_effect = [
            {'id': 'user-1'},
            [{'event_id': 2, 'event_coordinator_id': 'user-1', 'status': 'planning'}],
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
    # Requires authentication before listing an event's equipment requests.
    def test_list_equipment_requests_requires_auth(self, query):
        response = self.client.get('/api/events/2/equipment-requests')

        self.assertEqual(response.status_code, 401)
        self.assertIn('Authentication required.', response.json['error'])

    # Requires authentication before a request can be submitted.
    def test_create_equipment_request_requires_auth(self):
        response = self.client.post('/api/events/2/equipment-requests', json={})

        self.assertEqual(response.status_code, 401)
        self.assertIn('Authentication required.', response.json['error'])

    # Returns a storage failure from the request-list endpoint.
    def test_store_error_is_returned_by_route(self):
        from app.services.event_store import StoreError

        with patch(
            'app.routes.equipment_requests.list_equipment_requests',
            side_effect=StoreError(503, 'Database unavailable'),
        ):
            response = self.client.get('/api/events/2/equipment-requests', headers=self.headers)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {'error': 'Database unavailable'})

    # Rejects malformed request bodies and invalid optional technical requirements.
    def test_create_request_rejects_invalid_payload_fields(self):
        invalid_payloads = (
            None,
            [],
            {'equipment_type': 'Projector', 'quantity': 1, 'technical_requirements': 1},
            {'equipment_type': '  ', 'quantity': 1},
        )
        for payload in invalid_payloads:
            responses = [{'id': 'user'}, [{'event_id': 1, 'event_coordinator_id': 'user', 'status': 'planning'}]] if isinstance(payload, dict) else []
            with self.subTest(payload=payload), patch(
                'app.services.equipment_request_service.supabase_request', side_effect=responses,
            ):
                with self.assertRaises(EquipmentRequestError):
                    create_equipment_request(1, payload, 'token')

    # Rejects request creation when the caller is unauthenticated or the event cannot be found.
    def test_create_request_rejects_missing_user_or_unavailable_event(self):
        payload = {'equipment_type': 'Projector', 'quantity': 1}
        with patch('app.services.equipment_request_service.supabase_request', return_value={}):
            with self.assertRaises(EquipmentRequestError):
                create_equipment_request(1, payload, 'token')
        with patch('app.services.equipment_request_service.supabase_request', side_effect=[{'id': 'user'}, []]):
            with self.assertRaises(EquipmentRequestError):
                create_equipment_request(1, payload, 'token')

    # Prevents a coordinator from requesting equipment for an event assigned to someone else.
    def test_only_assigned_event_coordinator_can_create_a_request(self):
        payload = {'equipment_type': 'Projector', 'quantity': 1}
        with patch(
            'app.services.equipment_request_service.supabase_request',
            side_effect=[
                {'id': 'different-user'},
                [{'event_id': 1, 'event_coordinator_id': 'assigned-coordinator', 'status': 'planning'}],
            ],
        ) as query:
            with self.assertRaises(EquipmentRequestError) as raised:
                create_equipment_request(1, payload, 'token')

        self.assertEqual(raised.exception.status, 403)
        self.assertIn('assigned Event Coordinator', raised.exception.message)
        self.assertEqual(query.call_count, 2)

    # Prevents equipment requests after an event leaves the planning stage.
    def test_create_request_only_while_event_is_planning(self):
        payload = {'equipment_type': 'Projector', 'quantity': 1}
        for status in ('pending_safety_checks', 'confirmed', 'completed', 'cancelled'):
            with self.subTest(status=status), patch(
                'app.services.equipment_request_service.supabase_request',
                side_effect=[{'id': 'user'}, [{'event_id': 1, 'event_coordinator_id': 'user', 'status': status}]],
            ) as query:
                with self.assertRaises(EquipmentRequestError) as raised:
                    create_equipment_request(1, payload, 'token')
            self.assertEqual(raised.exception.status, 409)
            self.assertEqual(query.call_count, 2)

    # Preserves the normalized request record when the database returns no representation.
    def test_create_request_keeps_record_when_database_returns_no_representation(self):
        with patch('app.services.equipment_request_service.supabase_request', side_effect=[{'id': 'user'}, [{'event_id': 1, 'event_coordinator_id': 'user', 'status': 'planning'}], []]):
            record = create_equipment_request(1, {'equipment_type': ' Projector ', 'quantity': 1}, 'token')
        self.assertEqual(record['equipment_type'], 'Projector')
        self.assertIsNone(record['technical_requirements'])


class EquipmentRequestEditTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.headers = {'Authorization': 'Bearer user-token'}
        self.pending = [{'equipment_request_id': 15, 'status': 'pending'}]

    @patch('app.services.equipment_request_service.supabase_request')
    # Updates a pending request and normalizes blank optional requirements to null.
    def test_pending_request_can_be_edited(self, query):
        query.side_effect = [self.pending, [{'equipment_request_id': 15, 'quantity': 3, 'status': 'pending'}]]

        response = self.client.patch(
            '/api/events/2/equipment-requests/15', json={'quantity': 3, 'technical_requirements': '  '}, headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['equipment_request']['quantity'], 3)
        path = query.call_args.args[0]
        self.assertIn('status=eq.pending', path)
        self.assertEqual(query.call_args.kwargs['method'], 'PATCH')
        self.assertEqual(query.call_args.kwargs['payload'], {'quantity': 3, 'technical_requirements': None})

    @patch('app.services.equipment_request_service.supabase_request')
    # Rejects unsupported or invalid fields before querying the database.
    def test_edit_validates_fields_before_touching_the_database(self, query):
        for body in ({'quantity': 0}, {'equipment_type': ' '}, {'technical_requirements': 4}, {}, {'status': 'accepted'}):
            response = self.client.patch('/api/events/2/equipment-requests/15', json=body, headers=self.headers)
            self.assertEqual(response.status_code, 400, body)
        query.assert_not_called()

    @patch('app.services.equipment_request_service.supabase_request')
    # Requires an object-shaped JSON body when editing a request.
    def test_edit_requires_a_json_object(self, query):
        response = self.client.patch('/api/events/2/equipment-requests/15', json=[], headers=self.headers)

        self.assertEqual(response.status_code, 400)
        self.assertIn('provided as JSON', response.json['error'])
        query.assert_not_called()

    @patch('app.services.equipment_request_service.supabase_request')
    # Prevents edits and deletion once Technical Support has reviewed a request.
    def test_reviewed_request_cannot_be_edited_or_deleted(self, query):
        query.return_value = [{'equipment_request_id': 15, 'status': 'accepted'}]

        edited = self.client.patch('/api/events/2/equipment-requests/15', json={'quantity': 3}, headers=self.headers)
        deleted = self.client.delete('/api/events/2/equipment-requests/15', headers=self.headers)

        self.assertEqual(edited.status_code, 409)
        self.assertEqual(deleted.status_code, 409)
        self.assertEqual(query.call_count, 2)

    @patch('app.services.equipment_request_service.supabase_request')
    # Returns not found when the requested equipment request does not exist.
    def test_missing_request_is_not_found(self, query):
        query.return_value = []

        response = self.client.delete('/api/events/2/equipment-requests/99', headers=self.headers)

        self.assertEqual(response.status_code, 404)

    @patch('app.services.equipment_request_service.supabase_request')
    # Deletes a still-pending equipment request.
    def test_pending_request_can_be_deleted(self, query):
        query.side_effect = [self.pending, [{'equipment_request_id': 15}]]

        response = self.client.delete('/api/events/2/equipment-requests/15', headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['message'], 'Equipment request deleted.')
        self.assertEqual(query.call_args.kwargs['method'], 'DELETE')

    @patch('app.services.equipment_request_service.supabase_request')
    # Handles a review decision that occurs after a request edit has been checked.
    def test_request_reviewed_during_the_change_is_a_conflict(self, query):
        query.side_effect = [self.pending, []]

        response = self.client.patch('/api/events/2/equipment-requests/15', json={'quantity': 3}, headers=self.headers)

        self.assertEqual(response.status_code, 409)

    @patch('app.services.equipment_request_service.supabase_request')
    # Prevents deletion while a linked equipment reservation still exists.
    def test_reserved_request_cannot_be_deleted(self, query):
        query.side_effect = [self.pending, StoreError(503, code='23503')]

        response = self.client.delete('/api/events/2/equipment-requests/15', headers=self.headers)

        self.assertEqual(response.status_code, 409)
        self.assertIn('release the reservation', response.json['error'])

    @patch('app.services.equipment_request_service.supabase_request')
    # Returns unexpected storage failures instead of converting them to a deletion conflict.
    def test_unexpected_delete_storage_error_is_returned(self, query):
        query.side_effect = [self.pending, StoreError(503, 'Database unavailable')]

        response = self.client.delete('/api/events/2/equipment-requests/15', headers=self.headers)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {'error': 'Database unavailable'})

    @patch('app.services.equipment_request_service.supabase_request')
    # Handles a review decision that occurs after a deletion has been checked.
    def test_request_reviewed_during_delete_is_a_conflict(self, query):
        query.side_effect = [self.pending, []]

        response = self.client.delete('/api/events/2/equipment-requests/15', headers=self.headers)

        self.assertEqual(response.status_code, 409)

    @patch('app.services.equipment_request_service.supabase_request')
    # Allows a coordinator to explicitly clear optional technical requirements.
    def test_edit_can_clear_optional_technical_requirements(self, query):
        query.side_effect = [self.pending, [{'equipment_request_id': 15, 'technical_requirements': None}]]

        response = self.client.patch(
            '/api/events/2/equipment-requests/15',
            json={'technical_requirements': None}, headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(query.call_args.kwargs['payload']['technical_requirements'])

    # Requires authentication before an equipment request can be edited or deleted.
    def test_edit_and_delete_require_auth(self):
        self.assertEqual(self.client.patch('/api/events/2/equipment-requests/15', json={'quantity': 1}).status_code, 401)
        self.assertEqual(self.client.delete('/api/events/2/equipment-requests/15').status_code, 401)


if __name__ == '__main__':
    unittest.main()
