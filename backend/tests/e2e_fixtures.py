"""Create and remove the test data the Playwright registration tests need.

Registration only works on a confirmed event, and an event is confirmed only
through the real flow: request, assignment, approval, an approved venue
booking, safety submission and a Safety Officer approval. This reuses the
Flow helper from tests/integration/test_notifications.py to take each step
through the API, against the integration-test project only.

From backend/:
    python -m tests.e2e_fixtures setup <state file>     prints the data as JSON
    python -m tests.e2e_fixtures teardown <state file>  removes everything made
"""

import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
TEST_ENV = BACKEND / ".env.integration-test"

test_url = dotenv_values(TEST_ENV).get("SUPABASE_URL", "")
dev_url = dotenv_values(BACKEND / ".env").get("SUPABASE_URL", "")
if not test_url or test_url.rstrip("/") == dev_url.rstrip("/"):
    raise SystemExit(f"{TEST_ENV.name} must point at the test project, not dev.")
load_dotenv(TEST_ENV, override=True)

import os  # noqa: E402

from app import create_app  # noqa: E402
from tests.integration.supabase_admin import admin_request  # noqa: E402
from tests.integration.test_notifications import Flow, submit_for_safety  # noqa: E402

DETAILS = {"full_name": "E2E Filler Attendee", "contact_email": "filler@connectsphere.invalid",
           "contact_phone": "+65 6123 4567"}


def _sign_in_as(client):
    tokens = {}

    def sign_in(role):
        if role not in tokens:
            prefix = "INTEGRATION_" + role.upper().replace(" ", "_")
            login = client.post("/api/login", json={"email": os.environ[f"{prefix}_EMAIL"],
                                                    "password": os.environ[f"{prefix}_PASSWORD"]})
            tokens[role] = login.get_json()["access_token"]
        return {"Authorization": f"Bearer {tokens[role]}"}

    return sign_in


def _account(flow, name, role):
    """A temporary account the browser can sign in as: Flow.user() keeps no password."""
    email, password = f"e2e-{uuid.uuid4().hex[:10]}@connectsphere.invalid", uuid.uuid4().hex
    user_id = admin_request("/auth/v1/admin/users", {
        "email": email, "password": password, "email_confirm": True, "user_metadata": {"name": name},
    })["id"]
    flow.users.append(user_id)
    role_id = admin_request(f"/rest/v1/roles?select=role_id&role_name=eq.{role.replace(' ', '%20')}")[0]["role_id"]
    admin_request("/rest/v1/user_roles", {"user_id": user_id, "role_id": role_id})
    token = flow.client.post("/api/login", json={"email": email, "password": password}).get_json()["access_token"]
    return {"id": user_id, "email": email, "password": password, "name": name,
            "headers": {"Authorization": f"Bearer {token}"}}


def _confirm(flow, opens, closes, capacity=40, waiting_list=False, equipment=False):
    """An event taken through the real flow to Confirmed, with its registration period set."""
    if equipment:
        event, venue = flow.event(capacity), flow.venue()
        item = flow.equipment_item()
        flow.review_equipment(flow.request_equipment(event, item, 2), "accepted", item, 2)
        flow.decide(flow.book(event, venue), "approved")
        flow.call("Event Coordinator", "post", f"/api/events/{event['event_id']}/safety-checks")
        event = {**event, "venue_name": venue["venue_name"], "equipment_type": item["equipment_type"]}
    else:
        event = submit_for_safety(flow, capacity)
    flow.call("Safety Officer", "post", f"/api/operational-safety-reviews/{event['event_id']}/decision",
              {"outcome": "approved"})
    flow.call("Event Organiser", "patch", f"/api/events/{event['event_id']}/registration-period", {
        "registration_opens_at": opens.isoformat(), "registration_closes_at": closes.isoformat(),
        "waiting_list_enabled": waiting_list})
    return admin_request(f"/rest/v1/events?select=*&event_id=eq.{event['event_id']}")[0] | {
        key: event[key] for key in ("venue_name", "equipment_type") if key in event}


def _register(flow, who, event):
    flow.call(who, "post", f"/api/events/{event['event_id']}/registrations", DETAILS)


def setup(state_file):
    client = create_app().test_client()
    flow = Flow(client, _sign_in_as(client))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        filler = _account(flow, "E2E Filler Attendee", "Attendee")
        data = {
            # Open now, nobody registered: the Attendee registers in the test.
            "open": _confirm(flow, now - timedelta(minutes=5), now + timedelta(days=5), equipment=True),
            # Open, one place, taken by the filler: registration is refused.
            "full": _confirm(flow, now - timedelta(minutes=5), now + timedelta(days=5), capacity=1),
            # Open, one place taken, waiting list on: the Attendee is waitlisted.
            "waitlist": _confirm(flow, now - timedelta(minutes=5), now + timedelta(days=5),
                                 capacity=1, waiting_list=True),
            # Open, the Attendee already registered: they withdraw in the test.
            "withdraw": _confirm(flow, now - timedelta(minutes=5), now + timedelta(days=5)),
            "not_open": _confirm(flow, now + timedelta(days=1), now + timedelta(days=5)),
            "closed": _confirm(flow, now - timedelta(days=2), now - timedelta(days=1)),
            # The Attendee registered and withdrew, then the event was cancelled.
            "cancelled": _confirm(flow, now - timedelta(minutes=5), now + timedelta(days=5)),
            "planning": flow.event(),
            # For attendee-registration-notifications.spec.js only, so other files cannot
            # change them: the Attendee registers then withdraws; joins a waiting list;
            # and is registered for an event the Organiser cancels in the test.
            "notify_register": _confirm(flow, now - timedelta(minutes=5), now + timedelta(days=5)),
            "notify_waitlist": _confirm(flow, now - timedelta(minutes=5), now + timedelta(days=5),
                                        capacity=1, waiting_list=True),
            "notify_cancel": _confirm(flow, now - timedelta(minutes=5), now + timedelta(days=5)),
        }
        for event in ("open", "full", "waitlist", "notify_waitlist"):
            _register(flow, filler, data[event])
        _register(flow, "Attendee", data["notify_cancel"])
        _register(flow, "Attendee", data["waitlist"])
        _register(flow, "Attendee", data["withdraw"])
        _register(flow, "Attendee", data["cancelled"])
        flow.call("Attendee", "post", f"/api/events/{data['cancelled']['event_id']}/registrations/withdraw", {})
        flow.call("Event Organiser", "post", f"/api/events/{data['cancelled']['event_id']}/cancel", {})
        data["filler"] = {key: filler[key] for key in ("id", "name")} | {
            "email": DETAILS["contact_email"], "phone": DETAILS["contact_phone"]}
        data["empty_attendee"] = {k: v for k, v in _account(flow, "E2E New Attendee", "Attendee").items()
                                  if k != "headers"}
        data["other_organiser"] = {k: v for k, v in _account(flow, "E2E Other Organiser", "Event Organiser").items()
                                   if k != "headers"}
    finally:
        Path(state_file).write_text(json.dumps({
            "since": flow.since, "requests": flow.requests, "venues": flow.venues,
            "users": flow.users, "equipment": flow.equipment}))
    print(json.dumps(data, default=str))


def _account_exists(user_id):
    try:
        admin_request(f"/auth/v1/admin/users/{user_id}")
    except AssertionError as error:
        if "user_not_found" in str(error):
            return False
        raise
    return True


def teardown(state_file):
    path = Path(state_file)
    if not path.exists():
        return
    state = json.loads(path.read_text())
    client = create_app().test_client()
    flow = Flow(client, _sign_in_as(client))
    flow.since, flow.requests, flow.venues = state["since"], state["requests"], state["venues"]
    # An account may already be gone (an earlier teardown got that far, or the test
    # database was reset), and deleting it again would fail, so skip those.
    flow.users, flow.equipment = [user for user in state["users"] if _account_exists(user)], state["equipment"]
    # Remove registrations before their events.
    names = []
    for request_id in flow.requests:
        names += [row["event_name"] for row in admin_request(
            f"/rest/v1/event_request?select=event_name&event_request_id=eq.{request_id}")]
        for event in admin_request(f"/rest/v1/events?select=event_id&event_request_id=eq.{request_id}"):
            admin_request(f"/rest/v1/event_registration?event_id=eq.{event['event_id']}", method="DELETE")
    # Flow.clean() deletes every notification newer than flow.since, which would also
    # delete other runs' notifications (a CI run, or later local runs when this is a
    # stopped run's state). Keep it from deleting any, then delete only those about
    # this run's events; each event name is unique to the run.
    flow.since = 2 ** 62
    flow.clean()
    for name in names:
        admin_request(f"/rest/v1/notifications?body=like.*{quote(name)}*", method="DELETE")
    path.unlink()


if __name__ == "__main__":
    {"setup": setup, "teardown": teardown}[sys.argv[1]](sys.argv[2])
