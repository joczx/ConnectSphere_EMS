# Reserve equipment

All signed-in users can open **Reserve Equipment** from Home. There are no role
or event-membership restrictions on this feature. Existing sign-in is retained.

## Setup

1. Apply `supabase/010_equipment_reservations_existing_catalogue.sql` once in the Supabase SQL Editor.
   Use this instead of the legacy `005_equipment_reservations.sql`, which creates an incompatible UUID catalogue.
   It preserves the existing integer-ID `equipment` table and requires `equipment_request` and `public.events` and supports either
   `start_datetime` / `end_datetime` or `starts_at` / `ends_at` columns.
2. Add your actual inventory in the SQL Editor, for example:

   ```sql
   insert into public.equipment (equipment_type, equipment_model, total_quantity)
   values ('Projector', 'PX-500', 5), ('Microphone', 'M-100', 10), ('Speaker', 'S-200', 4);
   ```

3. Configure `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `backend/.env`.
4. Start the backend (`python run.py` inside `backend`) and frontend
   (`npm run dev` inside `frontend`). Sign in and open **Reserve Equipment**.
5. Choose an event with valid start/end times, equipment and quantity, then confirm.

## Behaviour

- Stock is reserved for the entire event duration. The end time is exclusive:
  equipment from an event ending at 10:00 can be used by one starting at 10:00.
- Availability is total stock minus the highest concurrent reservation quantity
  during the selected event. Non-overlapping reservations do not reduce it.
- The database locks the inventory row, rechecks availability and records the
  reservation in one transaction. Direct client writes are not permitted.
- One reservation per event/equipment pair prevents repeated submissions from
  silently deducting stock again. Reserve different equipment separately.
- Saved quantities appear in the availability table. Refresh retrieves current
  stock; confirmation always rechecks it even if the displayed count is stale.
- Events with reservations cannot change ID or dates. Deleting an event removes
  its reservations. The creator can cancel reservations in My equipment reservations before rescheduling an event.
- Inventory management is performed in Supabase. Do not lower stock below
  existing commitments. Cancellation status does not automatically release stock.

## Verification

Run `python -m pytest tests -q` inside `backend` and `npm run build` inside
`frontend`. `backend/tests/equipment_overlap.sql` exercises the real overlap
calculation in a test Supabase database and rolls back its fixtures.

For a disposable local integration run (requires Docker and the `postgres:13` image),
run these commands from the repository root:

```powershell
docker run --name connectsphere-equipment-test --detach --rm -e POSTGRES_PASSWORD=equipment-test-local postgres:13
python backend/tests/run_equipment_database_checks.py
docker stop connectsphere-equipment-test
```

The script requires an empty container. It checks the migration, peak overlap,
exact-stock reservations, insufficient-stock rejection, duplicate submission,
adjacent reuse, access without membership, date protection, deletion cleanup,
concurrent requests, both date column conventions, and direct-write protection.

For integration acceptance, reserve the last available units for two overlapping
events concurrently: exactly one should succeed and the other should report
insufficient equipment. Also check exact-stock success, over-stock rejection,
non-overlapping reuse, missing event dates, and access with ordinary user accounts.

## Loading failure diagnosis

The deployed database was reachable during read-only checks, but lacked
`equipment_reservations` and `equipment_events`. Its catalogue has integer IDs,
`equipment_type` and `equipment_model`, not the legacy UUID IDs and `name`.
Missing Flask reservation routes produced HTML 404 responses and the frontend's
JSON parser reported `Unexpected token '<'`.

The event picker now reads the existing events table directly. Apply migration
010 through the Supabase SQL Editor to enable availability and reservations;
the public anon/publishable key cannot apply database migrations. Restart Flask
and refresh the frontend afterwards. Both availability screens share the database
peak calculation, including committed equipment requests and reservations.
Pending equipment requests do not consume stock.

Administrative changes to accepted requests or total inventory must also respect
existing stock commitments; this feature only serializes reservation confirmations.

## Modify or cancel your reservations

After migration 010, apply `supabase/011_manage_equipment_reservations.sql` once
in the Supabase SQL Editor. It preserves existing reservations.

Open **Reserve Equipment ? My equipment reservations** to see reservations you
created across all events. Change the quantity and choose **Save quantity**, or
choose **Cancel reservation ? Confirm cancellation**. Cancellation removes the
reservation; it can be booked again later. There is no cancellation history.

The database checks ownership using the authenticated user's ID, including direct
RPC calls. It serializes updates/cancellations with new reservations using the same
event and stock locks. Increases account for the existing quantity, reductions
release only the difference, and cancellation releases the entire quantity. Both
availability screens use the updated allocation. Role restrictions remain unchanged:
all signed-in users can reserve, and only the creator can manage a reservation.

Endpoints: `GET /api/equipment/reservations`,
`PATCH /api/equipment/reservations/<id>` with `{"quantity": 3}`,
and `DELETE /api/equipment/reservations/<id>`.
