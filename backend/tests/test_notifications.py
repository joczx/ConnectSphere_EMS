from unittest.mock import patch

from app import create_app


def test_notifications_are_loaded_for_the_authenticated_user_not_query_parameter():
    client = create_app().test_client()
    client_id = "8c2d7e15-4b93-4a06-8f21-6e0b3d9a7c54"
    notifications = [{"notification_id": 1, "message": "An event request was assigned to you."}]

    with (
        patch("app.routes.notifications.authenticated_user", return_value=("token", client_id)),
        patch("app.routes.notifications.get_supabase", return_value="client"),
        patch(
            "app.routes.notifications.notification_service.list_for_recipient",
            return_value=notifications,
        ) as list_for_recipient,
    ):
        response = client.get(
            "/api/notifications?recipient_id=9c2d7e15-4b93-4a06-8f21-6e0b3d9a7c54&unread=1"
        )

    assert response.status_code == 200
    assert response.json["notifications"] == notifications
    assert response.headers["Cache-Control"] == "no-store"
    list_for_recipient.assert_called_once_with("client", client_id, unread_only=True)
