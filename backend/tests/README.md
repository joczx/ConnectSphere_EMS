# Automated event checks

From the repository root:

```powershell
cd backend
python -m unittest discover -s tests -v
```

Run just the 50 new cases:

```powershell
python -m unittest discover -s tests -p test_event_acceptance.py -v
```

No extra test packages, database writes, network access, or real credentials are needed.

## Coverage

- 01-16: authentication for list and direct detail requests.
- 17-24: write methods rejected by viewing endpoints.
- 25-34: authorised responses, empty/unavailable events, fresh reads, removal of access, null values, Unicode/markup JSON, malformed IDs and service errors.
- 35-50: Supabase transport errors, configuration, network timeout, invalid JSON, user-token forwarding and read-only HTTP requests.

These are 50 backend regression tests, not a one-to-one automation of the earlier 50 manual UI cases. The original eight tests remain separate.

## Limits and remaining acceptance work

Supabase calls are mocked. A mocked empty result verifies the API response to RLS filtering; it does NOT prove the deployed RLS policies enforce user isolation. Verify those separately using two real accounts with different event assignments. No service-role key should be used for that check.

Browser rendering, keyboard/screen-reader access, mobile layout, session navigation, manual/60-second/focus refresh, safe HTML rendering, and loading/retry UI still require browser tests. JSON preservation alone does not prove safe rendering.

Purpose, description, attendance, venue/accessibility/equipment requirements and registration needs are absent from the current event UI/schema described by the user. Their display acceptance criteria are not covered or satisfied by these tests.

The current client maps upstream HTTP 400 and 403 to 401. Tests record that existing contract; schema/configuration errors can therefore appear as authentication errors. Passing this suite does not establish full AC compliance.
