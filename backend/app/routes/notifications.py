"""Minimal read access to in-app notifications.

Enough for a user to see an outcome they were notified about. Marking as read,
preferences and delivery channels belong to the Notification System story.
"""

from flask import Blueprint, jsonify, request

from app.schemas.event_request import clean_user_id
from app.services import notification_service
from app.services.event_request_service import EventRequestError
from app.services.supabase_client import get_supabase

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.errorhandler(EventRequestError)
def handle_error(error):
    return jsonify(error.to_dict()), error.status_code


@notifications_bp.get("")
def index():
    """Return a user's notifications, newest first."""
    # TODO: take the recipient from the authenticated Supabase session rather
    # than trusting a query parameter.
    raw_recipient_id = request.args.get("recipient_id")

    if raw_recipient_id is None:
        raise EventRequestError("A recipient is required to list notifications.")

    recipient_id = clean_user_id(raw_recipient_id)

    if recipient_id is None:
        raise EventRequestError("recipient_id must be a user id (a UUID).")

    unread_only = request.args.get("unread", "").lower() in {"1", "true", "yes"}

    rows = notification_service.list_for_recipient(
        get_supabase(), recipient_id, unread_only=unread_only
    )

    return jsonify({"count": len(rows), "notifications": rows})
