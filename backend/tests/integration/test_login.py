"""Login against the real integration-test project, for every role.

Each role's account must exist in the test project with its role in
user_roles. A role whose INTEGRATION_<ROLE>_EMAIL/PASSWORD is blank is skipped.

Each test is labelled with its test case ID and the acceptance criterion it
covers from the user story "As a user, I want to login to the website so that
I can access the system":

  AC1  Users securely log in using their registered credentials.
  AC2  The user's assigned role is identified upon successful authentication.
  AC3  An error message is shown if the login is unsuccessful.
"""

import os

import pytest

ROLES = (
    "Event Organiser",
    "Event Coordinator Lead",
    "Event Coordinator",
    "Venue Staff",
    "Technical Support Staff",
    "Safety Officer",
    "Attendee",
)


def _credentials(role):
    prefix = "INTEGRATION_" + role.upper().replace(" ", "_")
    email = os.environ.get(f"{prefix}_EMAIL")
    password = os.environ.get(f"{prefix}_PASSWORD")
    if not email or not password:
        pytest.skip(f"{prefix}_EMAIL/PASSWORD not set.")
    return email, password


def _login(client, email, password):
    return client.post("/api/login", json={"email": email, "password": password})


# TC-001 to TC-007 (AC1, AC2): each role logs in with its registered email and
# password, receives a session, and is identified with its assigned role.
@pytest.mark.parametrize(
    "role", ROLES, ids=[f"TC-{n:03d} {role}" for n, role in enumerate(ROLES, 1)]
)
def test_each_role_signs_in_and_sees_its_role(client, role):
    email, password = _credentials(role)

    login = _login(client, email, password)
    assert login.status_code == 200, login.get_json()
    body = login.get_json()
    assert body["access_token"] and body["refresh_token"]

    account = client.get(
        "/api/users/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert account.status_code == 200, account.get_json()
    assert role in account.get_json()["user"]["roles"]


# TC-008 (AC1, AC3): a registered email with the wrong password is refused,
# and the user is told the login failed.
def test_wrong_password_is_rejected(client):
    email, password = _credentials("Event Organiser")

    response = _login(client, email, password + "-wrong")

    assert response.status_code == 401
    assert response.get_json() == {"error": "Incorrect email or password. Please try again."}


# TC-009 (AC1, AC3): an email with no account is refused with the same
# message as a wrong password.
def test_unknown_email_is_rejected(client):
    # The same wording stops the login form revealing which emails have accounts.
    response = _login(client, "no-such-user@connectsphere.invalid", "whatever-password")

    assert response.status_code == 401
    assert response.get_json() == {"error": "Incorrect email or password. Please try again."}


# TC-010 to TC-013 (AC3): a login with the email or password missing is
# refused with a message saying both are required.
@pytest.mark.parametrize("body", [
    pytest.param({}, id="TC-010 empty form"),
    pytest.param({"email": "", "password": "x"}, id="TC-011 blank email"),
    pytest.param({"email": "someone@example.com", "password": ""}, id="TC-012 blank password"),
    pytest.param({"email": "someone@example.com"}, id="TC-013 no password field"),
])
def test_missing_email_or_password_is_rejected_before_supabase(client, body):
    response = client.post("/api/login", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "Email and password are required."}


# TC-014 (AC1): the refresh token issued at login renews the session, so a
# signed-in user keeps access without logging in again.
def test_refresh_token_from_login_gives_a_working_session(client):
    email, password = _credentials("Event Organiser")
    refresh_token = _login(client, email, password).get_json()["refresh_token"]

    refreshed = client.post("/api/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200, refreshed.get_json()

    account = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {refreshed.get_json()['access_token']}"},
    )
    assert account.status_code == 200
