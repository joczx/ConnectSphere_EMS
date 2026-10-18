"""Backend role and record-level access checks for protected API routes."""

from dataclasses import dataclass
from urllib.parse import quote

from flask import g

from app.services.event_store import (
    authenticated_user,
    supabase_admin_request,
    supabase_request,
)


class AuthorizationError(Exception):
    def __init__(self, message, status=403):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass(frozen=True)
class RequestUser:
    user_id: str
    token: str
    roles: frozenset[str]


def normalize_role(value):
    normalized = " ".join(
        str(value or "").replace("_", " ").strip().casefold().split()
    )
    return "event organiser" if normalized == "event organizer" else normalized


def current_user():
    """Verify the bearer token and load roles using server-side data access."""
    cached = getattr(g, "_authorized_request_user", None)
    if cached is not None:
        return cached

    token, user_id = authenticated_user(supabase_request)
    user_filter = quote(str(user_id), safe="")
    memberships = supabase_admin_request(
        f"/rest/v1/user_roles?select=role_id&user_id=eq.{user_filter}"
    )
    role_ids = list(dict.fromkeys(
        str(row["role_id"])
        for row in memberships
        if row.get("role_id") is not None
    ))
    role_names = []
    if role_ids:
        role_filter = ",".join(quote(role_id, safe="") for role_id in role_ids)
        rows = supabase_admin_request(
            f"/rest/v1/roles?select=role_name&role_id=in.({role_filter})"
        )
        role_names = [normalize_role(row.get("role_name")) for row in rows]

    identity = RequestUser(
        user_id=str(user_id),
        token=token,
        roles=frozenset(name for name in role_names if name),
    )
    g._authorized_request_user = identity
    return identity


def require_roles(*roles):
    """Return the verified caller only when they hold at least one role."""
    identity = current_user()
    allowed = {normalize_role(role) for role in roles}
    if not identity.roles.intersection(allowed):
        names = " or ".join(roles)
        raise AuthorizationError(f"Only {names} can access this resource.")
    return identity


def has_role(identity, role):
    return normalize_role(role) in identity.roles


def load_event(event_id):
    rows = supabase_admin_request(
        f"/rest/v1/events?select=*&event_id=eq.{quote(str(event_id), safe='')}&limit=1"
    )
    return rows[0] if rows else None


def require_event_access(event_id, identity=None):
    """Return an event only to its assigned Organiser or Event Coordinator."""
    identity = identity or current_user()
    event = load_event(event_id)
    if event is None:
        raise AuthorizationError("Event not found or access unavailable.", status=404)

    user_id = identity.user_id
    organiser_access = (
        has_role(identity, "Event Organiser")
        and str(event.get("event_organiser_id")) == user_id
    )
    coordinator_access = (
        has_role(identity, "Event Coordinator")
        and str(event.get("event_coordinator_id")) == user_id
    )
    if not (organiser_access or coordinator_access):
        raise AuthorizationError("Event not found or access unavailable.", status=404)
    return event


def require_event_staff_access(event, identity=None):
    """Allow Venue Staff to operate only on a booking's assigned event."""
    identity = identity or current_user()
    if (
        has_role(identity, "Venue Staff")
        and str(event.get("venue_staff_id")) == identity.user_id
    ):
        return identity
    raise AuthorizationError(
        "Booking request not found or access unavailable.", status=404
    )


def load_event_request(event_request_id):
    rows = supabase_admin_request(
        "/rest/v1/event_request?select=*"
        f"&event_request_id=eq.{quote(str(event_request_id), safe='')}&limit=1"
    )
    return rows[0] if rows else None


def require_event_request_access(event_request_id, allow_assigned_coordinator=True):
    """Allow Organisers their rows and Coordinators their assigned review queue."""
    identity = current_user()
    event_request = load_event_request(event_request_id)
    if event_request is None:
        raise AuthorizationError(
            "Event request not found or access unavailable.", status=404
        )

    if (
        has_role(identity, "Event Organiser")
        and str(event_request.get("event_organiser_id")) == identity.user_id
    ):
        return identity, event_request

    if (
        allow_assigned_coordinator
        and has_role(identity, "Event Coordinator")
        and str(event_request.get("event_coordinator_id")) == identity.user_id
    ):
        return identity, event_request

    raise AuthorizationError(
        "Event request not found or access unavailable.", status=404
    )


def require_event_request_owner(event_request_id):
    identity = require_roles("Event Organiser")
    event_request = load_event_request(event_request_id)
    if (
        event_request is None
        or str(event_request.get("event_organiser_id")) != identity.user_id
    ):
        raise AuthorizationError(
            "Event request not found or access unavailable.", status=404
        )
    return identity, event_request
