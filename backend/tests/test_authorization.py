import pytest
from unittest.mock import patch

from app import create_app
from app.routes import event_requests as event_request_routes
from app.services import authorization


USER_ID = "4c7fc986-1a91-48ec-99c9-b50d37a38be7"
OTHER_ID = "4bfb6e79-eab4-47a5-99a8-eab7119a56f8"


def identity(*roles, user_id=USER_ID):
    return authorization.RequestUser(
        user_id=user_id,
        token="verified-token",
        roles=frozenset(authorization.normalize_role(role) for role in roles),
    )


def test_role_names_normalize_underscores_and_american_spelling():
    assert authorization.normalize_role("event_coordinator_lead") == "event coordinator lead"
    assert authorization.normalize_role("Event Organizer") == "event organiser"


def test_only_the_named_role_passes_a_role_check(monkeypatch):
    caller = identity("Event Coordinator")
    monkeypatch.setattr(authorization, "current_user", lambda: caller)

    assert authorization.require_roles("Event Coordinator") is caller
    with pytest.raises(authorization.AuthorizationError) as error:
        authorization.require_roles("Venue Staff")
    assert error.value.status == 403


@pytest.mark.parametrize(
    "roles,assignment,allowed",
    [
        (("Event Organiser",), "event_organiser_id", True),
        (("Event Coordinator",), "event_coordinator_id", True),
        (("Event Coordinator",), "event_organiser_id", False),
        (("Event Organiser",), "event_coordinator_id", False),
        (("Venue Staff",), "venue_staff_id", False),
    ],
)
def test_event_visibility_is_limited_to_its_organiser_or_coordinator(
    monkeypatch, roles, assignment, allowed
):
    caller = identity(*roles)
    event = {
        "event_id": 17,
        "event_organiser_id": OTHER_ID,
        "event_coordinator_id": OTHER_ID,
        "venue_staff_id": USER_ID,
    }
    event[assignment] = USER_ID
    monkeypatch.setattr(authorization, "current_user", lambda: caller)
    monkeypatch.setattr(authorization, "load_event", lambda _event_id: event)

    if allowed:
        assert authorization.require_event_access(17, caller) == event
    else:
        with pytest.raises(authorization.AuthorizationError) as error:
            authorization.require_event_access(17, caller)
        assert error.value.status == 404


def test_event_request_organiser_can_only_read_their_own_request(monkeypatch):
    caller = identity("Event Organiser")
    request_row = {
        "event_request_id": 29,
        "event_organiser_id": USER_ID,
        "event_coordinator_id": OTHER_ID,
    }
    monkeypatch.setattr(authorization, "current_user", lambda: caller)
    monkeypatch.setattr(
        authorization, "load_event_request", lambda _request_id: request_row
    )

    assert authorization.require_event_request_access(29) == (caller, request_row)

    request_row["event_organiser_id"] = OTHER_ID
    with pytest.raises(authorization.AuthorizationError) as error:
        authorization.require_event_request_access(29)
    assert error.value.status == 404


def test_venue_staff_must_be_attached_to_the_event(monkeypatch):
    caller = identity("Venue Staff")
    monkeypatch.setattr(authorization, "current_user", lambda: caller)

    assert authorization.require_event_staff_access(
        {"venue_staff_id": USER_ID}, caller
    ) is caller
    with pytest.raises(authorization.AuthorizationError) as error:
        authorization.require_event_staff_access(
            {"venue_staff_id": OTHER_ID}, caller
        )
    assert error.value.status == 404


def test_event_request_creation_always_uses_the_signed_in_organiser(monkeypatch):
    caller = identity("Event Organiser")
    monkeypatch.setattr(authorization, "current_user", lambda: caller)
    created = {
        "event_request_id": 41,
        "event_organiser_id": USER_ID,
        "status": "draft",
    }

    with patch.object(event_request_routes, "create_event_request", return_value=created) as create:
        response = create_app().test_client().post(
            "/api/event-requests",
            json={
                "event_name": "Community Forum",
                "event_organiser_id": OTHER_ID,
                "save_as_draft": True,
            },
        )

    assert response.status_code == 201
    assert create.call_args.args[0]["event_organiser_id"] == USER_ID


def test_event_organiser_list_is_scoped_to_their_authenticated_id(monkeypatch):
    caller = identity("Event Organiser")
    monkeypatch.setattr(authorization, "current_user", lambda: caller)
    monkeypatch.setattr(event_request_routes, "current_user", lambda: caller)

    with patch.object(event_request_routes, "list_event_requests", return_value=[]) as listing:
        response = create_app().test_client().get(
            "/api/event-requests?event_organiser_id=" + USER_ID
        )

    assert response.status_code == 200
    listing.assert_called_once_with(USER_ID, None)


def test_event_organiser_cannot_filter_for_another_users_requests(monkeypatch):
    caller = identity("Event Organiser")
    monkeypatch.setattr(authorization, "current_user", lambda: caller)
    monkeypatch.setattr(event_request_routes, "current_user", lambda: caller)

    with patch.object(event_request_routes, "list_event_requests") as listing:
        response = create_app().test_client().get(
            "/api/event-requests?event_organiser_id=" + OTHER_ID
        )

    assert response.status_code == 403
    listing.assert_not_called()


def test_event_coordinator_list_is_scoped_to_assigned_requests_and_shown_stages(
    monkeypatch,
):
    caller = identity("Event Coordinator")
    monkeypatch.setattr(authorization, "current_user", lambda: caller)
    monkeypatch.setattr(event_request_routes, "current_user", lambda: caller)

    with patch.object(event_request_routes, "list_event_requests", return_value=[]) as listing:
        response = create_app().test_client().get("/api/event-requests")

    assert response.status_code == 200
    listing.assert_called_once_with(
        status=("submitted", "planning", "rejected"),
        event_coordinator_id=caller.user_id,
    )


def test_non_staff_cannot_create_a_venue(monkeypatch):
    caller = identity("Event Coordinator")
    monkeypatch.setattr(authorization, "current_user", lambda: caller)
    response = create_app().test_client().post("/api/venues", json={})

    assert response.status_code == 403
