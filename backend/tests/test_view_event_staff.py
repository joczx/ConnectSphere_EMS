"""Unit tests for viewing the staff assigned to an event. Supabase is mocked.

User story SCRUM-273: "As an authorised user, I want to view the Venue Staff,
Technical Support Staff, and Safety Officer assigned to an event so that I know
which staff members are responsible for the venue arrangements, technical
requirements, and operational safety."

  AC1  The event information page shows which staff are assigned to the event.
"""

import unittest
from unittest.mock import patch

from app import create_app

EVENT_ID = 7
VENUE_STAFF = '11111111-1111-1111-1111-111111111111'
TECHNICAL_SUPPORT = '22222222-2222-2222-2222-222222222222'
SAFETY_OFFICER = '33333333-3333-3333-3333-333333333333'
USER = {'id': 'user-id'}


class ViewEventStaffTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.headers = {'Authorization': 'Bearer user-token'}

    # TC-VES-001 (AC1, happy): the event information includes all three
    # assigned staff members.
    @patch('app.routes.events.supabase_request')
    def test_event_information_includes_assigned_staff(self, query):
        query.side_effect = [USER, [{
            'event_id': EVENT_ID,
            'venue_staff_id': VENUE_STAFF,
            'technical_support_id': TECHNICAL_SUPPORT,
            'safety_officer_id': SAFETY_OFFICER,
        }]]

        response = self.client.get(f'/api/events/{EVENT_ID}', headers=self.headers)

        self.assertEqual(response.status_code, 200)
        event = response.json['event']
        self.assertEqual(event['venue_staff_id'], VENUE_STAFF)
        self.assertEqual(event['technical_support_id'], TECHNICAL_SUPPORT)
        self.assertEqual(event['safety_officer_id'], SAFETY_OFFICER)

    # TC-VES-002 (AC1, happy): the assigned staff IDs resolve to the names the
    # page displays.
    @patch('app.routes.users.supabase_request')
    def test_assigned_staff_ids_resolve_to_names(self, query):
        query.side_effect = [USER, [
            {'user_id': VENUE_STAFF, 'name': 'Vera Venue', 'email': 'vera@example.com'},
            {'user_id': TECHNICAL_SUPPORT, 'name': 'Theo Tech', 'email': 'theo@example.com'},
            {'user_id': SAFETY_OFFICER, 'name': 'Sam Safety', 'email': 'sam@example.com'},
        ]]

        response = self.client.get(
            f'/api/users?ids={VENUE_STAFF},{TECHNICAL_SUPPORT},{SAFETY_OFFICER}',
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['users'], {
            VENUE_STAFF: 'Vera Venue',
            TECHNICAL_SUPPORT: 'Theo Tech',
            SAFETY_OFFICER: 'Sam Safety',
        })

    # TC-VES-003 (AC1, negative): whichever role nobody is assigned to comes back
    # empty rather than causing an error, and the other staff are still returned.
    @patch('app.routes.events.supabase_request')
    def test_unassigned_staff_role_is_returned_empty(self, query):
        assigned = {
            'venue_staff_id': VENUE_STAFF,
            'technical_support_id': TECHNICAL_SUPPORT,
            'safety_officer_id': SAFETY_OFFICER,
        }
        for unassigned in assigned:
            with self.subTest(unassigned=unassigned):
                expected = {'event_id': EVENT_ID, **assigned, unassigned: None}
                query.side_effect = [USER, [expected]]

                response = self.client.get(f'/api/events/{EVENT_ID}', headers=self.headers)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['event'], expected)


    # TC-VES-004 (AC1, negative): a user the database does not let see the event
    # gets a 404 with no staff details.
    @patch('app.routes.events.supabase_request')
    def test_user_without_access_to_the_event_sees_no_staff(self, query):
        query.side_effect = [USER, []]

        response = self.client.get(f'/api/events/{EVENT_ID}', headers=self.headers)

        self.assertEqual(response.status_code, 404)
        self.assertNotIn('event', response.json)

    # TC-VES-005 (AC1, edge): a staff member whose account has a blank name is
    # still shown, by the part of their email address before the @.
    @patch('app.routes.users.supabase_request')
    def test_staff_member_with_a_blank_name_is_shown_by_email(self, query):
        query.side_effect = [USER, [
            {'user_id': VENUE_STAFF, 'name': '  ', 'email': 'vera.venue@example.com'},
        ]]

        response = self.client.get(f'/api/users?ids={VENUE_STAFF}', headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['users'], {VENUE_STAFF: 'vera.venue'})


class ViewEventStaffLookupTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.headers = {'Authorization': 'Bearer user-token'}

    # TC-VES-006 (AC1, edge): an event identified by a UUID shows its staff, and an id that is
    # neither a number nor a UUID is refused before the database is read.
    @patch('app.routes.events.supabase_request')
    def test_staff_are_shown_for_a_uuid_event_and_an_invalid_id_is_refused(self, query):
        event_uuid = '44bc334e-6a1f-4c2b-9d3e-5f7a8b9c0d1e'
        assigned = {
            'event_id': event_uuid,
            'venue_staff_id': VENUE_STAFF,
            'technical_support_id': TECHNICAL_SUPPORT,
            'safety_officer_id': SAFETY_OFFICER,
        }
        query.side_effect = [USER, [assigned]]

        response = self.client.get(f'/api/events/{event_uuid}', headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['event'], assigned)

        query.side_effect = [USER]
        response = self.client.get('/api/events/not-an-event', headers=self.headers)

        self.assertEqual(response.status_code, 404)
        self.assertNotIn('event', response.json)
        self.assertEqual(query.call_count, 3)

    # TC-VES-007 (AC1, edge): a staff account with neither a name nor an email is left out
    # rather than shown blank.
    @patch('app.routes.users.supabase_request')
    def test_staff_account_without_a_name_or_email_is_left_out(self, query):
        query.side_effect = [USER, [
            {'user_id': VENUE_STAFF, 'name': 'Vera Venue', 'email': 'vera@example.com'},
            {'user_id': TECHNICAL_SUPPORT, 'name': None, 'email': None},
        ]]

        response = self.client.get(f'/api/users?ids={VENUE_STAFF},{TECHNICAL_SUPPORT}', headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['users'], {VENUE_STAFF: 'Vera Venue'})


if __name__ == '__main__':
    unittest.main()
