# Reserve equipment before accepting a request

Apply `supabase/036_reserve_before_equipment_acceptance.sql` after migration 035,
and then `supabase/037_full_equipment_acceptance.sql`, then deploy/restart the backend and refresh the frontend. The migration includes
its API schema cache reload and can be applied again safely.

1. The Event Coordinator submits an equipment request, initially Pending.
2. The assigned Technical Support Staff opens **Reserved Equipment**, selects an event and request,
   then selects the equipment model and full requested quantity. The reservation records its
   `equipment_request_id`, model, quantity and full event period. Availability
   falls immediately for overlapping dates; the request remains Pending.
3. Technical Support returns to **Equipment Requests** and selects **Accept request**.
   Partial acceptance is not supported. Acceptance changes
   the decision only; it does not create another reservation or deduct twice.

A standalone reservation is not sufficient. The decision RPC and a database
trigger require a reservation linked to this exact request, matching the event,
model, requested equipment type, accepted quantity and event period. The RPCs
check the Technical Support role and event assignment. The review queue now
shows coordinator requests for the staff member's assigned events, replacing
legacy filtering by the account that submitted the request.

A pending request can be rejected without reserving. If stock is already held,
cancel its linked reservation first. Editing or cancelling a hold on a pending
request leaves the decision Pending; it does not implicitly accept or reject it.
Existing completed decisions are retained; the migration does not backfill holds.

`equipment.total_quantity` remains the owned inventory. Available quantity is
calculated from overlapping commitments using `equipment_peak()`.

Verification:

```powershell
node frontend/tests/equipment-full-acceptance-db.test.mjs
cd backend
python -m pytest tests/test_equipment_reviews.py tests/test_equipment.py tests/test_reserve_equipment.py tests/test_equipment_reservation_management.py -q -p no:cacheprovider
```

Database tests execute the migration for both integer and legacy text event IDs,
cover missing/standalone linked reservations and rejection of partial reservations, authorisation, stock,
repeated decisions, maintenance of pending holds and attempts to bypass the RPC.
They use embedded PostgreSQL; production deployment still needs verification.
