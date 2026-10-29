"""Confirms the integration project is reachable and the test accounts work.

Mirrors what the browser does on sign-in: POST /api/login, then load the
account through /api/users/me, which ProtectedPage waits for before it shows
the home page. The redirect to /home itself happens in React and is not
visible from here.
"""

import os


def test_coordinator_signs_in_and_home_page_account_loads(client):
    login = client.post("/api/login", json={
        "email": os.environ["INTEGRATION_EVENT_COORDINATOR_EMAIL"],
        "password": os.environ["INTEGRATION_EVENT_COORDINATOR_PASSWORD"],
    })
    assert login.status_code == 200, login.get_json()
    token = login.get_json()["access_token"]

    account = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})

    assert account.status_code == 200, account.get_json()
    assert "Event Coordinator" in account.get_json()["user"]["roles"]
