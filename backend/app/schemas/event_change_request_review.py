"""Validation and derived information for change-request reviews."""

DECISION_APPROVE = "approve"
DECISION_REJECT = "reject"
DECISIONS = frozenset({DECISION_APPROVE, DECISION_REJECT})

def parse_decision(payload):
    """Validate approve/reject input; rejection will require a non-blank reason."""
    if not isinstance(payload, dict):
        return {}, {"_body": "Provide a review decision."}

    errors = {}
    decision = payload.get("decision")
    if decision not in DECISIONS:
        errors["decision"] = "Choose Approve or Reject."

    reason = payload.get("reason", "")
    if not isinstance(reason, str):
        errors["reason"] = "The decision reason must be text."
        reason = ""
    else:
        reason = reason.strip()
        if len(reason) > 2000:
            errors["reason"] = "The decision reason must be 2000 characters or fewer."
        elif decision == DECISION_REJECT and not reason:
            errors["reason"] = "Please provide a reason for rejecting this change request."

    if errors:
        return {}, errors
    return {"decision": decision, "reason": reason or None}, {}

