"""Business logic for creating and submitting event requests.

Sits between the HTTP routes and Supabase so that the rules can be tested
without starting Flask, and so the routes stay thin.
"""

from app.schemas import event_request as schema
from app.services import db


class EventRequestError(Exception):
    """A problem worth reporting to the user rather than a 500."""

    def __init__(self, message, status_code=400, errors=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors or {}

    def to_dict(self):
        body = {"error": self.message}
        if self.errors:
            body["errors"] = self.errors
        return body


def create_event_request(payload, submit=True):
    """Create an event request, either as a draft or submitted for review.

    Returns the stored row. Raises EventRequestError when the payload is not
    acceptable or the database rejects it.
    """
    record, errors = schema.parse_payload(payload)

    if submit:
        errors = {**schema.find_missing(record), **errors}

    if errors:
        raise EventRequestError(
            "The event request could not be created because some details are "
            "missing or invalid.",
            errors=errors,
        )

    # The database requires these columns, so send an explicit value rather
    # than relying on whatever the caller happened to include.
    record.setdefault("required_facilities", [])
    record.setdefault("equipment_requirements", [])
    record.setdefault("need_wheelchair_accessibility", False)
    record.setdefault("need_blind_accessibility", False)

    if submit:
        record["status"] = schema.STATUS_SUBMITTED
        record["submitted_at"] = _now()
    else:
        record["status"] = schema.STATUS_DRAFT

    rows = _execute(
        lambda table: table.insert(record).execute(),
        action="create the event request",
    )

    if not rows:
        raise EventRequestError(
            "The event request could not be created. Please try again.",
            status_code=502,
        )

    return rows[0]


def apply_edit(existing, payload):
    """Validate an edit and write it. Returns (row, changes).

    `changes` records what actually differed, as {field: {from, to}}, because
    the previous value is lost the moment the row is updated.

    Only format is checked here, not completeness: an unfinished request is
    allowed to stay unfinished. The mandatory-field check happens on
    submission. The caller decides whether editing is permitted at all.
    """
    event_request_id = existing["event_request_id"]
    record, errors = schema.parse_payload(payload)

    # A request belongs to the Organiser who started it; handing it to someone
    # else is not part of any current story.
    if "event_organiser_id" in record:
        if record["event_organiser_id"] != existing.get("event_organiser_id"):
            errors["event_organiser_id"] = (
                "The event organiser of a request cannot be changed."
            )
        del record["event_organiser_id"]

    if errors:
        raise EventRequestError(
            "The changes could not be saved because some details are invalid.",
            errors=errors,
        )

    if not record:
        raise EventRequestError("No changes were provided.")

    changes = schema.diff(existing, record)

    record["updated_at"] = _now()

    rows = _execute(
        lambda table: table.update(record)
        .eq("event_request_id", event_request_id)
        .execute(),
        action="save the changes",
    )

    if not rows:
        raise EventRequestError(
            "The changes could not be saved. Please try again.", status_code=502
        )

    return rows[0], changes


def mark_submitted(event_request_id):
    """Validate completeness and move a request into the review queue."""
    now = _now()

    rows = _execute(
        lambda table: table.update(
            {
                "status": schema.STATUS_SUBMITTED,
                "submitted_at": now,
                "updated_at": now,
            }
        )
        .eq("event_request_id", event_request_id)
        .execute(),
        action="submit the event request",
    )

    if not rows:
        raise EventRequestError(
            "The event request could not be submitted. Please try again.",
            status_code=502,
        )

    return rows[0]


def find_blocking_errors(record):
    """Everything that stops a request being sent for review."""
    return {**schema.find_missing(record), **schema.check_timing(record)}


def require_event_request(event_request_id):
    """Fetch a request or raise a 404."""
    existing = get_event_request(event_request_id)

    if existing is None:
        raise EventRequestError(
            f"No event request found with id {event_request_id}.", status_code=404
        )

    return existing


def list_event_requests(event_organiser_id=None, status=None):
    """List event requests, most recently changed first.

    Both filters are optional and combine. An Organiser passes their own id to
    find drafts they left unfinished; an Event Coordinator passes
    status=submitted to see what is waiting for review.
    """
    if status is not None and status not in schema.ALL_STATUSES:
        raise EventRequestError(
            "Status must be one of: " + ", ".join(sorted(schema.ALL_STATUSES)) + "."
        )

    def query(table):
        builder = table.select("*")
        if event_organiser_id is not None:
            builder = builder.eq("event_organiser_id", event_organiser_id)
        if status is not None:
            builder = builder.eq("status", status)
        return builder.order("updated_at", desc=True).execute()

    return _execute(query, action="list the event requests")


def get_event_request(event_request_id):
    """Return one event request, or None. Used to review details before submitting."""
    rows = _execute(
        lambda table: table.select("*")
        .eq("event_request_id", event_request_id)
        .limit(1)
        .execute(),
        action="read the event request",
    )

    return rows[0] if rows else None


def _now():
    return db.utc_now()


def _execute(operation, action):
    """Run a Supabase call and turn database errors into readable messages."""
    return db.run(schema.TABLE_NAME, operation, action, _translate)


def _translate(exc, action):
    code = getattr(exc, "code", None)
    detail = str(getattr(exc, "message", None) or exc)

    # 22P02: a value did not match a PostgreSQL enum, e.g. an unknown facility.
    if code == "22P02" and "facility" in detail:
        return EventRequestError(
            "One or more of the required facilities is not recognised. Choose "
            "facilities from the ConnectSphere venue catalogue.",
            errors={"required_facilities": detail},
        )

    if code == "22P02":
        return EventRequestError(f"Some details are not in the expected format: {detail}")

    # 23503: foreign key violation, i.e. the organiser is not a known user.
    if code == "23503":
        return EventRequestError(
            "The event organiser does not match a known ConnectSphere user.",
            errors={"event_organiser_id": detail},
        )

    return EventRequestError(
        f"Could not {action} because the database is unavailable. Please try again.",
        status_code=502,
    )
