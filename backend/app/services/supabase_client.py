"""Creates Supabase clients for backend database access.

Credentials are read from backend/.env, which is never committed. See
backend/.env.example for the variables you need to set.

Authenticated Flask requests receive their own client carrying the caller's
bearer token for authentication and identity-dependent RPCs. Authorized
backend data operations use a separate server-only service-role client after
Flask has checked the user's role and record assignment.
"""

import os

from flask import g, has_request_context, request
from supabase import Client, ClientOptions, create_client

_anonymous_client: Client | None = None
_service_client: Client | None = None
_REQUEST_CLIENT_KEY = "_authenticated_supabase_client"
_REQUEST_SERVICE_CLIENT_KEY = "_service_role_supabase_client"


def get_supabase() -> Client:
    """Return a client operating as the current user, or anon when signed out."""
    url, key = _credentials()
    token = _bearer_token()

    if token is not None:
        client = getattr(g, _REQUEST_CLIENT_KEY, None)
        if client is None:
            client = create_client(
                url,
                key,
                ClientOptions(
                    headers={"Authorization": f"Bearer {token}"},
                    persist_session=False,
                    auto_refresh_token=False,
                ),
            )
            setattr(g, _REQUEST_CLIENT_KEY, client)
        return client

    return _get_anonymous_client(url, key)


def _credentials():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")

    # Fail loudly and early: a missing key otherwise surfaces much later as a
    # confusing 401 from Supabase.
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set. Copy "
            "backend/.env.example to backend/.env and fill them in using "
            "the values from Supabase > Project Settings > API Keys."
        )

    return url, key


def get_supabase_admin() -> Client:
    """Return a server-only client that bypasses database row policies.

    Callers must perform authorization in the backend before using this
    client. Never return this client or its key to the frontend.
    """
    url, key = _admin_credentials()
    if has_request_context():
        client = getattr(g, _REQUEST_SERVICE_CLIENT_KEY, None)
        if client is None:
            client = create_client(
                url,
                key,
                ClientOptions(
                    persist_session=False,
                    auto_refresh_token=False,
                ),
            )
            setattr(g, _REQUEST_SERVICE_CLIENT_KEY, client)
        return client

    return _get_service_client(url, key)


def _admin_credentials():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in the "
            "backend environment. Keep the service-role key server-side only."
        )
    return url, key


def _bearer_token():
    if not has_request_context():
        return None

    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _get_anonymous_client(url, key):
    global _anonymous_client

    if _anonymous_client is None:
        _anonymous_client = create_client(url, key)

    return _anonymous_client


def _get_service_client(url, key):
    global _service_client

    if _service_client is None:
        _service_client = create_client(
            url,
            key,
            ClientOptions(
                persist_session=False,
                auto_refresh_token=False,
            ),
        )

    return _service_client
