"""In-app notifications.

Deliberately small. The full Notification System is its own user story; this
module covers what "the Event Organiser should be notified of the outcome"
needs, and gives that later story a table to build on.
"""

NOTIFICATION_TABLE = "notification"


def build(recipient_id, event_request_id, notification_type, message):
    """Shape one notification row. One row per recipient."""
    return {
        "recipient_id": recipient_id,
        "event_request_id": event_request_id,
        "notification_type": notification_type,
        "message": message,
    }


def deliver(client, notifications):
    """Write notifications, returning the rows that were stored.

    A failure here must not undo a decision the Coordinator already made, so
    the caller is expected to treat the result as best effort.
    """
    if not notifications:
        return []

    response = client.table(NOTIFICATION_TABLE).insert(notifications).execute()

    return response.data or []


def list_for_recipient(client, recipient_id, unread_only=False):
    """Return a recipient's notifications, newest first."""
    query = (
        client.table(NOTIFICATION_TABLE)
        .select("*")
        .eq("recipient_id", recipient_id)
    )

    if unread_only:
        query = query.eq("is_read", False)

    return query.order("created_at", desc=True).execute().data or []
