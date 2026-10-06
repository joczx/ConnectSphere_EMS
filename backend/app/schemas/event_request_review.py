"""Validation rules for Event Coordinator reviews.

Backs the "Event Review and Approval" user story. Free of Flask and Supabase
imports so the rules can be unit tested on their own.
"""

from app.schemas import event_request as request_schema

REVIEW_TABLE = "event_request_review"

# public.review_outcome
OUTCOME_APPROVED = "approved"
OUTCOME_REJECTED = "rejected"
OUTCOME_CLARIFICATION = "clarification_requested"
OUTCOMES = frozenset({OUTCOME_APPROVED, OUTCOME_REJECTED, OUTCOME_CLARIFICATION})

# What the request's status becomes once the outcome is recorded. Approving
# moves it straight into planning: the customer described "approved" and
# "planning (approved event)" as the same state seen from two angles.
#
# Requesting clarification deliberately leaves the request where it is. The
# customer confirmed clarification "can be a sub-state of under_review" rather
# than a status of its own, and with under_review retired that sub-state is
# derived from the latest review row against a still-submitted request.
OUTCOME_TO_STATUS = {
    OUTCOME_APPROVED: request_schema.STATUS_PLANNING,
    OUTCOME_REJECTED: request_schema.STATUS_REJECTED,
    OUTCOME_CLARIFICATION: request_schema.STATUS_SUBMITTED,
}

# A request may only be reviewed once the Organiser has submitted it. A draft
# has not been sent for review, and an already-decided request is finished.
REVIEWABLE_STATUSES = frozenset({request_schema.STATUS_SUBMITTED})

# Approving without comment is fine. Rejecting or asking for clarification
# without saying why leaves the Organiser with nothing to act on.
OUTCOMES_NEEDING_COMMENTS = frozenset({OUTCOME_REJECTED, OUTCOME_CLARIFICATION})

# What a client may send. reviewer_id is deliberately absent: a review has to
# be attributable to whoever actually made it, so the identity comes from the
# authenticated session rather than the request body. A client that sends one
# now gets "Unrecognised field", which is better than being quietly ignored.
WRITABLE_FIELDS = ("outcome", "comments")


def parse_payload(payload, reviewer_id=None):
    """Turn a review body into a database-ready record.

    `reviewer_id` is the signed-in user, supplied by the route from the
    verified session. Returns (record, errors).
    """
    errors = {}

    if not isinstance(payload, dict):
        return {}, {"_body": "Expected a JSON object describing the review."}

    unknown = sorted(set(payload) - set(WRITABLE_FIELDS))
    if unknown:
        errors["_body"] = f"Unrecognised field(s): {', '.join(unknown)}."

    record = {}

    reviewer = request_schema.clean_user_id(reviewer_id)
    if reviewer is None:
        errors["reviewer_id"] = (
            "The reviewing Event Coordinator could not be identified. "
            "Please sign in again."
        )
    else:
        record["reviewer_id"] = reviewer

    outcome = payload.get("outcome")
    if not isinstance(outcome, str) or not outcome.strip():
        errors["outcome"] = (
            "An outcome is required: " + ", ".join(sorted(OUTCOMES)) + "."
        )
    elif outcome.strip() not in OUTCOMES:
        errors["outcome"] = "Outcome must be one of: " + ", ".join(sorted(OUTCOMES)) + "."
    else:
        record["outcome"] = outcome.strip()

    comments = payload.get("comments")
    if comments is None or (isinstance(comments, str) and not comments.strip()):
        record["comments"] = None
    elif isinstance(comments, str):
        record["comments"] = comments.strip()
    else:
        errors["comments"] = "Comments must be text."

    if record.get("outcome") in OUTCOMES_NEEDING_COMMENTS and not record.get("comments"):
        errors["comments"] = (
            "A comment is required when rejecting a request or asking for "
            "clarification, so the Event Organiser knows what to do next."
        )

    return record, errors


def describe(outcome, event_name):
    """Messages for the people involved. Returns (organiser_text, reviewer_text)."""
    name = event_name or "your event request"

    if outcome == OUTCOME_APPROVED:
        return (
            f"Your event request '{name}' has been approved.",
            f"You approved the event request '{name}'.",
        )

    if outcome == OUTCOME_REJECTED:
        return (
            f"Your event request '{name}' has been rejected. "
            "See the Event Coordinator's comments for the reason.",
            f"You rejected the event request '{name}'.",
        )

    return (
        f"The Event Coordinator has requested clarification on your event "
        f"request '{name}'.",
        f"You requested clarification on the event request '{name}'.",
    )
