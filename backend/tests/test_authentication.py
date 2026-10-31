"""Unit tests for bearer-token verification and authentication failures."""

from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError
import io

import pytest
from flask import Flask

from app.services import event_store
from app.services.event_store import StoreError


@pytest.fixture
def app():
    return Flask(__name__)


# Maps Supabase authentication failures to safe HTTP responses for the client.
@pytest.mark.parametrize(("path", "upstream_status", "expected"), [
    ("/auth/v1/token", 400, 401),
    ("/auth/v1/token", 401, 401),
    ("/rest/v1/events", 403, 403),
    ("/rest/v1/events", 500, 503),
])
def test_authentication_status_mapping(path, upstream_status, expected):
    assert event_store._application_status(path, upstream_status) == expected


# Requires Supabase configuration before an authentication request is sent.
def test_authentication_request_requires_supabase_credentials(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    with pytest.raises(StoreError) as caught:
        event_store.supabase_request("/auth/v1/user")

    assert caught.value.status == 503
    assert "credentials are missing" in caught.value.message


# Surfaces a safe error when Supabase returns an invalid authentication payload.
def test_authentication_request_rejects_non_json_response(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = b"not-json"
    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setattr(event_store, "urlopen", lambda *_args, **_kwargs: response)

    with pytest.raises(StoreError) as caught:
        event_store.supabase_request("/auth/v1/user", token="valid-token")

    assert caught.value.status == 503
    assert "non-JSON response" in caught.value.message


# Treats an unavailable Supabase authentication service as a temporary failure.
def test_authentication_request_handles_network_failure(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setattr(
        event_store, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("offline"))
    )

    with pytest.raises(StoreError) as caught:
        event_store.supabase_request("/auth/v1/user")

    assert caught.value.status == 503
    assert caught.value.message == "Supabase is temporarily unavailable."


# Keeps an empty upstream error body from exposing or depending on database details.
def test_authentication_request_handles_empty_upstream_error_body(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    error = HTTPError("https://example.test/auth/v1/user", 500, "Server Error", {}, io.BytesIO(b""))
    monkeypatch.setattr(event_store, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(error))

    with pytest.raises(StoreError) as caught:
        event_store.supabase_request("/auth/v1/user")

    assert caught.value.status == 503


# Rejects requests that do not carry a usable bearer token.
@pytest.mark.parametrize("header", [None, "", "Basic token", "Bearer", "Bearer   "])
def test_authenticated_user_rejects_missing_or_malformed_bearer_token(app, header):
    headers = {} if header is None else {"Authorization": header}

    with app.test_request_context(headers=headers), pytest.raises(StoreError) as caught:
        event_store.authenticated_user(lambda *_args, **_kwargs: {"id": "unused"})

    assert caught.value.status == 401


# Rejects a bearer token when Supabase cannot verify it as a user identity.
def test_authenticated_user_rejects_unverified_token(app):
    with app.test_request_context(headers={"Authorization": "Bearer token"}), pytest.raises(StoreError) as caught:
        event_store.authenticated_user(lambda *_args, **_kwargs: {})

    assert caught.value.status == 401


# Returns only a Supabase-verified token and user identity to protected routes.
def test_authenticated_user_and_token_return_verified_identity(app):
    calls = []

    def query(path, *, token):
        calls.append((path, token))
        return {"id": "user-1"}

    with app.test_request_context(headers={"Authorization": "Bearer verified-token"}):
        assert event_store.authenticated_user(query) == ("verified-token", "user-1")
        assert event_store.authenticated_token(query) == "verified-token"

    assert calls == [
        ("/auth/v1/user", "verified-token"),
        ("/auth/v1/user", "verified-token"),
    ]


# Keeps default authentication errors generic while preserving explicit messages.
def test_store_error_uses_safe_default_messages():
    assert StoreError(401).to_dict() == {"error": "Please sign in again."}
    assert StoreError(503).to_dict() == {"error": "Event service is temporarily unavailable."}
    assert StoreError(403, "Access denied", code="42501").code == "42501"
