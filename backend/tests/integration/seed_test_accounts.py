"""Create the integration-test accounts and roles after `supabase db reset --linked`.

Migrations restore the schema but not its data, so a reset removes every account
and role. This reads the emails and passwords from backend/.env.integration-test
and is safe to run again: anything already in place is left as it is, except
that each password is set to the one in the file.

From backend/:  python tests/integration/seed_test_accounts.py
"""

import sys
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

BACKEND = Path(__file__).resolve().parents[2]
INTEGRATION_ENV = BACKEND / ".env.integration-test"
ROLES = (
    "Event Organiser",
    "Event Coordinator Lead",
    "Event Coordinator",
    "Venue Staff",
    "Technical Support Staff",
    "Safety Officer",
    "Attendee",
)


def _load_integration_env():
    if not INTEGRATION_ENV.exists():
        sys.exit(f"{INTEGRATION_ENV} not found.")

    values = dotenv_values(INTEGRATION_ENV)
    url = values.get("SUPABASE_URL")
    if not url or not values.get("SUPABASE_SERVICE_ROLE_KEY"):
        sys.exit(f"Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in {INTEGRATION_ENV.name}.")

    dev_url = dotenv_values(BACKEND / ".env").get("SUPABASE_URL")
    if dev_url and dev_url.rstrip("/") == url.rstrip("/"):
        sys.exit("This file is pointed at the dev project. Refusing to run.")

    load_dotenv(INTEGRATION_ENV, override=True)
    return values


def _ensure_account(existing, email, password, admin_request):
    user_id = existing.get(email.lower())
    if user_id:
        admin_request(f"/auth/v1/admin/users/{user_id}", {"password": password}, method="PUT")
        return user_id
    return admin_request(
        "/auth/v1/admin/users", {"email": email, "password": password, "email_confirm": True}
    )["id"]


def _ensure_role(role, admin_request):
    rows = admin_request("/rest/v1/roles?select=role_id,role_name")
    for row in rows:
        if row["role_name"] == role:
            return row["role_id"]
    return admin_request("/rest/v1/roles", {"role_name": role})[0]["role_id"]


def _ensure_membership(user_id, role_id, admin_request):
    path = f"/rest/v1/user_roles?select=user_id&user_id=eq.{user_id}&role_id=eq.{role_id}"
    if not admin_request(path):
        admin_request("/rest/v1/user_roles", {"user_id": user_id, "role_id": role_id})


def main():
    values = _load_integration_env()

    # Imported here because it reads the environment loaded above when called.
    from supabase_admin import admin_request

    users = admin_request("/auth/v1/admin/users?per_page=1000")["users"]
    existing = {user["email"].lower(): user["id"] for user in users if user.get("email")}

    for role in ROLES:
        prefix = "INTEGRATION_" + role.upper().replace(" ", "_")
        email = values.get(f"{prefix}_EMAIL")
        password = values.get(f"{prefix}_PASSWORD")
        if not email or not password:
            print(f"Skipped {role}: {prefix}_EMAIL/PASSWORD not set.")
            continue
        user_id = _ensure_account(existing, email, password, admin_request)
        _ensure_membership(user_id, _ensure_role(role, admin_request), admin_request)
        print(f"Ready: {role}")


if __name__ == "__main__":
    main()
