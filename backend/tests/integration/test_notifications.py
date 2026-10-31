"""Notification user stories, tested against the real integration-test project.

Run from backend/:  python -m pytest tests/integration/test_notifications.py -v
Needs backend/.env.integration-test (CI writes it from a secret), and migrations
046, 047, 050 and 051 run in the test project.

HOW TO READ THESE TESTS
  * Every action under test goes through the backend API as the role that
    takes it in the app: the Organiser submits, the Lead assigns, the Event
    Coordinator reviews, Venue Staff hold, approve and block.
  * Every notification is read back through GET /api/notifications, signed in
    as its recipient. A pass therefore means the real database trigger ran
    and the right person can see the notification.
  * The secret key is used only to arrange (a test venue, a temporary user,
    moving a hold's expiry as if time had passed) and to clean up. Everything
    a run creates, including its notifications, is removed at the end.
  * A failing assertion message names the notification it looked for. If one
    is missing, the trigger behind it did not run or is missing from the test
    project; if its text differs, the migration's message was changed.

USER STORIES AND ACCEPTANCE CRITERIA (ACs as written in each story)
  S1 As an authenticated user, I want to receive and view in-app notifications
     relevant to me so that I can identify important updates and access the
     affected item.
     AC1 The delivery provides the shared notification infrastructure.
         (Covered by S1 AC2-AC5 together; no test of its own.)
     AC2 The backend can create notifications, store past notifications, and
         deliver them to relevant parties.
     AC3 Shown two ways: a popup of the newest 10, and a full page of the last
         14 days, max 20 per page, highlighting those not yet opened.
     AC4 Users can retrieve and access past notifications received.
     AC5 A notification is marked as read once opened.
  S2 As an Event Coordinator Lead, I want to receive notifications about any
     received event request submission.
     AC1 Sent to the Lead when an event request is successfully submitted.
     AC2 Shows the Event Organiser's name and the event's name.
     AC3 Clicking it navigates to the respective event request.
  S3 As an Event Coordinator, I want to receive a notification when an event is
     assigned or reassigned to me.
     AC1 The Coordinator is notified when an event is assigned or reassigned to them.
     AC2 The notification includes the event name and relevant event information.
     AC3 The previous Coordinator is notified when responsibility is transferred.
  S4 As an Event Organiser, I want to receive notifications about my event
     request submission and its approval or rejection.
     AC1 A confirmation is sent when the request is successfully submitted.
     AC2 The Organiser is notified when the request is approved or rejected.
  S5 As venue/technical support/safety officer staff, I want to receive a
     notification when an event is assigned to me.
     AC1 Each staff member is notified when an event is assigned to them.
     AC2 The notification includes the event name and relevant event information.
     AC3 The Coordinator is informed when staff are assigned to their event.
  S6 As an Event Coordinator, I want to receive notifications about my venue
     booking request and its outcome.
     AC1 The Coordinator is told when a booking request is successfully submitted.
     AC2 The relevant Venue Staff is notified of a new request for an event
         they are assigned to.
     AC3 The Coordinator is notified when the request is approved or rejected.
     AC4 The notification includes the event name, venue and booking status.
  S7 As an Event Coordinator, I want to receive notifications when my booking is
     affected by a venue being declared unavailable.
     AC1 The Coordinator is notified when a venue booked for their event
         becomes unavailable for any affected period.
     AC2 The notification identifies the affected venue and event(s).
     AC3 The Coordinator is notified if the unavailability affects a pending request.
  S8 As an Event Coordinator, I want to receive notifications about tentative
     venue holds and their expiry.
     AC1 The Coordinator is notified when Venue Staff place a hold for their event.
     AC2 The notification includes the venue, event name and hold expiry.
     AC3 A reminder is sent before the hold expires, and a separate
         notification when it has expired.
  S9 As an Event Organiser, I want to receive notifications about event change
     requests and their outcomes.
     AC1 The Organiser is told when a change request is successfully submitted.
     AC2 The assigned Event Coordinator is notified when one is submitted.
     AC3 The notification includes the details of the requested changes.
     AC4 The Organiser is notified when it is approved or rejected.
     AC5 If approved, the relevant users are notified of the approved changes.
  S10 As an Event Coordinator, I want to receive notifications when my equipment
     request is submitted and when its status changes.
     AC1 The Coordinator is told when an equipment request is successfully submitted.
     AC2 The relevant Technical Support Staff is notified of a new request.
     AC3 The notification includes the equipment request's details.
     AC4 The Coordinator is notified when the status changes to Rejected or Accepted.
  S11 As a Safety Officer, I want to receive a notification when an event is
     submitted for safety review.
     AC1 The Safety Officer is notified when an event is submitted for safety review.
     AC2 It shows the event name, the event date and a link to the event.
     AC3 The event's Coordinator is notified once its safety review is approved or
         rejected, or when it sends the event back to Planning.
  S12 As an Attendee, I want to receive notifications about my event registration
     and withdrawal.
     AC1 A confirmation is sent when the Attendee successfully registers.
     AC2 It includes the event name, date, time, and venue when available.
     AC3 If the event is full and has a waiting list, the Attendee is told they
         were added to the waiting list instead of a confirmed registration.
     AC4 A notification is sent if the event is cancelled.
     AC5 A confirmation is sent when the registration is successfully withdrawn.

COVERAGE (every notification function, and every branch in it, is run here)
  app/routes/notifications.py: index popup, page and bad-page branches
      (TC-NTF-002, 003), mark_read success and refusal (005, 006), the
      sign-in error handler (004), and the database-error branch (007).
  notify_user (046) 001; notify_role (046) 008.
  list_my_notifications (046) 001-005; mark_notification_read (046) 005, 006.
  notify_event_request_submitted (050): submitted on insert and on update 008,
      approved 015, rejected 015.
  notify_coordinator_assignment (047): unchanged coordinator 011, request
      assigned and reassigned 011, 012, event reassigned 012, previous coordinator 013.
  notify_event_staff_assigned (050): each staff role 016, a role nobody holds 018.
  authenticated_read_events policy (050): Safety Officer opens the event 016.
  notify_venue_booking_change (051): submitted 019, 020, 022, approved and rejected
      021, cancelled by unavailability (approved 023, pending 025), hold placed
      026, expired 029.
  expire_venue_holds (051): too early, reminder once 028; expiry 029.
  notify_event_change_request (055): submitted pending and applied 030, 031,
      approved and rejected 033, approved changes to staff (reviewed and
      applied) 034. event_change_summary and event_change_value (055): each kind
      of value (text, date, number, yes/no, list, equipment, empty list) 032.
  notify_equipment_request (055): submitted 035-037, accepted and rejected 038.
  submit_event_for_safety_checks (055, from 048): 039, 040.
  notify_safety_decision (055): approved, rejected and changes requested 041.
  notify_event_registration (057): registered 042-044, waiting list 044,
      withdrawn 046. event_registration_details (057) 043-046.
  notify_event_cancelled (057): registered and waitlisted attendees 045.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import quote

import pytest

from tests.integration.supabase_admin import admin_request, delete_as_user, user_id_for

SGT = timezone(timedelta(hours=8))


def sgt(moment):
    """A time as the database writes it in notifications: '05 Jan 2027 10:00'."""
    if isinstance(moment, str):
        moment = datetime.fromisoformat(moment)
    return moment.astimezone(SGT).strftime("%d %b %Y %H:%M")


def name_of(user_id):
    return admin_request(f"/rest/v1/users?select=name&user_id=eq.{user_id}")[0]["name"]


def run_hold_job():
    """Run the every-minute hold job now, as pg_cron does in the real project."""
    admin_request("/rest/v1/rpc/expire_venue_holds", payload={})


class Flow:
    """Takes actions through the API as each role, and removes what it made."""

    def __init__(self, client, sign_in):
        self.client, self.sign_in = client, sign_in
        latest = admin_request("/rest/v1/notifications?select=notification_id&order=notification_id.desc&limit=1")
        self.since = latest[0]["notification_id"] if latest else 0
        self.requests, self.venues, self.users, self.equipment = [], [], [], []
        self.coordinator = user_id_for("Event Coordinator")

    def call(self, who, method, path, body=None, status=200):
        """`who` is a role name, or a temporary user from user()."""
        headers = who["headers"] if isinstance(who, dict) else self.sign_in(who)
        response = getattr(self.client, method)(path, headers=headers, json=body)
        assert response.status_code == status, (method, path, response.get_json())
        return response.get_json()

    def inbox(self, who, link=None):
        """What `who` has received since this run began, through the API, newest first."""
        items = self.call(who, "get", "/api/notifications?limit=50")["items"]
        return [n for n in items if n["notification_id"] > self.since and (link is None or n["link"] == link)]

    def one(self, who, title, link, about=""):
        """The single notification `who` has with this title and link (and text `about`)."""
        found = [n for n in self.inbox(who, link) if n["title"] == title and about in n["body"]]
        assert len(found) == 1, f"expected one {title!r} linking to {link} about {about!r}, got {found}"
        return found[0]

    def user(self, name, role=None):
        """A temporary account, signed in, optionally holding `role`."""
        email, password = f"itest-{uuid.uuid4().hex[:10]}@connectsphere.invalid", uuid.uuid4().hex
        made = admin_request("/auth/v1/admin/users", {"email": email, "password": password,
                                                      "email_confirm": True, "user_metadata": {"name": name}})
        self.users.append(made["id"])
        if role:
            role_id = admin_request(f"/rest/v1/roles?select=role_id&role_name=eq.{quote(role)}")[0]["role_id"]
            admin_request("/rest/v1/user_roles", {"user_id": made["id"], "role_id": role_id})
        token = self.client.post("/api/login", json={"email": email, "password": password}).get_json()["access_token"]
        return {"id": made["id"], "name": name, "headers": {"Authorization": f"Bearer {token}"}}

    def drop_user(self, user):
        admin_request(f"/auth/v1/admin/users/{user['id']}", method="DELETE")
        self.users.remove(user["id"])

    def notify(self, user, title, age=timedelta(0), read=False):
        """Arrange: a notification already in `user`'s inbox, `age` old."""
        created = datetime.now(timezone.utc) - age
        return admin_request("/rest/v1/notifications", {
            "recipient_id": user["id"], "kind": "itest", "title": title, "body": f"{title} body.",
            "link": "/events", "created_at": created.isoformat(),
            "read_at": created.isoformat() if read else None})[0]

    def submit_request(self, draft=False, capacity=40):
        """The Organiser submits a complete request (or saves it as a draft)."""
        starts = (datetime.now(SGT) + timedelta(days=60 + len(self.requests))).replace(
            hour=10, minute=0, second=0, microsecond=0)
        row = self.call("Event Organiser", "post", "/api/event-requests", {
            "event_name": f"ITEST notifications {uuid.uuid4().hex[:8]}", "purpose": "Integration test",
            "description": "Created by test_notifications.py; removed afterwards.",
            "event_organiser_id": user_id_for("Event Organiser"),
            "start_datetime": starts.isoformat(), "end_datetime": (starts + timedelta(hours=3)).isoformat(),
            "capacity_needed": capacity, "room_layout": "theatre", "required_facilities": ["projector"],
            "equipment_requirements": [], "registration_needs": "None", "save_as_draft": draft,
        }, 201)["event_request"]
        self.requests.append(row["event_request_id"])
        return row

    def assign(self, request, coordinator_id=None):
        """The Lead assigns the request to a coordinator (the test Coordinator by default)."""
        self.call("Event Coordinator Lead", "post", f"/api/event-requests/{request['event_request_id']}/assign-coordinator",
                  {"coordinator_id": coordinator_id or self.coordinator})

    def review(self, request, outcome, comments=None):
        """The assigned Coordinator approves or rejects the request."""
        self.call("Event Coordinator", "post", f"/api/event-requests/{request['event_request_id']}/review",
                  {"outcome": outcome, **({"comments": comments} if comments else {})})

    def event(self, capacity=40):
        """A request submitted, assigned and approved: the event approval created."""
        request = self.submit_request(capacity=capacity)
        self.assign(request)
        self.review(request, "approved")
        return admin_request(f"/rest/v1/events?select=*&event_request_id=eq.{request['event_request_id']}")[0]

    def venue(self):
        """Arrange: a venue that meets every test event's requirements."""
        row = admin_request("/rest/v1/venues", {
            "venue_name": f"ITEST Hall {uuid.uuid4().hex[:6]}", "capacity": 100, "postal_code": "123456",
            "block_number": "1", "street_name": "Integration Street", "wheelchair_accessible": False,
            "blind_accessible": False, "facilities": ["projector"], "supported_room_layouts": ["theatre"],
            "operating_hours": {day: {"open": "08:00", "close": "22:00"} for day in (
                "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")},
            "default_setup_minutes": 0, "default_turnaround_minutes": 0})[0]
        self.venues.append(row["venue_id"])
        return row

    def book(self, event, venue):
        """The Coordinator requests `venue` for `event`."""
        return self.call("Event Coordinator", "post", "/api/venue-bookings", {
            "event_id": event["event_id"], "venue_id": venue["venue_id"], "event_name": event["event_name"],
            "attendance": event["capacity_needed"], "venue_requirements": "Integration test",
            "starts_at": event["start_datetime"], "ends_at": event["end_datetime"]}, 201)["booking"]

    def decide(self, booking, outcome, comments=None):
        """Venue Staff approve or reject a booking request."""
        self.call("Venue Staff", "post", f"/api/venue-bookings/{booking['booking_id']}/review",
                  {"outcome": outcome, **({"comments": comments} if comments else {})})

    def hold(self, booking, expires):
        """Venue Staff place a tentative hold until `expires`."""
        self.call("Venue Staff", "post", f"/api/venue-bookings/{booking['booking_id']}/hold",
                  {"expires_at": expires.isoformat()})

    def move_hold_expiry(self, booking, expires):
        """Arrange: the hold's expiry is now `expires`, as if time had passed."""
        admin_request(f"/rest/v1/venue_booking_requests?booking_id=eq.{booking['booking_id']}",
                      {"hold_expires_at": expires.isoformat()}, "PATCH")

    def change(self, event, reason, values):
        """The Organiser asks to change `event`; returns the change request."""
        current = admin_request(f"/rest/v1/events?select=updated_at&event_id=eq.{event['event_id']}")[0]
        return self.call("Event Organiser", "post", f"/api/events/{event['event_id']}/change-requests", {
            "reason": reason, "proposed_values": values,
            "expected_event_updated_at": current["updated_at"]}, 201)["change_request"]

    def decide_change(self, change, decision, reason=None):
        """The assigned Coordinator approves or rejects a change request."""
        self.call("Event Coordinator", "post", f"/api/event-change-requests/{change['event_change_request_id']}/decision",
                  {"decision": decision, **({"reason": reason} if reason else {})})

    def equipment_item(self):
        """Arrange: a catalogue item Technical Support can reserve."""
        row = admin_request("/rest/v1/equipment", {"equipment_type": f"ITEST Mic {uuid.uuid4().hex[:6]}",
                                                   "equipment_model": "Test", "total_quantity": 10})[0]
        self.equipment.append(row["equipment_id"])
        return row

    def request_equipment(self, event, item, quantity, requirements=None):
        """The Coordinator requests `quantity` of `item` for `event`."""
        return self.call("Event Coordinator", "post", f"/api/events/{event['event_id']}/equipment-requests", {
            "equipment_type": item["equipment_type"], "quantity": quantity,
            "technical_requirements": requirements}, 201)["equipment_request"]

    def review_equipment(self, request, outcome, item=None, quantity=None, reason=None):
        """Technical Support reserves the equipment (to accept) and records the decision."""
        path = f"/api/equipment-request-reviews/{request['equipment_request_id']}"
        if outcome != "rejected":
            self.call("Technical Support Staff", "post", f"{path}/reservation",
                      {"equipment_id": item["equipment_id"], "quantity": quantity}, 201)
        self.call("Technical Support Staff", "post", path, {
            "outcome": outcome, "equipment_id": item and item["equipment_id"], "accepted_quantity": quantity,
            "reason": reason or ""})

    def register(self, who, event):
        """`who` (an Attendee) registers for `event`."""
        self.call(who, "post", f"/api/events/{event['event_id']}/registrations", {
            "full_name": "ITEST Attendee", "contact_email": "itest@connectsphere.invalid",
            "contact_phone": "+65 6123 4567"})

    def clean(self):
        for request_id in self.requests:
            for event in admin_request(f"/rest/v1/events?select=event_id&event_request_id=eq.{request_id}"):
                # A reviewed equipment request can only be deleted by its requester once pending again.
                admin_request(f"/rest/v1/equipment_reservations?event_id=eq.{event['event_id']}", method="DELETE")
                admin_request(f"/rest/v1/equipment_request?event_id=eq.{event['event_id']}", {
                    "status": "pending", "accepted_quantity": None, "reviewed_by": None, "reviewed_at": None,
                    "equipment_id": None, "reason_for_rejection": None}, "PATCH")
                delete_as_user(f"/rest/v1/equipment_request?event_id=eq.{event['event_id']}",
                               self.sign_in("Event Coordinator"))
        for equipment_id in self.equipment:
            admin_request(f"/rest/v1/equipment?equipment_id=eq.{equipment_id}", method="DELETE")
        for venue_id in self.venues:
            for table in ("venue_booking_requests", "venue_blocks", "venues"):
                admin_request(f"/rest/v1/{table}?venue_id=eq.{venue_id}", method="DELETE")
        for request_id in self.requests:
            admin_request(f"/rest/v1/events?event_request_id=eq.{request_id}", method="DELETE")
            admin_request(f"/rest/v1/event_request?event_request_id=eq.{request_id}", method="DELETE")
        for user_id in list(self.users):
            admin_request(f"/auth/v1/admin/users/{user_id}", method="DELETE")
        admin_request(f"/rest/v1/notifications?notification_id=gt.{self.since}", method="DELETE")


@pytest.fixture(scope="module")
def flow(client, sign_in):
    actions = Flow(client, sign_in)
    yield actions
    actions.clean()


@pytest.fixture(scope="module")
def submitted(flow):
    """One request submitted by the Organiser, not yet assigned (S2, S4 AC1)."""
    return flow.submit_request()


@pytest.fixture(scope="module")
def approved(flow):
    """One approved request and its event, which approval gave staff (S4 AC2, S5)."""
    return flow.event()


def in_minutes(**delta):
    return (datetime.now(timezone.utc) + timedelta(**delta)).replace(second=0, microsecond=0)


# ---------------------------------------------------------------------------
# S1 Notification system
# ---------------------------------------------------------------------------

def test_ntf_001_backend_creates_stores_and_delivers_to_the_recipient_only(flow):
    """TC-NTF-001 | S1 AC2: create, store and deliver to the relevant party.

    Does: the backend's notify_user() creates a notification for user A, then
    A and another user B each open their notifications through the API.
    Expect: A sees exactly that notification, with its title, text and link;
    B sees nothing. A failure means notifications are not stored, or are
    delivered to the wrong people.
    """
    a, b = flow.user("ITEST Recipient"), flow.user("ITEST Bystander")
    admin_request("/rest/v1/rpc/notify_user", {"p_recipient": a["id"], "p_kind": "itest", "p_title": "ITEST notice",
                                                "p_body": "Stored for one user.", "p_link": "/events"})

    [received] = flow.inbox(a)
    assert (received["title"], received["body"], received["link"]) == ("ITEST notice", "Stored for one user.", "/events")
    assert flow.inbox(b) == []


def test_ntf_002_popup_shows_the_newest_ten_of_any_age(flow):
    """TC-NTF-002 | S1 AC3: the bell popup shows the newest 10 notifications.

    Does: gives a user 12 notifications, 3 days apart (0 to 33 days old), and
    asks for the popup's list (?limit=10), as the bell does.
    Expect: 10 items, newest first (Notice 0 to 9), including ones older than
    14 days: the popup is the newest 10, not the last 14 days. Fewer items or
    another order means the popup shows the wrong notifications.
    """
    user = flow.user("ITEST Popup")
    for i in range(12):
        flow.notify(user, f"Notice {i}", timedelta(days=3 * i))

    items = flow.call(user, "get", "/api/notifications?limit=10")["items"]

    assert [n["title"] for n in items] == [f"Notice {i}" for i in range(10)]


def test_ntf_003_full_page_shows_20_per_page_from_14_days_and_marks_unopened(flow):
    """TC-NTF-003 | S1 AC3: the full page shows 14 days, 20 per page, unopened highlighted.

    Does: gives a user 23 notifications from the last 12 days (Notice 1 already
    opened) and 2 older than 14 days, then reads page 1, page 2 and page 0.
    Expect: page 1 has the newest 20 of the 23, page 2 the other 3, and neither
    the 2 older ones; each item says whether it has been opened (read_at), which
    is what the page highlights by; page 0 is refused. A failure means the page
    shows too much, too little, or cannot tell new from opened.
    """
    user = flow.user("ITEST Full page")
    for i in range(23):
        flow.notify(user, f"Notice {i}", timedelta(hours=12 * i + 1), read=(i == 1))
    for days in (15, 20):
        flow.notify(user, f"Old {days}", timedelta(days=days))

    first = flow.call(user, "get", "/api/notifications?page=1")
    second = flow.call(user, "get", "/api/notifications?page=2")

    assert (first["page_size"], first["total"], first["unread"]) == (20, 23, 24)
    assert [n["title"] for n in first["items"]] == [f"Notice {i}" for i in range(20)]
    assert [n["title"] for n in second["items"]] == ["Notice 20", "Notice 21", "Notice 22"]
    assert [n["read_at"] is not None for n in first["items"][:3]] == [False, True, False]
    assert flow.call(user, "get", "/api/notifications?page=0", status=400)


def test_ntf_004_signed_in_users_retrieve_past_notifications_and_their_links(flow, client):
    """TC-NTF-004 | S1 AC4: users retrieve and access past notifications.

    Does: gives a user a notification from 10 days ago, reads it on the full
    page, then asks for notifications without signing in.
    Expect: the old notification is still there with the link to its item;
    without a sign-in the request is refused with 401. A failure means past
    notifications are lost, cannot lead to their item, or are open to anyone.
    """
    user = flow.user("ITEST History")
    flow.notify(user, "From last week", timedelta(days=10))

    [past] = flow.call(user, "get", "/api/notifications?page=1")["items"]

    assert (past["title"], past["link"]) == ("From last week", "/events")
    assert client.get("/api/notifications?page=1").status_code == 401


def test_ntf_005_opening_a_notification_marks_it_read_once(flow):
    """TC-NTF-005 | S1 AC5: a notification is marked read once opened.

    Does: the recipient opens an unread notification (POST .../read, as the bell
    and full page do), reads the list, then opens it again.
    Expect: it now has a read time and the unread count drops from 1 to 0;
    opening it again keeps the first read time. A failure means the bell's
    count never clears, or "read" moves every time it is opened.
    """
    user = flow.user("ITEST Reader")
    note = flow.notify(user, "Open me")
    assert flow.call(user, "get", "/api/notifications?limit=10")["unread"] == 1

    flow.call(user, "post", f"/api/notifications/{note['notification_id']}/read")
    after = flow.call(user, "get", "/api/notifications?limit=10")
    flow.call(user, "post", f"/api/notifications/{note['notification_id']}/read")

    assert after["unread"] == 0 and after["items"][0]["read_at"]
    assert flow.call(user, "get", "/api/notifications?limit=10")["items"][0]["read_at"] == after["items"][0]["read_at"]


def test_ntf_006_nobody_else_can_mark_a_notification_read(flow):
    """TC-NTF-006 | S1 AC5: only the recipient's opening marks it read.

    Does: another signed-in user tries to mark the recipient's notification read.
    Expect: refused as not found (404, so it does not even reveal the
    notification exists), and it stays unread for the recipient. A failure
    means one user can clear another's notifications.
    """
    owner, other = flow.user("ITEST Owner"), flow.user("ITEST Other")
    note = flow.notify(owner, "Not yours")

    flow.call(other, "post", f"/api/notifications/{note['notification_id']}/read", status=404)

    assert flow.inbox(owner)[0]["read_at"] is None


def test_ntf_007_a_database_refusal_to_list_is_passed_on(client):
    """TC-NTF-007 | S1 AC4: the list is only given to a signed-in user.

    Does: the route is given a valid sign-in, but the database refuses with its
    sign-in error. The database is faked here: once the token is verified the
    real one never refuses, so no live request can reach this branch.
    Expect: the refusal and its 401 are returned, not an empty list. A failure
    means a refused request would look like "no notifications".
    """
    with patch("app.routes.notifications.authenticated_token", return_value="token"), \
         patch("app.routes.notifications.supabase_request",
               return_value={"error": "Please sign in again.", "status": 401}):
        response = client.get("/api/notifications?limit=10")

    assert (response.status_code, response.get_json()) == (401, {"error": "Please sign in again."})


# ---------------------------------------------------------------------------
# S2 Event Coordinator Lead: new event requests
# ---------------------------------------------------------------------------

def test_ntf_008_lead_is_notified_when_a_request_is_submitted(flow, submitted):
    """TC-NTF-008 | S2 AC1: the Lead is notified when a request is successfully submitted.

    Does: the Organiser saves a draft, then submits it; separately, submits a
    request straight away (the fixture). The Lead's notifications are read.
    Expect: nothing for the draft while it is a draft, then exactly one "New
    event request" for each submission, whichever way it was submitted. A
    failure means Leads miss requests, or are told about unfinished drafts.
    """
    draft = flow.submit_request(draft=True)
    draft_link = f"/assign-event-coordinators?request={draft['event_request_id']}"
    assert flow.inbox("Event Coordinator Lead", draft_link) == []

    flow.call("Event Organiser", "post", f"/api/event-requests/{draft['event_request_id']}/submit")

    flow.one("Event Coordinator Lead", "New event request", draft_link)
    flow.one("Event Coordinator Lead", "New event request",
             f"/assign-event-coordinators?request={submitted['event_request_id']}")


def test_ntf_009_lead_sees_the_organiser_and_event_name(flow, submitted):
    """TC-NTF-009 | S2 AC2: the notification shows the Organiser's and the event's name.

    Does: reads the Lead's notification for the submitted request.
    Expect: "Event request for <event> by <Organiser's name> received and
    pending coordinator assignment." A failure means a name is missing or wrong.
    """
    note = flow.one("Event Coordinator Lead", "New event request",
                    f"/assign-event-coordinators?request={submitted['event_request_id']}")

    assert note["body"] == (f"Event request for {submitted['event_name']} by "
                            f"{name_of(user_id_for('Event Organiser'))} received and pending coordinator assignment.")


def test_ntf_010_lead_notification_opens_the_request(flow, submitted):
    """TC-NTF-010 | S2 AC3: clicking it navigates to the event request.

    Does: checks the notification's link, and that the request it names is in
    the list that page (Assign Event Coordinators) shows the Lead.
    Expect: the link is /assign-event-coordinators?request=<id>, which the page
    highlights, and the request is in the Lead's list. A failure means the
    click leads nowhere useful.
    """
    link = f"/assign-event-coordinators?request={submitted['event_request_id']}"
    flow.one("Event Coordinator Lead", "New event request", link)

    queue = flow.call("Event Coordinator Lead", "get", "/api/event-requests/unassigned")

    assert submitted["event_request_id"] in {r["event_request_id"] for r in queue["event_requests"]}


# ---------------------------------------------------------------------------
# S3 Event Coordinator: assigned or reassigned
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def handover(flow):
    """A request assigned to the test Coordinator, then reassigned to a second one."""
    second = flow.user("ITEST Second Coordinator", "Event Coordinator")
    request = flow.submit_request()
    flow.assign(request)
    # Saving the same coordinator again is not an assignment.
    admin_request(f"/rest/v1/event_request?event_request_id=eq.{request['event_request_id']}",
                  {"event_coordinator_id": flow.coordinator}, "PATCH")
    flow.call("Event Coordinator Lead", "patch",
              f"/api/coordinator-lead/event-requests/{request['event_request_id']}/coordinator",
              {"coordinator_id": second["id"]})
    return request, second


def test_ntf_011_coordinator_is_notified_when_assigned_or_reassigned(flow, handover):
    """TC-NTF-011 | S3 AC1: notified when an event is assigned or reassigned to them.

    Does: the Lead assigns a request to the test Coordinator, the same
    coordinator is saved again, then the Lead reassigns it to a second coordinator.
    Expect: the first coordinator has exactly one "Event assigned to you" (none
    for saving the same coordinator again), and the second coordinator has one
    too. A failure means a coordinator is not told, or is told twice.
    """
    request, second = handover
    link = f"/review-event-requests/{request['event_request_id']}"

    flow.one("Event Coordinator", "Event assigned to you", link)
    flow.one(second, "Event assigned to you", link)


def test_ntf_012_assignment_names_the_event_and_its_details(flow, handover):
    """TC-NTF-012 | S3 AC2: includes the event name and relevant event information.

    Does: reads both coordinators' notifications from the handover, then the
    Lead reassigns an approved event, and the new coordinator's is read.
    Expect, for a request: "Event request <event> by <Organiser> has been
    assigned / reassigned to you by <Lead>, pending review.", opening the review
    page. For an event: "Event <event> by <Organiser> has been reassigned to you
    by <Lead>. It is currently in planning.", opening the event. A failure means
    the coordinator cannot tell what they now manage or who gave it to them.
    """
    request, second = handover
    organiser, lead = name_of(user_id_for("Event Organiser")), name_of(user_id_for("Event Coordinator Lead"))
    link = f"/review-event-requests/{request['event_request_id']}"
    item = f"{request['event_name']} by {organiser}"

    assert flow.one("Event Coordinator", "Event assigned to you", link)["body"] == \
        f"Event request {item} has been assigned to you by {lead}, pending review."
    assert flow.one(second, "Event assigned to you", link)["body"] == \
        f"Event request {item} has been reassigned to you by {lead}, pending review."

    event = flow.event()
    flow.call("Event Coordinator Lead", "patch", f"/api/coordinator-lead/events/{event['event_id']}/coordinator",
              {"coordinator_id": second["id"]})

    assert flow.one(second, "Event assigned to you", f"/events/{event['event_id']}")["body"] == \
        f"Event {event['event_name']} by {organiser} has been reassigned to you by {lead}. It is currently in planning."


def test_ntf_013_previous_coordinator_is_told_of_the_transfer(flow, handover):
    """TC-NTF-013 | S3 AC3: the previous Coordinator is notified of the transfer.

    Does: reads the first coordinator's notifications after the reassignment.
    Expect: "Event request <event> by <Organiser> has been reassigned from you to
    <second coordinator> by <Lead>.", linking to their list, since they can no
    longer open the request. A failure means they are not told it moved.
    """
    request, second = handover
    found = [n for n in flow.inbox("Event Coordinator", "/review-event-requests") if request["event_name"] in n["body"]]

    assert [(n["title"], n["body"]) for n in found] == [(
        "Event reassigned",
        f"Event request {request['event_name']} by {name_of(user_id_for('Event Organiser'))} has been reassigned "
        f"from you to {second['name']} by {name_of(user_id_for('Event Coordinator Lead'))}.")]


# ---------------------------------------------------------------------------
# S4 Event Organiser: submitted, approved or rejected
# ---------------------------------------------------------------------------

def test_ntf_014_organiser_is_sent_a_confirmation_on_submission(flow, submitted):
    """TC-NTF-014 | S4 AC1: a confirmation when the request is successfully submitted.

    Does: reads the Organiser's notifications after they submitted a request.
    Expect: one "Event request submitted": "Your event request <event> has been
    submitted and is awaiting review.", opening the request. A failure means the
    Organiser gets no confirmation.
    """
    note = flow.one("Event Organiser", "Event request submitted", f"/event-requests/{submitted['event_request_id']}")

    assert note["body"] == f"Your event request {submitted['event_name']} has been submitted and is awaiting review."


def test_ntf_015_organiser_is_notified_of_approval_or_rejection(flow, approved):
    """TC-NTF-015 | S4 AC2: notified when the request is approved or rejected.

    Does: the Coordinator approved one request (the fixture) and now rejects
    another with a reason; the Organiser's notifications are read.
    Expect: "Event request approved": "... has been approved by <Coordinator>.
    It is now in planning.", opening the new event; and "Event request
    rejected": "... has been rejected by <Coordinator>. Reason: <reason>",
    opening the request. A failure means the Organiser misses the outcome or
    the reason.
    """
    coordinator = name_of(flow.coordinator)
    request = flow.submit_request()
    flow.assign(request)
    flow.review(request, "rejected", "The hall is closed for repairs.")

    approval = flow.one("Event Organiser", "Event request approved", f"/events/{approved['event_id']}")
    rejection = flow.one("Event Organiser", "Event request rejected", f"/event-requests/{request['event_request_id']}")

    assert approval["body"] == (f"Your event request {approved['event_name']} has been approved by {coordinator}. "
                                "It is now in planning.")
    assert rejection["body"] == (f"Your event request {request['event_name']} has been rejected by {coordinator}. "
                                 "Reason: The hall is closed for repairs.")


# ---------------------------------------------------------------------------
# S5 Venue Staff, Technical Support and Safety Officer: assigned to an event
# ---------------------------------------------------------------------------

STAFF = {"Venue Staff": "venue_staff_id", "Technical Support Staff": "technical_support_id",
         "Safety Officer": "safety_officer_id"}


def test_ntf_016_each_assigned_staff_member_is_notified(flow, approved):
    """TC-NTF-016 | S5 AC1: each staff member is notified when an event is assigned to them.

    Does: approval assigned a Venue Staff, a Technical Support and a Safety
    Officer to the event; each reads their notifications and opens the link.
    Expect: each has exactly one "Event assigned to you" opening the event, and
    the event then loads for each of them (including the Safety Officer, whom
    050 allowed to read it). A failure means staff are not told, or the link
    does not open for them.
    """
    link = f"/events/{approved['event_id']}"
    for role, column in STAFF.items():
        assert approved[column] == user_id_for(role), f"{role} was not the one assigned"
        flow.one(role, "Event assigned to you", link)
        assert flow.call(role, "get", f"/api/events/{approved['event_id']}")["event"]["event_id"] == approved["event_id"]


def test_ntf_017_staff_notification_includes_the_event_details(flow, approved):
    """TC-NTF-017 | S5 AC2: includes the event name and relevant event information.

    Does: reads each staff member's notification.
    Expect: "Event <event> by <Organiser> (<start> – <end> SGT) has been assigned
    to you as <role>. Event Coordinator: <name>." A failure means staff cannot
    tell which event, when, or in what role.
    """
    details = (f"{approved['event_name']} by {name_of(user_id_for('Event Organiser'))} "
               f"({sgt(approved['start_datetime'])} – {sgt(approved['end_datetime'])} SGT)")
    for role, label in (("Venue Staff", "Venue Staff"), ("Technical Support Staff", "Technical Support"),
                        ("Safety Officer", "Safety Officer")):
        note = flow.one(role, "Event assigned to you", f"/events/{approved['event_id']}")
        assert note["body"] == (f"Event {details} has been assigned to you as {label}. "
                                f"Event Coordinator: {name_of(flow.coordinator)}.")


def test_ntf_018_coordinator_is_told_who_was_assigned(flow, approved):
    """TC-NTF-018 | S5 AC3: the Coordinator is informed when staff are assigned.

    Does: reads the Coordinator's notification for the fixture's event. Then,
    with nobody holding the Safety Officer role for a moment, approves another
    request, and reads that one.
    Expect: "Staff assigned to <event>: Venue Staff <name>, Technical Support
    <name>, Safety Officer <name>."; for the second, "Safety Officer not
    assigned". A failure means the Coordinator does not know who is on the event.
    """
    names = {role: name_of(user_id_for(role)) for role in STAFF}
    staffed = ("Venue Staff {Venue Staff}, Technical Support {Technical Support Staff}, "
               "Safety Officer {Safety Officer}.")
    note = flow.one("Event Coordinator", "Staff assigned to your event", f"/events/{approved['event_id']}")
    assert note["body"] == f"Staff assigned to {approved['event_name']}: " + staffed.format(**names)

    officer = user_id_for("Safety Officer")
    held = admin_request(f"/rest/v1/user_roles?user_id=eq.{officer}&select=role_id,roles!inner(role_name)"
                         "&roles.role_name=eq.Safety%20Officer")
    admin_request(f"/rest/v1/user_roles?user_id=eq.{officer}&role_id=eq.{held[0]['role_id']}", method="DELETE")
    try:
        event = flow.event()
    finally:
        admin_request("/rest/v1/user_roles", {"user_id": officer, "role_id": held[0]["role_id"]})

    note = flow.one("Event Coordinator", "Staff assigned to your event", f"/events/{event['event_id']}")
    assert note["body"] == f"Staff assigned to {event['event_name']}: " + staffed.format(
        **{**names, "Safety Officer": "not assigned"})


# ---------------------------------------------------------------------------
# S6 Venue booking request and its outcome
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def booking(flow):
    """The Coordinator's venue booking request for an approved event."""
    event, venue = flow.event(), flow.venue()
    return event, venue, flow.book(event, venue)


def test_ntf_019_coordinator_is_told_the_request_was_submitted(flow, booking):
    """TC-NTF-019 | S6 AC1: the Coordinator is told the booking request was submitted.

    Does: reads the Coordinator's notifications after their request.
    Expect: one "Venue booking request submitted", opening the booking. A
    failure means the Coordinator has no confirmation.
    """
    _, _, request = booking

    flow.one("Event Coordinator", "Venue booking request submitted", f"/venue-bookings/{request['booking_id']}")


def test_ntf_020_the_events_venue_staff_is_notified_of_the_request(flow, booking):
    """TC-NTF-020 | S6 AC2: the Venue Staff assigned to the event is notified.

    Does: reads the event's Venue Staff's notifications; then, with a second
    Venue Staff account that is not assigned to the event, the Coordinator
    requests another venue for it.
    Expect: the assigned Venue Staff has "New venue booking request", opening its
    review page; the unassigned one receives nothing. A failure means the wrong
    staff, or nobody, is told.
    """
    event, _, request = booking
    assert event["venue_staff_id"] == user_id_for("Venue Staff")
    flow.one("Venue Staff", "New venue booking request", f"/review-venue-bookings/{request['booking_id']}")

    unassigned = flow.user("ITEST Unassigned Venue Staff", "Venue Staff")
    try:
        flow.book(event, flow.venue())
        assert flow.inbox(unassigned) == []
    finally:
        flow.drop_user(unassigned)


def test_ntf_021_coordinator_is_notified_of_approval_or_rejection(flow, booking):
    """TC-NTF-021 | S6 AC3: notified when the booking request is approved or rejected.

    Does: Venue Staff approve the request, then the Coordinator requests a
    second venue for the same event and Venue Staff reject it with a reason.
    Expect: "Venue booking approved": "... has been approved by <Venue Staff>.",
    and "Venue booking rejected": "... has been rejected by <Venue Staff>.
    Reason: <reason>". A failure means the Coordinator misses the outcome.
    """
    event, venue, request = booking
    staff = name_of(user_id_for("Venue Staff"))
    other = flow.venue()
    refused = flow.book(event, other)
    flow.decide(request, "approved")
    flow.decide(refused, "rejected", "Stage is being rebuilt.")
    period = f"({sgt(event['start_datetime'])} – {sgt(event['end_datetime'])} SGT)"

    approval = flow.one("Event Coordinator", "Venue booking approved", f"/venue-bookings/{request['booking_id']}")
    rejection = flow.one("Event Coordinator", "Venue booking rejected", f"/venue-bookings/{refused['booking_id']}")

    assert approval["body"] == (f"Your venue booking request for {venue['venue_name']} for {event['event_name']} "
                                f"{period} has been approved by {staff}.")
    assert rejection["body"] == (f"Your venue booking request for {other['venue_name']} for {event['event_name']} "
                                 f"{period} has been rejected by {staff}. Reason: Stage is being rebuilt.")


def test_ntf_022_booking_notification_includes_event_venue_and_status(flow, booking):
    """TC-NTF-022 | S6 AC4: includes the event name, venue and booking status.

    Does: reads the Coordinator's submission confirmation.
    Expect: "Your venue booking request for <venue> for <event> (<start> – <end>
    SGT) has been submitted. Status: pending Venue Staff review." (The outcome
    messages in TC-NTF-021 carry the new status the same way.) A failure means
    the Coordinator cannot tell which booking it is or where it stands.
    """
    event, venue, request = booking
    note = flow.one("Event Coordinator", "Venue booking request submitted", f"/venue-bookings/{request['booking_id']}")

    assert note["body"] == (f"Your venue booking request for {venue['venue_name']} for {event['event_name']} "
                            f"({sgt(event['start_datetime'])} – {sgt(event['end_datetime'])} SGT) has been "
                            "submitted. Status: pending Venue Staff review.")


# ---------------------------------------------------------------------------
# S7 Venue becomes unavailable
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def blocked(flow):
    """Two events booked at one venue, one approved and one pending, then Venue
    Staff mark the venue unavailable over both."""
    venue, first, second = flow.venue(), flow.event(), flow.event()
    approved_booking, pending_booking = flow.book(first, venue), flow.book(second, venue)
    flow.decide(approved_booking, "approved")
    starts = datetime.fromisoformat(first["start_datetime"]) - timedelta(days=1)
    ends = datetime.fromisoformat(second["end_datetime"]) + timedelta(days=1)
    flow.call("Venue Staff", "post", f"/api/venues/{venue['venue_id']}/unavailability",
              {"starts_at": starts.isoformat(), "ends_at": ends.isoformat(), "reason": "Flooding"}, 201)
    return venue, (starts, ends), (first, approved_booking), (second, pending_booking)


def unavailable_text(venue, period, affected, event):
    return (f"{venue['venue_name']} is unavailable from {sgt(period[0])} to {sgt(period[1])} SGT (Flooding), "
            f"which affects your {affected} {venue['venue_name']} for {event['event_name']} "
            f"({sgt(event['start_datetime'])} – {sgt(event['end_datetime'])} SGT). It has been cancelled.")


def test_ntf_023_coordinator_is_notified_when_a_booked_venue_becomes_unavailable(flow, blocked):
    """TC-NTF-023 | S7 AC1: notified when a venue booked for their event becomes unavailable.

    Does: reads the Coordinator's notification for the approved booking.
    Expect: one "Venue unavailable" saying it "affects your approved booking of
    <venue> for <event> ... It has been cancelled.", opening the booking. A
    failure means a confirmed booking is lost without the Coordinator knowing.
    """
    venue, period, (event, request), _ = blocked
    note = flow.one("Event Coordinator", "Venue unavailable", f"/venue-bookings/{request['booking_id']}")

    assert note["body"] == unavailable_text(venue, period, "approved booking of", event)


def test_ntf_024_unavailability_identifies_the_venue_and_each_event(flow, blocked):
    """TC-NTF-024 | S7 AC2: identifies the affected venue and event(s).

    Does: reads every "Venue unavailable" notification this one block caused.
    Expect: exactly one per affected booking (two), each naming the venue, its
    own event, the unavailable period in SGT and the reason. A failure means an
    affected event goes unmentioned, or is mentioned twice.
    """
    venue, (starts, ends), (first, _), (second, _) = blocked
    found = [n["body"] for n in flow.inbox("Event Coordinator") if n["title"] == "Venue unavailable"
             and venue["venue_name"] in n["body"]]
    named = sorted([e["event_name"] for e in (first, second) if e["event_name"] in body] for body in found)

    assert named == sorted([[first["event_name"]], [second["event_name"]]])
    assert all(f"from {sgt(starts)} to {sgt(ends)} SGT (Flooding)" in body for body in found)


def test_ntf_025_coordinator_is_notified_when_a_pending_request_is_affected(flow, blocked):
    """TC-NTF-025 | S7 AC3: notified when the unavailability affects a pending request.

    Does: reads the Coordinator's notification for the pending booking.
    Expect: "... affects your pending booking request for <venue> for <event>
    ... It has been cancelled." A failure means the Coordinator keeps waiting on
    a request that can no longer be approved.
    """
    venue, period, _, (event, request) = blocked
    note = flow.one("Event Coordinator", "Venue unavailable", f"/venue-bookings/{request['booking_id']}")

    assert note["body"] == unavailable_text(venue, period, "pending booking request for", event)


# ---------------------------------------------------------------------------
# S8 Tentative holds and their expiry
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def held(flow):
    """A booking request Venue Staff hold for 30 hours."""
    event, venue = flow.event(), flow.venue()
    request, expires = flow.book(event, venue), in_minutes(hours=30)
    flow.hold(request, expires)
    return event, venue, request, expires


def test_ntf_026_coordinator_is_notified_when_a_hold_is_placed(flow, held):
    """TC-NTF-026 | S8 AC1: notified when Venue Staff place a hold for their event.

    Does: reads the Coordinator's notifications after Venue Staff held the request.
    Expect: one "Tentative hold placed", opening the booking. A failure means the
    Coordinator does not know a deadline has started.
    """
    _, _, request, _ = held

    flow.one("Event Coordinator", "Tentative hold placed", f"/venue-bookings/{request['booking_id']}")


def test_ntf_027_hold_notification_includes_venue_event_and_expiry(flow, held):
    """TC-NTF-027 | S8 AC2: includes the venue, event name and hold expiry.

    Does: reads the hold notification's text.
    Expect: "Venue Staff have placed a tentative hold on <venue> for <event>
    (<start> – <end> SGT). It expires on <expiry> SGT." A failure means the
    Coordinator cannot tell what is held or until when.
    """
    event, venue, request, expires = held
    note = flow.one("Event Coordinator", "Tentative hold placed", f"/venue-bookings/{request['booking_id']}")

    assert note["body"] == (f"Venue Staff have placed a tentative hold on {venue['venue_name']} for "
                            f"{event['event_name']} ({sgt(event['start_datetime'])} – {sgt(event['end_datetime'])} "
                            f"SGT). It expires on {sgt(expires)} SGT.")


def test_ntf_028_coordinator_is_reminded_once_before_the_hold_expires(flow, held):
    """TC-NTF-028 | S8 AC3 (reminder): a reminder before the hold expires.

    Does: runs the every-minute hold job while the hold is 30 hours from expiry;
    then, as if time had passed, makes it 2 hours from expiry and runs the job twice.
    Expect: no reminder at 30 hours (reminders come in the last 24); then exactly
    one "Tentative hold expiring soon" naming the venue, event and expiry,
    however often the job runs. A failure means no reminder, an early one, or
    one every minute.
    """
    event, venue, request, _ = held
    link = f"/venue-bookings/{request['booking_id']}"
    run_hold_job()
    assert [n for n in flow.inbox("Event Coordinator", link) if n["title"] == "Tentative hold expiring soon"] == []

    expires = in_minutes(hours=2)
    flow.move_hold_expiry(request, expires)
    run_hold_job()
    run_hold_job()

    assert flow.one("Event Coordinator", "Tentative hold expiring soon", link)["body"] == (
        f"Reminder: the tentative hold on {venue['venue_name']} for {event['event_name']} expires on "
        f"{sgt(expires)} SGT. Unless Venue Staff confirm the booking by then, the venue becomes available to other requests.")


def test_ntf_029_a_separate_notification_is_sent_when_the_hold_expires(flow, held):
    """TC-NTF-029 | S8 AC3 (expiry): a separate notification when the hold has expired.

    Does: as if time had passed, makes the hold's expiry a minute ago and runs
    the hold job.
    Expect: the booking is now expired, and the Coordinator has one "Tentative
    hold expired" saying when it expired and that the venue is available to
    others, as well as (not instead of) the reminder. A failure means the
    Coordinator is not told the venue has gone.
    """
    event, venue, request, _ = held
    link = f"/venue-bookings/{request['booking_id']}"
    expired = in_minutes(minutes=-1)
    flow.move_hold_expiry(request, expired)
    run_hold_job()

    status = admin_request(f"/rest/v1/venue_booking_requests?select=status&booking_id=eq.{request['booking_id']}")
    assert status == [{"status": "expired"}]
    assert flow.one("Event Coordinator", "Tentative hold expired", link)["body"] == (
        f"The tentative hold on {venue['venue_name']} for {event['event_name']} ({sgt(event['start_datetime'])} – "
        f"{sgt(event['end_datetime'])} SGT) expired on {sgt(expired)} SGT. The venue is now available to other requests.")


# ---------------------------------------------------------------------------
# S9 Event change requests and their outcomes
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def changes(flow):
    """Three change requests for one event: a minor one applied straight away,
    one approved after review, and one with every kind of value, rejected."""
    event = flow.event()
    original, renamed = event["event_name"], event["event_name"] + " (renamed)"
    applied = flow.change(event, "Clearer title", {"event_name": renamed, "description": "Updated description."})
    approved = flow.change(event, "More guests expected", {"capacity_needed": 60})
    flow.decide_change(approved, "approve")
    starts = datetime.fromisoformat(event["start_datetime"]) + timedelta(hours=1)
    ends = datetime.fromisoformat(event["end_datetime"]) + timedelta(hours=1)
    rejected = flow.change(event, "Different set-up", {
        "start_datetime": starts.isoformat(), "end_datetime": ends.isoformat(), "room_layout": "u_shape",
        "need_wheelchair_accessibility": True, "required_facilities": ["projector", "wifi"],
        "equipment_requirements": [{"equipment_type": "Microphone", "quantity": 2}]})
    flow.decide_change(rejected, "reject", "Too late to change the set-up.")
    summaries = {
        "applied": f"Description: Created by test_notifications.py; removed afterwards. → Updated description.; "
                   f"Event name: {original} → {renamed}",
        "approved": "Expected attendance: 40 → 60",
        "rejected": (f"End: {sgt(event['end_datetime'])} → {sgt(ends)}; Equipment requirements: none → Microphone ×2; "
                     f"Wheelchair accessibility: No → Yes; Venue requirements: projector → projector, wifi; "
                     f"Room layout: theatre → u shape; Start: {sgt(event['start_datetime'])} → {sgt(starts)}")}
    return dict(event=event, original=original, renamed=renamed, applied=applied, approved=approved,
                rejected=rejected, summaries=summaries)


def test_ntf_030_organiser_is_told_the_change_request_was_submitted(flow, changes):
    """TC-NTF-030 | S9 AC1: the Organiser is told a change request was successfully submitted.

    Does: the Organiser submitted a minor change (applied straight away) and a
    change that needs review; their notifications are read.
    Expect: one "Event change request submitted" for each: "Your change request
    for <event> has been submitted and applied. Changes: ..." and "... has been
    submitted and is awaiting review. Changes: ...", opening their change
    requests. A failure means the Organiser has no confirmation.
    """
    link = "/event-change-requests/new"
    applied = flow.one("Event Organiser", "Event change request submitted", link, "and applied")
    pending = flow.one("Event Organiser", "Event change request submitted", link, changes["summaries"]["approved"])

    assert applied["body"] == (f"Your change request for {changes['original']} has been submitted and applied. "
                               f"Changes: {changes['summaries']['applied']}")
    assert pending["body"] == (f"Your change request for {changes['renamed']} has been submitted and is awaiting "
                               f"review. Changes: {changes['summaries']['approved']}")


def test_ntf_031_assigned_coordinator_is_notified_of_a_change_request(flow, changes):
    """TC-NTF-031 | S9 AC2: the assigned Event Coordinator is notified when one is submitted.

    Does: reads the event's Coordinator's notifications for the two submissions.
    Expect: one "New event change request" each: the one needing review opens
    its review page; the one already applied says so and opens the event. A
    failure means the Coordinator does not know a change was asked for.
    """
    event = changes["event"]
    flow.one("Event Coordinator", "New event change request",
             f"/review-event-change-requests/{changes['approved']['event_change_request_id']}")
    applied = flow.one("Event Coordinator", "New event change request", f"/events/{event['event_id']}")

    assert "(applied, no review needed)" in applied["body"]


def test_ntf_032_change_request_notification_details_the_changes(flow, changes):
    """TC-NTF-032 | S9 AC3: the notification includes the details of the requested changes.

    Does: reads the Coordinator's notification for the request that changes the
    times, layout, accessibility, facilities and equipment.
    Expect: "<Organiser> requested changes to <event>. Changes: <field>: <from>
    → <to>; ... Reason: <reason>", each value readable: times in SGT, Yes/No,
    lists joined, equipment as "Microphone ×2", an empty list as "none". A
    failure means the Coordinator cannot see what is being asked.
    """
    link = f"/review-event-change-requests/{changes['rejected']['event_change_request_id']}"
    note = flow.one("Event Coordinator", "New event change request", link)

    assert note["body"] == (f"{name_of(user_id_for('Event Organiser'))} requested changes to {changes['renamed']}. "
                            f"Changes: {changes['summaries']['rejected']}. Reason: Different set-up")


def test_ntf_033_organiser_is_notified_of_approval_or_rejection(flow, changes):
    """TC-NTF-033 | S9 AC4: the Organiser is notified when it is approved or rejected.

    Does: the Coordinator approved one reviewed request and rejected another
    with a reason; the Organiser's notifications are read.
    Expect: "Event change request approved": "... has been approved by
    <Coordinator>. The event has been updated." and "Event change request
    rejected": "... has been rejected by <Coordinator>. Reason: <reason>". A
    failure means the Organiser does not learn the outcome.
    """
    coordinator, link = name_of(flow.coordinator), "/event-change-requests/new"

    assert flow.one("Event Organiser", "Event change request approved", link, changes["renamed"])["body"] == \
        f"Your change request for {changes['renamed']} has been approved by {coordinator}. The event has been updated."
    assert flow.one("Event Organiser", "Event change request rejected", link, changes["renamed"])["body"] == \
        f"Your change request for {changes['renamed']} has been rejected by {coordinator}. Reason: Too late to change the set-up."


def test_ntf_034_staff_are_told_of_approved_changes(flow, changes):
    """TC-NTF-034 | S9 AC5: if approved, the relevant users are notified of the changes.

    Does: reads the notifications of the event's Venue Staff, Technical Support
    and Safety Officer.
    Expect: each has one "Event changes approved" per approved request (the one
    applied straight away and the one approved after review), listing the
    changes and opening the event; none for the rejected request. A failure
    means staff keep working from outdated event details.
    """
    link = f"/events/{changes['event']['event_id']}"
    for role in STAFF:
        received = sorted(n["body"] for n in flow.inbox(role, link) if n["title"] == "Event changes approved")
        assert received == sorted([
            f"Changes to {changes['original']} have been approved. Changes: {changes['summaries']['applied']}",
            f"Changes to {changes['renamed']} have been approved. Changes: {changes['summaries']['approved']}"]), role


# ---------------------------------------------------------------------------
# S10 Equipment requests and their status
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def equipment(flow):
    """Two equipment requests for one event: one accepted, one rejected."""
    event, item = flow.event(), flow.equipment_item()
    accepted = flow.request_equipment(event, item, 2, "Wireless, with spare batteries")
    refused = flow.request_equipment(event, item, 1)
    flow.review_equipment(accepted, "accepted", item, 2)
    flow.review_equipment(refused, "rejected", reason="Not available that week.")
    return event, item


def equipment_text(item, quantity):
    return f"{quantity} × {item['equipment_type']}"


def test_ntf_035_coordinator_is_told_the_equipment_request_was_submitted(flow, equipment):
    """TC-NTF-035 | S10 AC1: the Coordinator is told the request was successfully submitted.

    Does: reads the Coordinator's notifications after their two requests.
    Expect: one "Equipment request submitted" for each, opening their equipment
    requests. A failure means the Coordinator has no confirmation.
    """
    _, item = equipment
    for quantity in (2, 1):
        flow.one("Event Coordinator", "Equipment request submitted", "/equipment-requests", equipment_text(item, quantity))


def test_ntf_036_the_events_technical_support_is_notified(flow, equipment):
    """TC-NTF-036 | S10 AC2: the relevant Technical Support Staff is notified.

    Does: reads the notifications of the Technical Support Staff assigned to the
    event (approval assigned them).
    Expect: one "New equipment request" per request, opening the equipment
    review page. A failure means nobody is told there is equipment to arrange.
    """
    event, item = equipment
    assert event["technical_support_id"] == user_id_for("Technical Support Staff")
    for quantity in (2, 1):
        flow.one("Technical Support Staff", "New equipment request", "/equipment", equipment_text(item, quantity))


def test_ntf_037_equipment_notification_includes_the_request_details(flow, equipment):
    """TC-NTF-037 | S10 AC3: the notification includes the equipment request's details.

    Does: reads both notifications for the request with technical requirements.
    Expect, to Technical Support: "<Coordinator> requested 2 × <equipment> for
    <event> (<start> – <end> SGT). Technical requirements: <text>. Status:
    pending review."; to the Coordinator: "Your equipment request for 2 ×
    <equipment> for <event> has been submitted. Status: pending Technical Support
    review." A failure means staff cannot tell what is needed, when, or for what.
    """
    event, item = equipment
    asked = equipment_text(item, 2)

    assert flow.one("Technical Support Staff", "New equipment request", "/equipment", asked)["body"] == (
        f"{name_of(flow.coordinator)} requested {asked} for {event['event_name']} ({sgt(event['start_datetime'])} – "
        f"{sgt(event['end_datetime'])} SGT). Technical requirements: Wireless, with spare batteries. Status: pending review.")
    assert flow.one("Event Coordinator", "Equipment request submitted", "/equipment-requests", asked)["body"] == (
        f"Your equipment request for {asked} for {event['event_name']} has been submitted. "
        "Status: pending Technical Support review.")


def test_ntf_038_coordinator_is_notified_when_the_request_is_accepted_or_rejected(flow, equipment):
    """TC-NTF-038 | S10 AC4: notified when the status changes to Rejected or Accepted.

    Does: Technical Support reserved and accepted one request, and rejected
    another with a reason; the Coordinator's notifications are read.
    Expect: "Equipment request accepted" and "Equipment request rejected" (with
    the reason), each naming the equipment, event and reviewer. A failure means
    the Coordinator does not know whether the equipment is arranged.
    """
    event, item = equipment
    staff, name = name_of(user_id_for("Technical Support Staff")), event["event_name"]
    expected = {
        ("Equipment request accepted", 2): "has been accepted by {staff}.",
        ("Equipment request rejected", 1): "has been rejected by {staff}. Reason: Not available that week.",
    }
    for (title, quantity), outcome in expected.items():
        asked = equipment_text(item, quantity)
        assert flow.one("Event Coordinator", title, "/equipment-requests", asked)["body"] == \
            f"Your equipment request for {asked} for {name} " + outcome.format(staff=staff)


# ---------------------------------------------------------------------------
# S11 Safety Officer: event submitted for safety review
# ---------------------------------------------------------------------------

def submit_for_safety(flow, capacity=40):
    """An event with its venue approved, submitted for safety checks by its Coordinator."""
    event, venue = flow.event(capacity), flow.venue()
    flow.decide(flow.book(event, venue), "approved")
    flow.call("Event Coordinator", "post", f"/api/events/{event['event_id']}/safety-checks")
    return {**event, "venue_name": venue["venue_name"]}


@pytest.fixture(scope="module")
def safety_review(flow):
    return submit_for_safety(flow)


def test_ntf_039_safety_officer_is_notified_of_a_safety_review(flow, safety_review):
    """TC-NTF-039 | S11 AC1: the Safety Officer is notified when an event is submitted for safety review.

    Does: reads the notifications of the Safety Officer assigned to the event.
    Expect: exactly one "Event awaiting safety check" for it. A failure means
    the event waits in the queue without the officer knowing.
    """
    assert safety_review["safety_officer_id"] == user_id_for("Safety Officer")

    flow.one("Safety Officer", "Event awaiting safety check", f"/operational-safety-reviews/{safety_review['event_id']}")


def test_ntf_040_safety_notification_shows_the_event_its_date_and_link(flow, safety_review):
    """TC-NTF-040 | S11 AC2: shows the event name, the event date and a link to it.

    Does: reads the notification's text and opens its link's review as the officer.
    Expect: "<event> (<start> – <end> SGT) has been submitted for safety checks
    by <Coordinator>.", and the safety review it links to opens for the officer.
    A failure means a missing name or date, or a link that does not open.
    """
    link = f"/operational-safety-reviews/{safety_review['event_id']}"
    note = flow.one("Safety Officer", "Event awaiting safety check", link)

    assert note["body"] == (f"{safety_review['event_name']} ({sgt(safety_review['start_datetime'])} – "
                            f"{sgt(safety_review['end_datetime'])} SGT) has been submitted for safety checks by "
                            f"{name_of(flow.coordinator)}.")
    assert flow.call("Safety Officer", "get", "/api" + link)["event"]["event_id"] == safety_review["event_id"]


def test_ntf_041_coordinator_is_notified_of_the_safety_decision(flow):
    """TC-NTF-041 | S11 AC3: the Coordinator is told the safety review's outcome, including a return to Planning.

    Does: three events are submitted for safety checks; the Safety Officer
    approves one, rejects one and requests changes on one, with remarks for the
    last two. The Coordinator's notifications are read.
    Expect: "Safety review approved": "The safety review for <event> (<start> –
    <end> SGT) has been approved by <officer>."; "Safety review rejected": "...
    has been rejected by <officer>. Remarks: <remarks> The event has returned to
    Planning."; and "Safety changes requested": "... has been sent back with
    changes requested by <officer>. Remarks: ... returned to Planning.", each
    opening its event. A failure means the Coordinator does not learn the
    outcome, why, or that the event is back in Planning.
    """
    officer, back = name_of(user_id_for("Safety Officer")), ". Remarks: No fire marshal. The event has returned to Planning."
    for outcome, title, verdict, ending in (
            ("approved", "Safety review approved", "approved", "."),
            ("rejected", "Safety review rejected", "rejected", back),
            ("changes_requested", "Safety changes requested", "sent back with changes requested", back)):
        event = submit_for_safety(flow)
        flow.call("Safety Officer", "post", f"/api/operational-safety-reviews/{event['event_id']}/decision",
                  {"outcome": outcome, "remarks": None if outcome == "approved" else "No fire marshal."})
        note = flow.one("Event Coordinator", title, f"/events/{event['event_id']}")

        assert note["body"] == (f"The safety review for {event['event_name']} ({sgt(event['start_datetime'])} – "
                                f"{sgt(event['end_datetime'])} SGT) has been {verdict} by {officer}{ending}")


# ---------------------------------------------------------------------------
# S12 Attendee: registration and withdrawal
# ---------------------------------------------------------------------------

def open_registration(flow, capacity=40, waiting_list=False):
    """A confirmed event (safety approved) whose registration is open now."""
    event = submit_for_safety(flow, capacity)
    flow.call("Safety Officer", "post", f"/api/operational-safety-reviews/{event['event_id']}/decision",
              {"outcome": "approved"})
    now = datetime.now(timezone.utc)
    flow.call("Event Organiser", "patch", f"/api/events/{event['event_id']}/registration-period", {
        "registration_opens_at": (now - timedelta(minutes=1)).isoformat(),
        "registration_closes_at": (now + timedelta(days=1)).isoformat(), "waiting_list_enabled": waiting_list})
    return event


def details(event):
    """The event as registration notifications describe it."""
    return (f"{event['event_name']} ({sgt(event['start_datetime'])} – {sgt(event['end_datetime'])} SGT) "
            f"at {event['venue_name']}")


@pytest.fixture(scope="module")
def registered(flow):
    """The Attendee registered for an event with places left (S12 AC1, AC2, AC5)."""
    event = open_registration(flow)
    flow.register("Attendee", event)
    return event


@pytest.fixture(scope="module")
def full_event(flow):
    """An event for one, with a waiting list: another attendee took the place,
    then the Attendee registered (S12 AC3, AC4)."""
    event = open_registration(flow, capacity=1, waiting_list=True)
    first = flow.user("ITEST First Attendee", "Attendee")
    flow.register(first, event)
    flow.register("Attendee", event)
    return event, first


def test_ntf_042_attendee_is_sent_a_confirmation_on_registering(flow, registered):
    """TC-NTF-042 | S12 AC1: a confirmation when the Attendee successfully registers.

    Does: reads the Attendee's notifications after registering for an event
    that has places left.
    Expect: exactly one "Event registration confirmed" for it, opening My
    Registrations. A failure means the Attendee cannot tell the registration
    went through.
    """
    flow.one("Attendee", "Event registration confirmed", "/my-registrations", registered["event_name"])


def test_ntf_043_registration_shows_the_event_its_date_time_and_venue(flow, registered):
    """TC-NTF-043 | S12 AC2: includes the event name, date, time and venue.

    Does: reads the confirmation's text.
    Expect: "Your registration for <event> (<start> – <end> SGT) at <venue> is
    confirmed.", the venue being the event's approved booking. A failure means a
    detail is missing or wrong.
    """
    note = flow.one("Attendee", "Event registration confirmed", "/my-registrations", registered["event_name"])

    assert note["body"] == f"Your registration for {details(registered)} is confirmed."


def test_ntf_044_a_full_event_puts_the_attendee_on_the_waiting_list(flow, full_event):
    """TC-NTF-044 | S12 AC3: when full with a waiting list on, the Attendee is told they are waitlisted.

    Does: reads the notifications of the attendee who took the only place, and
    of the Attendee who registered after it was full.
    Expect: the first has "Event registration confirmed"; the Attendee has
    "Added to waiting list": "<event> ... is full, so you have been added to
    its waiting list instead. This does not confirm a place at the event." and
    no confirmation. A failure means a waitlisted Attendee believes they have a
    place, or the reverse.
    """
    event, first = full_event
    flow.one(first, "Event registration confirmed", "/my-registrations", event["event_name"])
    note = flow.one("Attendee", "Added to waiting list", "/my-registrations", event["event_name"])

    assert note["body"] == (f"{details(event)} is full, so you have been added to its waiting list instead. "
                            "This does not confirm a place at the event.")
    assert not [n for n in flow.inbox("Attendee", "/my-registrations")
                if n["title"] == "Event registration confirmed" and event["event_name"] in n["body"]]


def test_ntf_045_registered_and_waitlisted_attendees_are_told_of_a_cancellation(flow, full_event):
    """TC-NTF-045 | S12 AC4: a notification if the event is cancelled.

    Does: the Organiser cancels the full event, which has one registered and one
    waitlisted attendee.
    Expect: each has one "Event cancelled": "<event> ... has been cancelled, so
    your registration no longer applies.", opening My Registrations. A failure
    means an attendee turns up to an event that is not happening.
    """
    event, first = full_event
    flow.call("Event Organiser", "post", f"/api/events/{event['event_id']}/cancel")

    for attendee in (first, "Attendee"):
        note = flow.one(attendee, "Event cancelled", "/my-registrations", event["event_name"])
        assert note["body"] == f"{details(event)} has been cancelled, so your registration no longer applies."


def test_ntf_046_attendee_is_sent_a_confirmation_on_withdrawing(flow, registered):
    """TC-NTF-046 | S12 AC5: a confirmation when the registration is successfully withdrawn.

    Does: the Attendee withdraws their registration.
    Expect: one "Event registration withdrawn": "Your registration for <event>
    ... has been withdrawn.", opening My Registrations. A failure means the
    Attendee cannot tell the withdrawal went through.
    """
    flow.call("Attendee", "post", f"/api/events/{registered['event_id']}/registrations/withdraw")

    note = flow.one("Attendee", "Event registration withdrawn", "/my-registrations", registered["event_name"])
    assert note["body"] == f"Your registration for {details(registered)} has been withdrawn."
