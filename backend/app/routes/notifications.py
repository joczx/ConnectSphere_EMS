"""The signed-in user's in-app notifications (046_notification_service.sql).

Notifications are created by the database when something happens; this only
lists them and marks one read. Each call uses the caller's own token, and the
database functions only ever return or change the caller's notifications.
"""

from flask import Blueprint, jsonify, request

from app.services.event_store import StoreError, authenticated_token, supabase_request

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

PAGE_SIZE = 20   # full notifications page
PAGE_DAYS = 14   # how far back the full page goes


@notifications_bp.after_request
def prevent_caching(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@notifications_bp.errorhandler(StoreError)
def handle_store_error(error):
    return jsonify(error.to_dict()), error.status


def _whole_number(name, default):
    value = request.args.get(name, str(default))
    return int(value) if value.isdecimal() and int(value) > 0 else None


@notifications_bp.get("")
def index():
    """`?limit=N` for the newest N (the bell popup); `?page=N` for the full page."""
    token = authenticated_token()
    popup = "limit" in request.args
    number = _whole_number("limit" if popup else "page", 10 if popup else 1)
    if number is None:
        return jsonify(error="Use a positive whole number."), 400
    payload = ({"p_limit": number, "p_offset": 0, "p_days": None} if popup
               else {"p_limit": PAGE_SIZE, "p_offset": (number - 1) * PAGE_SIZE, "p_days": PAGE_DAYS})
    result = supabase_request("/rest/v1/rpc/list_my_notifications", token=token, payload=payload)
    if result.get("error"):
        return jsonify(error=result["error"]), result.get("status", 400)
    return jsonify(**result, page_size=PAGE_SIZE)


@notifications_bp.post("/<int:notification_id>/read")
def mark_read(notification_id):
    token = authenticated_token()
    result = supabase_request("/rest/v1/rpc/mark_notification_read", token=token,
                              payload={"p_notification_id": notification_id})
    if result.get("error"):
        return jsonify(error=result["error"]), result.get("status", 400)
    return jsonify(result)
