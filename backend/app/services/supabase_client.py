"""Creates and shares a single Supabase client for the whole backend.

Credentials are read from backend/.env, which is never committed. See
backend/.env.example for the variables you need to set.
"""

import os

from supabase import Client, create_client

# Built on first use and then reused, so we do not open a new connection on
# every request.
_client: Client | None = None


def get_supabase() -> Client:
    """Return the shared Supabase client, creating it on first use."""
    global _client

    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")

        # Fail loudly and early: a missing key otherwise surfaces much later as
        # a confusing 401 from Supabase.
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set. Copy "
                "backend/.env.example to backend/.env and fill them in using "
                "the values from Supabase > Project Settings > API Keys."
            )

        _client = create_client(url, key)

    return _client
