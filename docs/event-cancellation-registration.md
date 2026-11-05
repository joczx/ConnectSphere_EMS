# Automatic withdrawal when an event is cancelled

Apply [062_withdraw_registrations_on_event_cancellation.sql](../supabase/062_withdraw_registrations_on_event_cancellation.sql) after 061 in the target Supabase project to enable this behaviour. The migration has been tested locally; it has not been applied to a remote project by this change.

When an event enters `cancelled`, its `registered` and `waiting_list` records change to `withdrawn` with withdrawal timestamps in the same transaction. A failure rolls back cancellation and the associated changes. Already withdrawn registrations keep their original timestamps, other events are untouched, and rerunning the migration does not repeat withdrawals.

The migration also withdraws active registrations on previously cancelled events. Existing notification triggers deliver the cancellation notice before the automatic withdrawals and generate withdrawal notices. No confirmation email is sent. The attendee's existing registration view will display Withdrawn on its next fetch; manager totals no longer count those attendees as registered or waiting. The cancelled event remains hidden from the attendee catalogue.

Local SQL regression test (uses embedded PostgreSQL, no network):

```powershell
node --test frontend/tests/cancel-event-registrations-db.test.mjs
```

This test executes the production cancellation RPC, notification triggers and migration. It verifies registered/waitlisted withdrawal, timestamp preservation, unrelated records, historical repair, migration reapplication, permission refusal, repeated cancellation and atomic rollback. Verified: 1 test passed on 4 November 2026.

After applying 062 to the separate integration project:

```powershell
cd backend
$env:RUN_INTEGRATION_TESTS = '1'
python -m pytest tests/integration/test_event_cancellation_registration_integration.py -v -p no:cacheprovider
```

The live integration case additionally checks attendee registration reads, catalogue exclusion and organiser roster totals. It has been collected successfully, but not executed against a remote project because 062 has not yet been applied there.
