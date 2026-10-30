"""Point the backend at the integration-test Supabase project.

backend/.env.integration-test must be loaded before `app` is imported, because
app/__init__.py loads backend/.env and would otherwise fill any gap with the
dev project's credentials. Every required value must therefore come from the
integration file itself, and the run refuses to start if it names the same
project as backend/.env.
"""

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values, load_dotenv

BACKEND = Path(__file__).resolve().parents[2]
INTEGRATION_ENV = BACKEND / ".env.integration-test"
REQUIRED = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY")
ROLES = (
    "EVENT_ORGANISER",
    "EVENT_COORDINATOR_LEAD",
    "EVENT_COORDINATOR",
    "VENUE_STAFF",
    "TECHNICAL_SUPPORT_STAFF",
    "SAFETY_OFFICER",
    "ATTENDEE",
)


def _load_integration_env():
    if not INTEGRATION_ENV.exists():
        pytest.exit(f"{INTEGRATION_ENV} not found.", returncode=2)

    values = dotenv_values(INTEGRATION_ENV)
    missing = [name for name in REQUIRED if not values.get(name)]
    if missing:
        pytest.exit(f"Set {', '.join(missing)} in {INTEGRATION_ENV.name}.", returncode=2)

    dev_url = dotenv_values(BACKEND / ".env").get("SUPABASE_URL")
    if dev_url and dev_url.rstrip("/") == values["SUPABASE_URL"].rstrip("/"):
        pytest.exit("Integration tests are pointed at the dev project. Refusing to run.", returncode=2)

    load_dotenv(INTEGRATION_ENV, override=True)


_load_integration_env()

from app import create_app  # noqa: E402
from app.services import supabase_client  # noqa: E402
from app.services.event_store import supabase_request  # noqa: E402

# Drop any anon client cached from the dev credentials.
supabase_client._anonymous_client = None


@pytest.fixture(scope="session")
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture(scope="session")
def sign_in():
    """Return a function giving `role`'s auth header, signing in once per role.

    `role` is the role's display name, e.g. sign_in("Event Coordinator Lead").
    """
    tokens = {}

    def _sign_in(role):
        role = role.strip().upper().replace(" ", "_")
        if role not in ROLES:
            raise ValueError(f"Unknown role {role!r}; expected one of {ROLES}.")
        if role not in tokens:
            email = os.environ.get(f"INTEGRATION_{role}_EMAIL")
            password = os.environ.get(f"INTEGRATION_{role}_PASSWORD")
            if not email or not password:
                pytest.skip(f"INTEGRATION_{role}_EMAIL/PASSWORD not set.")
            session = supabase_request(
                "/auth/v1/token?grant_type=password",
                payload={"email": email, "password": password},
                method="POST",
            )
            tokens[role] = session["access_token"]
        return {"Authorization": f"Bearer {tokens[role]}"}

    return _sign_in
