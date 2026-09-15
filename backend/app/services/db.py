"""Shared Supabase plumbing used by the service modules."""

from datetime import datetime, timezone

from app.services.supabase_client import get_supabase


def utc_now():
    """Current time as an ISO 8601 string, for timestamptz columns."""
    return datetime.now(timezone.utc).isoformat()


def run(table_name, operation, action, translate):
    """Run a Supabase call and return its rows.

    `translate(exc, action)` builds the error to raise when the database
    refuses, so each service can phrase its own messages.
    """
    try:
        response = operation(get_supabase().table(table_name))
    except Exception as exc:  # noqa: BLE001 - mapped to a user-facing message
        raise translate(exc, action) from exc

    return response.data or []
