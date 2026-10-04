"""Tests for request-scoped Supabase authentication used by RLS."""

from unittest.mock import patch

from flask import Flask

from app.services.supabase_client import get_supabase


def test_authenticated_client_carries_bearer_token_and_is_reused_per_request():
    app = Flask(__name__)
    first_client = object()
    second_client = object()

    with patch.dict(
        "os.environ",
        {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_ANON_KEY": "anon-key"},
    ), patch(
        "app.services.supabase_client.create_client",
        side_effect=[first_client, second_client],
    ) as create:
        with app.test_request_context(headers={"Authorization": "Bearer first-token"}):
            assert get_supabase() is first_client
            assert get_supabase() is first_client

        with app.test_request_context(headers={"Authorization": "Bearer second-token"}):
            assert get_supabase() is second_client

    assert create.call_count == 2
    assert create.call_args_list[0].args[2].headers["Authorization"] == "Bearer first-token"
    assert create.call_args_list[1].args[2].headers["Authorization"] == "Bearer second-token"


def test_client_without_bearer_token_uses_the_anonymous_key():
    app = Flask(__name__)
    anonymous_client = object()

    with patch.dict(
        "os.environ",
        {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_ANON_KEY": "anon-key"},
    ), patch(
        "app.services.supabase_client._anonymous_client", None
    ), patch(
        "app.services.supabase_client.create_client", return_value=anonymous_client
    ) as create, app.test_request_context():
        assert get_supabase() is anonymous_client

    create.assert_called_once_with("https://example.supabase.co", "anon-key")
