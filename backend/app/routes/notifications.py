"""Minimal read access to in-app notifications.

Enough for a user to see an outcome they were notified about. Marking as read,
preferences and delivery channels belong to the Notification System story.
"""

from flask import Blueprint, jsonify, request

from app.services import notification_service
from app.services.event_request_service import EventRequestError
from app.services.event_store import StoreError, authenticated_user
from app.services.supabase_client import get_supabase

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.after_request
def prevent_caching(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@notifications_bp.errorhandler(EventRequestError)
def handle_error(error):
    return jsonify(error.to_dict()), error.status_code


@notifications_bp.errorhandler(StoreError)
def handle_store_error(error):
    return jsonify(error.to_dict()), error.status


@notifications_bp.get("")
def index():
    """Return the signed-in user's notifications, newest first."""
    _, recipient_id = authenticated_user()

    unread_only = request.args.get("unread", "").lower() in {"1", "true", "yes"}

    rows = notification_service.list_for_recipient(
        get_supabase(), recipient_id, unread_only=unread_only
    )

    return jsonify({"count": len(rows), "notifications": rows})
