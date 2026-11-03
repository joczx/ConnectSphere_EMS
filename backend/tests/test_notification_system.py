from pathlib import Path
import unittest
from unittest.mock import patch
import pytest
from app import create_app
from app.services.event_store import StoreError

# S1 is the notification API (app/routes/notifications.py). S2-S12 are database
# triggers, so their tests check the migration that defines each one; the
# integration suite (tests/integration/test_notifications.py) runs them for real.

HEADERS = {'Authorization': 'Bearer user-token'}
NOTIFICATIONS_URL = '/api/notifications'
LIST_RPC = '/rest/v1/rpc/list_my_notifications'
READ_RPC = '/rest/v1/rpc/mark_notification_read'
ITEMS = {'items': [{'notification_id': 7, 'title': 'New event request', 'read_at': None}], 'total': 1, 'unread': 1}
SUPABASE = Path(__file__).resolve().parents[2] / 'supabase'


def client():
    return create_app().test_client()


def migration(name):
    return ' '.join((SUPABASE / name).read_text(encoding='utf-8').split())


def function(name, migration_file):
    """One function, from its name to the end of its body, whitespace collapsed."""
    text = migration(migration_file)
    start = text.index(f'function public.{name}(')
    return text[start:text.index('$$;', text.index('$$', start) + 2) + 3]


def trigger(name, migration_file):
    text = migration(migration_file)
    start = text.index(f'create trigger {name} ')
    return text[start:text.index(';', start) + 1]


def assert_defines(checks):
    for definition, fragments in checks:
        for fragment in fragments:
            assert fragment in definition, f'{fragment!r} missing from {definition[:60]!r}...'


REQUEST = function('notify_event_request_submitted', '050_notify_requests_and_staff.sql')
ASSIGN = function('notify_coordinator_assignment', '047_notify_coordinator_assignment.sql')
STAFF = function('notify_event_staff_assigned', '050_notify_requests_and_staff.sql')
VENUE = function('notify_venue_booking_change', '051_notify_venue_bookings.sql')
HOLDS = function('expire_venue_holds', '051_notify_venue_bookings.sql')
CHANGE = function('notify_event_change_request', '055_notify_change_equipment_safety.sql')
EQUIPMENT = function('notify_equipment_request', '055_notify_change_equipment_safety.sql')
SAFETY = function('submit_event_for_safety_checks', '055_notify_change_equipment_safety.sql')
DECISION = function('notify_safety_decision', '055_notify_change_equipment_safety.sql')
REGISTRATION = function('notify_event_registration', '057_notify_event_registration.sql')
CANCELLED = function('notify_event_cancelled', '057_notify_event_registration.sql')


# ---------------------------------------------------------------------------
# S1 Notification system: the API behind the bell popup and the full page
# ---------------------------------------------------------------------------

# Verifies the bell popup asks for the caller's own newest 10 notifications.
@patch('app.routes.notifications.supabase_request', return_value=ITEMS)
@patch('app.routes.notifications.authenticated_token', return_value='user-token')
def test_popup_lists_the_newest_ten_for_the_signed_in_user(_, query):
    response = client().get(f'{NOTIFICATIONS_URL}?limit=10', headers=HEADERS)
    assert response.status_code == 200
    assert response.json == {**ITEMS, 'page_size': 20}
    query.assert_called_once_with(LIST_RPC, token='user-token', payload={'p_limit': 10, 'p_offset': 0, 'p_days': None})


class NotificationRegressionTests(unittest.TestCase):
    @patch('app.routes.notifications.supabase_request', return_value={
        'items': [{'notification_id': 8, 'notification_type': 'venue_hold_expired'}],
        'total': 1,
        'unread': 1,
    })
    @patch('app.routes.notifications.authenticated_token', return_value='user-token')
    def test_expired_venue_hold_notification_is_returned(self, _, query):
        response = client().get(f'{NOTIFICATIONS_URL}?limit=10', headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['items'], [
            {'notification_id': 8, 'notification_type': 'venue_hold_expired'}
        ])


# Verifies a full-page request reads 20 notifications from the last 14 days, skipping earlier pages.
@patch('app.routes.notifications.supabase_request', return_value=ITEMS)
@patch('app.routes.notifications.authenticated_token', return_value='user-token')
def test_full_page_reads_20_from_the_last_14_days(_, query):
    client().get(f'{NOTIFICATIONS_URL}?page=2', headers=HEADERS)
    assert query.call_args.kwargs['payload'] == {'p_limit': 20, 'p_offset': 20, 'p_days': 14}


# Verifies the full page opens on its first page when no page is given.
@patch('app.routes.notifications.supabase_request', return_value=ITEMS)
@patch('app.routes.notifications.authenticated_token', return_value='user-token')
def test_full_page_defaults_to_the_first_page(_, query):
    client().get(NOTIFICATIONS_URL, headers=HEADERS)
    assert query.call_args.kwargs['payload'] == {'p_limit': 20, 'p_offset': 0, 'p_days': 14}


# Ensures a page or popup size that is not a positive whole number is refused before reading.
@pytest.mark.parametrize('query_string', ['?page=0', '?page=-1', '?page=abc', '?limit=0', '?limit='])
@patch('app.routes.notifications.supabase_request')
@patch('app.routes.notifications.authenticated_token', return_value='user-token')
def test_invalid_page_or_limit_is_refused(_, query, query_string):
    response = client().get(NOTIFICATIONS_URL + query_string, headers=HEADERS)
    assert response.status_code == 400
    assert response.json == {'error': 'Use a positive whole number.'}
    query.assert_not_called()


# Ensures notifications cannot be listed or marked read without signing in.
@patch('app.routes.notifications.supabase_request')
def test_sign_in_is_required(query):
    browser = client()
    for response in (browser.get(NOTIFICATIONS_URL), browser.post(f'{NOTIFICATIONS_URL}/7/read')):
        assert response.status_code == 401
        assert response.json == {'error': 'Please sign in again.'}
    query.assert_not_called()


# Ensures a database refusal to list is passed on rather than shown as no notifications.
@patch('app.routes.notifications.supabase_request', return_value={'error': 'Please sign in again.', 'status': 401})
@patch('app.routes.notifications.authenticated_token', return_value='user-token')
def test_list_passes_on_a_database_refusal(_, query):
    response = client().get(NOTIFICATIONS_URL, headers=HEADERS)
    assert response.status_code == 401
    assert response.json == {'error': 'Please sign in again.'}


# Ensures an unavailable database is reported, not mistaken for an empty notification list.
@patch('app.routes.notifications.supabase_request', side_effect=StoreError(503))
@patch('app.routes.notifications.authenticated_token', return_value='user-token')
def test_storage_failure_is_reported(_, query):
    response = client().get(NOTIFICATIONS_URL, headers=HEADERS)
    assert response.status_code == 503
    assert response.json == {'error': 'Event service is temporarily unavailable.'}


# Verifies opening a notification marks that notification read for the caller.
@patch('app.routes.notifications.supabase_request', return_value={'notification_id': 5})
@patch('app.routes.notifications.authenticated_token', return_value='user-token')
def test_opening_a_notification_marks_it_read(_, query):
    response = client().post(f'{NOTIFICATIONS_URL}/5/read', headers=HEADERS)
    assert response.status_code == 200
    assert response.json == {'notification_id': 5}
    query.assert_called_once_with(READ_RPC, token='user-token', payload={'p_notification_id': 5})


# Ensures marking another user's notification read is refused as not found.
@patch('app.routes.notifications.supabase_request', return_value={'error': 'Notification not found.', 'status': 404})
@patch('app.routes.notifications.authenticated_token', return_value='user-token')
def test_marking_someone_elses_notification_is_refused(_, query):
    response = client().post(f'{NOTIFICATIONS_URL}/5/read', headers=HEADERS)
    assert response.status_code == 404
    assert response.json == {'error': 'Notification not found.'}


# ---------------------------------------------------------------------------
# S2-S12: each case is one acceptance criterion's trigger, recipient and message
# ---------------------------------------------------------------------------

# Verifies the Event Coordinator Lead is told of each submitted request, with names and a link to it.
@pytest.mark.parametrize('checks', [
    pytest.param([(trigger('notify_event_request_submitted', '046_notification_service.sql'),
                   ['after insert or update of status on public.event_request']),
                  (REQUEST, ["if new.status = 'submitted' and (tg_op = 'INSERT' or old.status is distinct from 'submitted') "
                             "then perform public.notify_role('event_coordinator_lead', 'event_request_submitted', 'New event request',"])],
                 id='AC1'),
    pytest.param([(REQUEST, ["request text := coalesce(new.event_name",
                             "format('Event request for %s by %s received and pending coordinator assignment.', request, "
                             "coalesce((select name from public.users where user_id = new.event_organiser_id)"])], id='AC2'),
    pytest.param([(REQUEST, ["'/assign-event-coordinators?request=' || new.event_request_id"])], id='AC3'),
])
def test_s2_lead_is_notified_of_submitted_requests(checks):
    assert_defines(checks)


# Verifies coordinators are told of assignment and reassignment, and the previous coordinator of the transfer.
@pytest.mark.parametrize('checks', [
    pytest.param([(trigger('notify_coordinator_assignment', '047_notify_coordinator_assignment.sql'),
                   ['after update of event_coordinator_id on public.event_request']),
                  (ASSIGN, ["perform public.notify_user(new.event_coordinator_id, 'coordinator_assigned', 'Event assigned to you',",
                            "case when old.event_coordinator_id is null then 'assigned' else 'reassigned' end"])], id='AC1'),
    pytest.param([(ASSIGN, ['if new.event_coordinator_id is not distinct from old.event_coordinator_id then return null;'])],
                 id='AC1-unchanged'),
    pytest.param([(ASSIGN, ["item := format('%s by %s', coalesce(planned.event_name, new.event_name",
                            "'Event request %s has been %s to you by %s, pending review.'",
                            "'Event %s has been reassigned to you by %s. It is currently in %s.'"])], id='AC2'),
    pytest.param([(ASSIGN, ["if old.event_coordinator_id is not null then perform public.notify_user(old.event_coordinator_id, "
                            "'coordinator_unassigned', 'Event reassigned',",
                            "'%s %s has been reassigned from you to %s by %s.'"])], id='AC3'),
])
def test_s3_coordinator_is_notified_of_assignment(checks):
    assert_defines(checks)


# Verifies the Event Organiser is told of submission, approval and rejection.
@pytest.mark.parametrize('checks', [
    pytest.param([(REQUEST, ["perform public.notify_user(new.event_organiser_id, 'event_request_submitted', 'Event request submitted', "
                             "format('Your event request %s has been submitted and is awaiting review.'"])], id='AC1'),
    pytest.param([(REQUEST, ["elsif tg_op = 'UPDATE' and new.status in ('planning', 'rejected') and old.status is distinct from new.status then",
                             "'Event request approved', format('Your event request %s has been approved by %s. It is now in planning.'",
                             "'Event request rejected', format('Your event request %s has been rejected by %s. Reason: %s'"])],
                 id='AC2'),
])
def test_s4_organiser_is_notified_of_their_request(checks):
    assert_defines(checks)


# Verifies Venue Staff, Technical Support and Safety Officers are told of their event, and the Coordinator of them.
@pytest.mark.parametrize('checks', [
    pytest.param([(trigger('notify_event_staff_assigned', '050_notify_requests_and_staff.sql'), ['after insert on public.events']),
                  (STAFF, ["(new.venue_staff_id, 'Venue Staff',", "(new.technical_support_id, 'Technical Support',",
                           "(new.safety_officer_id, 'Safety Officer',",
                           "if staff.user_id is not null then perform public.notify_user(staff.user_id, 'event_staff_assigned', "
                           "'Event assigned to you',"])], id='AC1'),
    pytest.param([(STAFF, ["details text := format('%s by %s (%s – %s SGT)', coalesce(new.event_name",
                           "format('Event %s has been assigned to you as %s. Event Coordinator: %s.', details, staff.role, coordinator)"])],
                 id='AC2'),
    pytest.param([(STAFF, ["perform public.notify_user(new.event_coordinator_id, 'event_staff_assigned', 'Staff assigned to your event', "
                           "format('Staff assigned to %s: %s.'"])], id='AC3'),
])
def test_s5_staff_are_notified_of_their_event(checks):
    assert_defines(checks)


# Verifies venue booking requests and their outcomes reach the Coordinator and the event's Venue Staff.
@pytest.mark.parametrize('checks', [
    pytest.param([(trigger('notify_venue_booking_change', '051_notify_venue_bookings.sql'), ['after insert or update of status']),
                  (VENUE, ["if tg_op = 'INSERT' then if new.status = 'submitted' then perform public.notify_user(new.requested_by, "
                           "'venue_booking_submitted', 'Venue booking request submitted',"])], id='AC1'),
    pytest.param([(VENUE, ["perform public.notify_user((select venue_staff_id from public.events where event_id = new.event_id), "
                           "'venue_booking_submitted', 'New venue booking request',",
                           "'/review-venue-bookings/' || new.booking_id"])], id='AC2'),
    pytest.param([(VENUE, ["if old.status = 'submitted' and new.status in ('approved', 'rejected') then perform public.notify_user("
                           "new.requested_by, 'venue_booking_' || new.status, 'Venue booking ' || new.status,",
                           "' Reason: ' || coalesce(new.review_comments, 'none given')"])], id='AC3'),
    pytest.param([(VENUE, ["booking text := format('%s for %s (%s – %s SGT)', venue, coalesce(new.event_name, 'an unnamed event')",
                           'Status: pending Venue Staff review.', "has been %s by %s.%s', booking, new.status"])], id='AC4'),
])
def test_s6_venue_booking_requests_are_notified(checks):
    assert_defines(checks)


# Verifies the Coordinator is told when a venue becomes unavailable over their booking or pending request.
@pytest.mark.parametrize('checks', [
    pytest.param([(VENUE, ["elsif new.status = 'cancelled' and new.cancellation_reason like 'Venue unavailable: %' then",
                           "perform public.notify_user(new.requested_by, 'venue_unavailable', 'Venue unavailable',",
                           "case when old.status = 'approved' then 'approved booking of'"])], id='AC1'),
    pytest.param([(VENUE, ["'%s is unavailable from %s to %s SGT (%s), which affects your %s %s. It has been cancelled.', venue",
                           'block.reason',
                           "tstzrange(k.starts_at, k.ends_at, '[)') && tstzrange(new.occupied_from, new.occupied_until, '[)')"])],
                 id='AC2'),
    pytest.param([(VENUE, ["else 'pending booking request for' end, booking)"])], id='AC3'),
])
def test_s7_venue_unavailability_is_notified(checks):
    assert_defines(checks)


# Verifies tentative holds are notified when placed, reminded once before expiry, and notified when expired.
@pytest.mark.parametrize('checks', [
    pytest.param([(trigger('notify_venue_booking_change', '051_notify_venue_bookings.sql'),
                   ['hold_expires_at on public.venue_booking_requests']),
                  (VENUE, ["elsif old.hold_expires_at is null and new.hold_expires_at is not null and new.status = 'submitted' "
                           "then perform public.notify_user(new.requested_by, 'venue_hold_placed', 'Tentative hold placed',"])],
                 id='AC1'),
    pytest.param([(VENUE, ["expiry text := to_char(new.hold_expires_at at time zone 'Asia/Singapore'",
                           "format('Venue Staff have placed a tentative hold on %s. It expires on %s SGT.', booking, expiry)"])],
                 id='AC2'),
    pytest.param([(HOLDS, ["b.hold_expires_at <= now() + interval '24 hours'",
                           "and not exists (select 1 from public.notifications n where n.recipient_id = b.requested_by "
                           "and n.kind = 'venue_hold_reminder'",
                           "'Tentative hold expiring soon'"])], id='AC3-reminder'),
    pytest.param([(VENUE, ["elsif old.status = 'submitted' and new.status = 'expired' then perform public.notify_user("
                           "new.requested_by, 'venue_hold_expired', 'Tentative hold expired',"]),
                  (HOLDS, ["update public.venue_booking_requests set status = 'expired'"])], id='AC3-expired'),
])
def test_s8_tentative_holds_are_notified(checks):
    assert_defines(checks)


# Verifies event change requests are notified on submission and decision, with their changes.
@pytest.mark.parametrize('checks', [
    pytest.param([(trigger('notify_event_change_request', '055_notify_change_equipment_safety.sql'),
                   ['after insert or update of status on public.event_change_request']),
                  (CHANGE, ["perform public.notify_user(new.requested_by, 'event_change_submitted', 'Event change request submitted',"])],
                 id='AC1'),
    pytest.param([(CHANGE, ["perform public.notify_user(new.assigned_coordinator_id, 'event_change_submitted', 'New event change request',",
                            "'/review-event-change-requests/' || new.event_change_request_id"])], id='AC2'),
    pytest.param([(CHANGE, ['summary text := public.event_change_summary(new.changes);', 'Changes: %s']),
                  (function('event_change_summary', '055_notify_change_equipment_safety.sql'),
                   ["format('%s: %s → %s',", "when 'start_datetime' then 'Start'"]),
                  (function('event_change_value', '055_notify_change_equipment_safety.sql'),
                   ["to_char((p_value #>> '{}')::timestamptz at time zone 'Asia/Singapore'"])], id='AC3'),
    pytest.param([(CHANGE, ["elsif new.status in ('approved', 'rejected') and old.status is distinct from new.status then "
                            "perform public.notify_user(new.requested_by, 'event_change_' || new.status, 'Event change request ' || new.status,",
                            "' Reason: ' || coalesce(new.decision_reason, 'none given')"])], id='AC4'),
    pytest.param([(CHANGE, ["array[planned.venue_staff_id, planned.technical_support_id, planned.safety_officer_id]",
                            "'Event changes approved', format('Changes to %s have been approved. Changes: %s'"])], id='AC5'),
])
def test_s9_event_change_requests_are_notified(checks):
    assert_defines(checks)


# Verifies equipment requests are notified on submission and on acceptance or rejection.
@pytest.mark.parametrize('checks', [
    pytest.param([(trigger('notify_equipment_request', '055_notify_change_equipment_safety.sql'),
                   ['after insert or update of status on public.equipment_request']),
                  (EQUIPMENT, ["perform public.notify_user(new.requested_by, 'equipment_request_submitted', 'Equipment request submitted',"])],
                 id='AC1'),
    pytest.param([(EQUIPMENT, ["perform public.notify_user(planned.technical_support_id, 'equipment_request_submitted', "
                               "'New equipment request',"])], id='AC2'),
    pytest.param([(EQUIPMENT, ["item text := format('%s × %s', new.quantity, new.equipment_type);",
                               "'%s requested %s for %s (%s – %s SGT). Technical requirements: %s. Status: pending review.'"])],
                 id='AC3'),
    pytest.param([(EQUIPMENT, ["elsif new.status in ('accepted', 'rejected') and old.status is distinct from new.status then "
                               "perform public.notify_user(new.requested_by, 'equipment_request_' || new.status, "
                               "'Equipment request ' || new.status,",
                               "' Reason: ' || coalesce(new.reason_for_rejection, 'none given')"])], id='AC4'),
])
def test_s10_equipment_requests_are_notified(checks):
    assert_defines(checks)


# Verifies the Safety Officer is told of a safety review, and the Coordinator of its outcome.
@pytest.mark.parametrize('checks', [
    pytest.param([(SAFETY, ["perform public.notify_user(saved.safety_officer_id, 'safety_check_requested', 'Event awaiting safety check',"])],
                 id='AC1'),
    pytest.param([(SAFETY, ["format('%s (%s – %s SGT) has been submitted for safety checks by %s.', coalesce(saved.event_name",
                            "'/operational-safety-reviews/' || saved.event_id"])], id='AC2'),
    pytest.param([(trigger('notify_safety_decision', '055_notify_change_equipment_safety.sql'),
                   ['after insert on public.operational_safety_decision']),
                  (DECISION, ["perform public.notify_user(planned.event_coordinator_id, 'safety_review_' || new.outcome,",
                              "else 'Safety review ' || new.outcome end",
                              "'The safety review for %s (%s – %s SGT) has been %s by %s.%s'"])], id='AC3'),
    pytest.param([(DECISION, ["case new.outcome when 'changes_requested' then 'Safety changes requested'",
                              "case when new.outcome <> 'approved' then ' Remarks: ' || new.remarks || "
                              "' The event has returned to Planning.'"])], id='AC4'),
])
def test_s11_safety_reviews_are_notified(checks):
    assert_defines(checks)


# Verifies Attendees are told of registration, the waiting list, cancellation and withdrawal.
@pytest.mark.parametrize('checks', [
    pytest.param([(trigger('notify_event_registration', '057_notify_event_registration.sql'),
                   ['after insert or update of status on public.event_registration']),
                  (REGISTRATION, ["case new.status when 'registered' then 'Event registration confirmed'",
                                  "format('Your registration for %s is confirmed.', details)"])], id='AC1'),
    pytest.param([(function('event_registration_details', '057_notify_event_registration.sql'),
                   ["format('%s (%s – %s SGT)%s', p_event.event_name",
                    "coalesce(' at ' || (select v.venue_name from public.venue_booking_requests b",
                    "b.status = 'approved'"])], id='AC2'),
    pytest.param([(REGISTRATION, ["when 'waiting_list' then 'Added to waiting list'",
                                  "'%s is full, so you have been added to its waiting list instead. '",
                                  "'This does not confirm a place at the event.'"])], id='AC3'),
    pytest.param([(trigger('notify_event_cancelled', '057_notify_event_registration.sql'),
                   ["when (new.status = 'cancelled' and old.status is distinct from new.status)"]),
                  (CANCELLED, ["status in ('registered', 'waiting_list')",
                               "'Event cancelled', format('%s has been cancelled, so your registration no longer applies.'"])],
                 id='AC4'),
    pytest.param([(REGISTRATION, ["else 'Event registration withdrawn' end",
                                  "format('Your registration for %s has been withdrawn.', details)"])], id='AC5'),
])
def test_s12_attendee_registration_is_notified(checks):
    assert_defines(checks)
