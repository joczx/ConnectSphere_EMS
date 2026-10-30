"""Arrange and clean up integration-test data with the secret key.

The secret key bypasses Row Level Security, so use these only for setting up
and removing test data, never for the request under test.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import pytest


def admin_request(path, payload=None, method=None):
    """Call the test project's REST API with the secret key, bypassing RLS.

    For arranging and cleaning up test data only. Never use it for the request
    under test, or Row Level Security is not being tested at all.
    """
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return _rest(path, key, key, payload, method)


def delete_as_user(path, auth_header):
    """DELETE through the REST API as a signed-in user.

    Needed for equipment_request: guard_equipment_request_review() returns NEW
    for a secret-key DELETE, which is NULL there, so Postgres silently skips the
    delete. The requester can still delete their own pending request.
    """
    token = auth_header["Authorization"].removeprefix("Bearer ")
    return _rest(path, os.environ["SUPABASE_ANON_KEY"], token, method="DELETE")


def _rest(path, api_key, token, payload=None, method=None):
    method = method or ("GET" if payload is None else "POST")
    request = urllib.request.Request(
        os.environ["SUPABASE_URL"].rstrip("/") + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"apikey": api_key, "Authorization": f"Bearer {token}",
                 "Content-Type": "application/json", "Prefer": "return=representation"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise AssertionError(f"Test setup failed: {method} {path} -> "
                             f"{error.code} {error.read().decode(errors='replace')}") from None
    return json.loads(body) if body else []


def user_id_for(role):
    """The test-project user ID of `role`'s account in .env.integration-test."""
    email = os.environ.get(f"INTEGRATION_{role.upper().replace(' ', '_')}_EMAIL")
    if not email:
        pytest.skip(f"No test account configured for {role}.")
    rows = admin_request(f"/rest/v1/users?select=user_id&email=eq.{urllib.parse.quote(email)}")
    if not rows:
        pytest.skip(f"{email} has no row in public.users in the test project.")
    return rows[0]["user_id"]
