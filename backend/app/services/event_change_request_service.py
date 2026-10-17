"""Application operations for event change requests."""

from app.schemas import event_change_request as schema
from app.services.event_store import supabase_request


class EventChangeRequestError(Exception):
    """Expected validation, authorization, conflict, or stale-data failure."""

    def __init__(self, message, status=400, *, errors=None,
                 critical_fields=None, stale=False):
        super().__init__(message)
        self.message = message
        self.status = status
        self.errors = errors
        self.critical_fields = critical_fields
        self.stale = stale

    def to_dict(self):
        result = {"error": self.message}
        if self.errors:
            result["errors"] = self.errors
        if self.critical_fields:
            result["critical_fields"] = self.critical_fields
        if self.stale:
            result["stale"] = True
        return result


def _rpc(name, token, payload):
    result = supabase_request(
        f"/rest/v1/rpc/{name}", token=token, payload=payload, method="POST"
    )
    if isinstance(result, dict) and result.get("error"):
        raise EventChangeRequestError(
            result["error"], status=result.get("status", 400),
            errors=result.get("errors"),
            critical_fields=result.get("critical_fields"),
            stale=result.get("stale", False),
        )
    return result


def list_eligible_events(token):
    """List non-terminal events submitted by the signed-in organiser."""
    return _rpc("eligible_event_change_request_events", token, {}).get("events", [])


def list_change_requests(event_id, token):
    """List requests visible to the event's organiser or coordinator."""
    return _rpc("event_change_requests_for_event", token, {
        "p_event_id": int(event_id),
    }).get("change_requests", [])


def submit_change_request(event_id, payload, token):
    """Validate and submit proposed values without changing the event."""
    submission, errors = schema.parse_submission(payload)
    if errors:
        raise EventChangeRequestError(
            "The change request could not be submitted because some details are invalid.",
            errors=errors,
        )
    return _rpc("submit_event_change_request", token, {
        "p_event_id": int(event_id),
        "p_reason": submission["reason"],
        "p_proposed_values": submission["proposed_values"],
        "p_expected_event_updated_at": submission["expected_event_updated_at"],
        "p_confirm_critical": submission["confirm_critical"],
    })

