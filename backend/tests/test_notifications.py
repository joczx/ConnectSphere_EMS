"""Notification system user stories, one test per acceptance criterion.

The API is tested with Supabase mocked. Notifications are created by database
functions, so those are tested by reading the migration that last defines each
one. Add each new notification story as its own class below.
"""
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app

MIGRATIONS = Path(__file__).parents[2] / "supabase"
LISTED = {"items": [{"notification_id": 1, "title": "New event request", "read_at": None}], "total": 1, "unread": 1}


def migration(name):
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def function(name, file):
    """One database function's definition, from the migration that last defines it."""
    sql = migration(file)
    start = sql.index(f"create or replace function public.{name}(")
    return sql[start:sql.index("\n$$;", start)]


def call(path, method="get", result=LISTED):
    with patch("app.routes.notifications.authenticated_token", return_value="user-token"), \
         patch("app.routes.notifications.supabase_request", return_value=result) as database:
        return getattr(create_app().test_client(), method)(path), database


class NotificationSystem(unittest.TestCase):
    """As an authenticated user, I want to receive and view in-app notifications relevant to me."""

    def test_backend_creates_and_stores_a_notification_for_one_user(self):
        self.assertIn("create table if not exists public.notifications (", migration("046_notification_service.sql"))
        self.assertIn("select p_recipient, p_kind, p_title, p_body, p_link",
                      function("notify_user", "046_notification_service.sql"))

    def test_backend_delivers_a_notification_to_everyone_holding_a_role(self):
        self.assertIn("where replace(lower(trim(r.role_name)), ' ', '_') = p_role",
                      function("notify_role", "046_notification_service.sql"))

    def test_popup_shows_the_newest_notifications(self):
        response, database = call("/api/notifications?limit=10")
        self.assertEqual(response.json["items"], LISTED["items"])
        self.assertEqual(database.call_args.kwargs["payload"], {"p_limit": 10, "p_offset": 0, "p_days": None})

    def test_full_page_shows_20_per_page_from_the_last_14_days(self):
        response, database = call("/api/notifications?page=3")
        self.assertEqual(database.call_args.kwargs["payload"], {"p_limit": 20, "p_offset": 40, "p_days": 14})
        self.assertEqual(response.json["page_size"], 20)
        response, database = call("/api/notifications?page=0")
        self.assertEqual(response.status_code, 400)
        database.assert_not_called()

    def test_users_retrieve_only_their_own_past_notifications_newest_first(self):
        listed = function("list_my_notifications", "046_notification_service.sql")
        for rule in ("where recipient_id = auth.uid()", "(p_days is null or created_at > now() - make_interval(days => p_days))",
                     "order by created_at desc", "where recipient_id = auth.uid() and read_at is null"):
            self.assertIn(rule, listed)

    def test_notifications_are_retrieved_only_when_signed_in(self):
        self.assertEqual(create_app().test_client().get("/api/notifications").status_code, 401)
        response, _ = call("/api/notifications", result={"error": "Please sign in again.", "status": 401})
        self.assertEqual(response.status_code, 401)

    def test_opening_a_notification_marks_it_read_once(self):
        response, database = call("/api/notifications/7/read", "post", {"notification_id": 7})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(database.call_args.kwargs["payload"], {"p_notification_id": 7})
        marked = function("mark_notification_read", "046_notification_service.sql")
        self.assertIn("set read_at = coalesce(read_at, now())", marked)
        self.assertIn("where notification_id = p_notification_id and recipient_id = auth.uid();", marked)

    def test_another_users_notification_cannot_be_marked_read(self):
        response, _ = call("/api/notifications/7/read", "post", {"error": "Notification not found.", "status": 404})
        self.assertEqual(response.status_code, 404)


class LeadNotifiedOfSubmission(unittest.TestCase):
    """As an Event Coordinator Lead, I want to receive notifications about any received event request submission."""

    notify = function("notify_event_request_submitted", "050_notify_requests_and_staff.sql")

    def test_every_lead_is_notified_when_a_request_is_submitted(self):
        self.assertIn("create trigger notify_event_request_submitted after insert or update of status on public.event_request",
                      migration("046_notification_service.sql"))
        self.assertIn("if new.status = 'submitted' and (tg_op = 'INSERT' or old.status is distinct from 'submitted') then", self.notify)
        self.assertIn("perform public.notify_role('event_coordinator_lead', 'event_request_submitted'", self.notify)

    def test_notification_names_the_event_and_its_organiser(self):
        self.assertIn("format('Event request for %s by %s received and pending coordinator assignment.', request,", self.notify)
        self.assertIn("coalesce((select name from public.users where user_id = new.event_organiser_id)", self.notify)

    def test_notification_opens_the_event_request(self):
        self.assertIn("'/assign-event-coordinators?request=' || new.event_request_id", self.notify)


class CoordinatorNotifiedOfAssignment(unittest.TestCase):
    """As an Event Coordinator, I want to receive a notification when an event is assigned or reassigned to me."""

    notify = function("notify_coordinator_assignment", "047_notify_coordinator_assignment.sql")

    def test_new_coordinator_is_notified_on_assignment_or_reassignment(self):
        self.assertIn("after update of event_coordinator_id on public.event_request",
                      migration("047_notify_coordinator_assignment.sql"))
        self.assertIn("perform public.notify_user(new.event_coordinator_id, 'coordinator_assigned'", self.notify)
        self.assertIn("case when old.event_coordinator_id is null then 'assigned' else 'reassigned' end", self.notify)

    def test_notification_names_the_event_organiser_and_lead(self):
        self.assertIn("item := format('%s by %s'", self.notify)
        self.assertIn("'Event request %s has been %s to you by %s, pending review.'", self.notify)
        self.assertIn("'Event %s has been reassigned to you by %s. It is currently in %s.'", self.notify)

    def test_previous_coordinator_is_notified_of_the_transfer(self):
        self.assertIn("perform public.notify_user(old.event_coordinator_id, 'coordinator_unassigned'", self.notify)
        self.assertIn("'%s %s has been reassigned from you to %s by %s.'", self.notify)


class OrganiserNotifiedOfRequestOutcome(unittest.TestCase):
    """As an Event Organiser, I want to receive notifications about my event request submission and its approval or rejection."""

    notify = function("notify_event_request_submitted", "050_notify_requests_and_staff.sql")

    def test_organiser_is_sent_a_confirmation_on_submission(self):
        self.assertIn("perform public.notify_user(new.event_organiser_id, 'event_request_submitted'", self.notify)
        self.assertIn("'Your event request %s has been submitted and is awaiting review.'", self.notify)

    def test_organiser_is_notified_of_approval_or_rejection(self):
        self.assertIn("new.status in ('planning', 'rejected') and old.status is distinct from new.status", self.notify)
        self.assertIn("'Your event request %s has been approved by %s. It is now in planning.'", self.notify)
        self.assertIn("'Your event request %s has been rejected by %s. Reason: %s'", self.notify)


class StaffNotifiedOfAssignment(unittest.TestCase):
    """As a venue/technical support/safety officer, I want to receive a notification when an event is assigned to me."""

    sql = migration("050_notify_requests_and_staff.sql")
    notify = function("notify_event_staff_assigned", "050_notify_requests_and_staff.sql")

    def test_each_assigned_staff_member_is_notified(self):
        # Staff are assigned before the event is inserted (043), so this sees them.
        self.assertIn("create trigger notify_event_staff_assigned after insert on public.events", self.sql)
        for column, role in (("venue_staff_id", "Venue Staff"), ("technical_support_id", "Technical Support"),
                             ("safety_officer_id", "Safety Officer")):
            self.assertIn(f"(new.{column}, '{role}', '/events/' || new.event_id)", self.notify)
        self.assertIn("perform public.notify_user(staff.user_id, 'event_staff_assigned'", self.notify)
        self.assertIn("or safety_officer_id = (select auth.uid())", self.sql)  # so the Safety Officer can open it

    def test_notification_includes_the_event_name_and_details(self):
        self.assertIn("format('%s by %s (%s – %s SGT)'", self.notify)
        self.assertIn("'Event %s has been assigned to you as %s. Event Coordinator: %s.'", self.notify)

    def test_coordinator_is_told_who_was_assigned(self):
        self.assertIn("perform public.notify_user(new.event_coordinator_id, 'event_staff_assigned', 'Staff assigned to your event',",
                      self.notify)
        self.assertIn("'Staff assigned to %s: %s.'", self.notify)


class CoordinatorNotifiedOfVenueBooking(unittest.TestCase):
    """As an Event Coordinator, I want to receive notifications about my venue booking request and its outcome."""

    notify = function("notify_venue_booking_change", "051_notify_venue_bookings.sql")

    def test_coordinator_is_sent_a_confirmation_on_submission(self):
        self.assertIn("after insert or update of status, hold_expires_at on public.venue_booking_requests",
                      migration("051_notify_venue_bookings.sql"))
        self.assertIn("perform public.notify_user(new.requested_by, 'venue_booking_submitted', 'Venue booking request submitted',",
                      self.notify)

    def test_the_events_venue_staff_is_notified_of_a_new_request(self):
        self.assertIn("perform public.notify_user((select venue_staff_id from public.events where event_id = new.event_id),",
                      self.notify)
        self.assertIn("'/review-venue-bookings/' || new.booking_id", self.notify)

    def test_coordinator_is_notified_of_approval_or_rejection(self):
        self.assertIn("if old.status = 'submitted' and new.status in ('approved', 'rejected') then", self.notify)
        self.assertIn("'Your venue booking request for %s has been %s by %s.%s', booking, new.status,", self.notify)

    def test_notification_includes_the_event_venue_and_status(self):
        self.assertIn("booking text := format('%s for %s (%s – %s SGT)', venue, coalesce(new.event_name", self.notify)
        self.assertIn("Status: pending Venue Staff review.", self.notify)


class CoordinatorNotifiedOfVenueUnavailability(unittest.TestCase):
    """As an Event Coordinator, I want to receive notifications when my booking is affected by a venue becoming unavailable."""

    notify = function("notify_venue_booking_change", "051_notify_venue_bookings.sql")

    def test_coordinator_is_notified_when_a_booked_venue_becomes_unavailable(self):
        self.assertIn("elsif new.status = 'cancelled' and new.cancellation_reason like 'Venue unavailable: %' then", self.notify)
        self.assertIn("perform public.notify_user(new.requested_by, 'venue_unavailable', 'Venue unavailable',", self.notify)
        self.assertIn("when old.status = 'approved' then 'approved booking of'", self.notify)

    def test_notification_identifies_the_venue_event_and_unavailable_period(self):
        self.assertIn("tstzrange(k.starts_at, k.ends_at, '[)') && tstzrange(new.occupied_from, new.occupied_until, '[)')", self.notify)
        self.assertIn("'%s is unavailable from %s to %s SGT (%s), which affects your %s %s. It has been cancelled.', venue,",
                      self.notify)

    def test_coordinator_is_notified_when_a_pending_request_is_affected(self):
        self.assertIn("else 'pending booking request for' end, booking)", self.notify)


class CoordinatorNotifiedOfTentativeHolds(unittest.TestCase):
    """As an Event Coordinator, I want to receive notifications about tentative venue holds and their expiry."""

    notify = function("notify_venue_booking_change", "051_notify_venue_bookings.sql")
    expire = function("expire_venue_holds", "051_notify_venue_bookings.sql")

    def test_coordinator_is_notified_when_a_hold_is_placed(self):
        self.assertIn("elsif old.hold_expires_at is null and new.hold_expires_at is not null and new.status = 'submitted' then",
                      self.notify)
        self.assertIn("perform public.notify_user(new.requested_by, 'venue_hold_placed', 'Tentative hold placed',", self.notify)

    def test_notification_includes_the_venue_event_and_expiry(self):
        self.assertIn("expiry text := to_char(new.hold_expires_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI');", self.notify)
        self.assertIn("'Venue Staff have placed a tentative hold on %s. It expires on %s SGT.', booking, expiry", self.notify)

    def test_coordinator_is_reminded_once_before_the_hold_expires(self):
        self.assertIn("b.hold_expires_at > now() and b.hold_expires_at <= now() + interval '24 hours'", self.expire)
        self.assertIn("n.kind = 'venue_hold_reminder'", self.expire)
        self.assertIn("perform public.notify_user(held.requested_by, 'venue_hold_reminder', 'Tentative hold expiring soon',", self.expire)

    def test_coordinator_is_separately_notified_when_the_hold_expires(self):
        self.assertIn("elsif old.status = 'submitted' and new.status = 'expired' then", self.notify)
        self.assertIn("perform public.notify_user(new.requested_by, 'venue_hold_expired', 'Tentative hold expired',", self.notify)
