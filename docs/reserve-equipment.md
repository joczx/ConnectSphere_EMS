# Reserve Equipment

The Equipment page contains a direct reservation form. Assigned Technical
Support Staff select an event, equipment model and positive whole quantity.
Availability uses the event dates and the same `equipment_peak` calculation as
Check Equipment Availability. Reservations affect stock only during their
half-open time windows: an event ending at another event's start does not overlap.

The POST RPC locks the event and equipment stock row, rechecks available stock
and records the reservation in one transaction. A stale preview cannot bypass
this check. Existing accepted equipment requests are included; linked requests
are counted once. Insufficient stock returns a displayable 409 error and creates
no reservation. Non-overlapping events reuse the stock.

One direct reservation per event/model is allowed. Users change its quantity in
the existing reservation-management UI. Request-linked reservations remain
separate. Assignment in `events.technical_support_id` is the authorization rule;
an Organiser who is not assigned technical support cannot create a direct
reservation after this migration. Request-review workflows are unchanged.

## Deployment

Apply `supabase/022_reserve_available_equipment.sql` after the equipment migrations
010 through 016, before deploying the application. It enables the assigned-event
RPC and updates reservation/availability functions. No production Supabase
database is changed by editing this repository.

## AC tests

From `backend`:

```powershell
python -m pytest tests/test_reserve_equipment.py tests/test_equipment.py tests/test_equipment_availability.py tests/test_equipment_reservation_management.py -q -p no:cacheprovider
```

For real PostgreSQL assertions, from the repository root with Docker running:

```powershell
python backend/tests/run_reserve_equipment_database_checks.py
```

The runner starts an isolated disposable container and removes only that
container. It tests event assignment, quantity validation, recording against
events, rejection without writes, overlapping/adjacent/non-overlapping periods,
shared preview calculations, simultaneous reservations and linked-request stock.
It never connects to the configured Supabase database.

Browser check: sign in as assigned staff; select an event/model; verify preview,
reserve available quantity and check confirmation plus reservation list. Try
exceeding stock, stale availability, and a nonassigned account. Verify successful
reservation refreshes available stock and failed submissions retain selections.
