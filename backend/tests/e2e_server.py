"""Run the API against the integration-test project, for the Playwright tests.

From backend/:  python -m tests.e2e_server
"""
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
TEST_ENV = BACKEND / ".env.integration-test"

# Refuse to start against dev, as the integration tests do.
test_url = dotenv_values(TEST_ENV).get("SUPABASE_URL", "")
dev_url = dotenv_values(BACKEND / ".env").get("SUPABASE_URL", "")
if not test_url or test_url.rstrip("/") == dev_url.rstrip("/"):
    raise SystemExit(f"{TEST_ENV.name} must point at the test project, not dev.")

load_dotenv(TEST_ENV, override=True)

from app import create_app  # noqa: E402

create_app().run(port=int(os.environ.get("E2E_BACKEND_PORT", "5000")))
