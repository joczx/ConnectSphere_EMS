"""The notification service's API (046_notification_service.sql). Supabase is mocked."""
from unittest.mock import patch

import pytest

from app import create_app

RESULT = {"items": [{"notification_id": 1, "title": "New event request"}], "total": 1, "unread": 1}


def call(path, method="get", result=None):
    with patch("app.routes.notifications.authenticated_token", return_value="user-token"), patch(
        "app.routes.notifications.supabase_request", return_value=RESULT if result is None else result
    ) as query:
        return getattr(create_app().test_client(), method)(path), query


def test_the_popup_asks_for_the_newest_notifications_of_any_age():
    response, query = call("/api/notifications?limit=10")
    assert response.status_code == 200
    assert response.json["items"] == RESULT["items"] and response.json["unread"] == 1
    assert query.call_args.args[0] == "/rest/v1/rpc/list_my_notifications"
    assert query.call_args.kwargs["payload"] == {"p_limit": 10, "p_offset": 0, "p_days": None}
    assert query.call_args.kwargs["token"] == "user-token"
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("page,offset", [(None, 0), ("1", 0), ("3", 40)])
def test_the_full_page_lists_20_per_page_from_the_last_14_days(page, offset):
    response, query = call("/api/notifications" + (f"?page={page}" if page else ""))
    assert query.call_args.kwargs["payload"] == {"p_limit": 20, "p_offset": offset, "p_days": 14}
    assert response.json["page_size"] == 20


@pytest.mark.parametrize("path", ["/api/notifications?page=0", "/api/notifications?page=x", "/api/notifications?limit=-1"])
def test_invalid_paging_never_reaches_the_database(path):
    response, query = call(path)
    assert response.status_code == 400
    query.assert_not_called()


def test_a_notification_is_marked_read_by_id():
    response, query = call("/api/notifications/7/read", "post", {"notification_id": 7})
    assert response.status_code == 200
    assert query.call_args.args[0] == "/rest/v1/rpc/mark_notification_read"
    assert query.call_args.kwargs["payload"] == {"p_notification_id": 7}


def test_someone_elses_notification_is_not_found():
    response, _ = call("/api/notifications/7/read", "post", {"error": "Notification not found.", "status": 404})
    assert response.status_code == 404


def test_sign_in_is_required():
    assert create_app().test_client().get("/api/notifications?limit=10").status_code == 401
