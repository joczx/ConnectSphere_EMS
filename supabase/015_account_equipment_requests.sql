-- Apply after 013; 014 is optional and fully superseded by this migration.
-- Account ownership only; no role or staff-assignment checks.
begin;
create or replace function public.equipment_request_review_queue() returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(to_jsonb(r) || jsonb_build_object(
        'event_name', e.event_name) order by e.event_name, r.requested_at), '[]'::jsonb)
    from public.equipment_request r join public.events e on e.event_id = r.event_id
    where r.requested_by = auth.uid();
$$;

-- Include owned events even without requests, plus events containing this
-- account's requests. Other accounts' requests are never returned in the queue.
create function public.my_equipment_request_events() returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(jsonb_build_object(
        'event_id', e.event_id::text, 'event_name', e.event_name
    ) order by e.event_name), '[]'::jsonb)
    from public.events e
    where auth.uid() is not null and (
        coalesce(to_jsonb(e)->>'created_by', to_jsonb(e)->>'event_organiser_id') = auth.uid()::text
        or exists (select 1 from public.equipment_request r
            where r.event_id = e.event_id and r.requested_by = auth.uid())
    );
$$;
revoke all on function public.my_equipment_request_events() from public, anon;
grant execute on function public.my_equipment_request_events() to authenticated;

create or replace function public.review_equipment_request(
    p_request_id integer, p_outcome text, p_equipment_id integer,
    p_accepted_quantity integer, p_reason text
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    saved public.equipment_request;
    ev jsonb;
    item public.equipment;
    starts timestamptz;
    ends timestamptz;
    amount integer;
    available bigint;
    reservation public.equipment_reservations;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if p_outcome is null or p_outcome not in ('accepted', 'rejected', 'partially_accepted') then
        return jsonb_build_object('error', 'Choose a valid review outcome.', 'status', 400);
    end if;
    select * into saved from public.equipment_request where equipment_request_id = p_request_id;
    if not found then return jsonb_build_object('error', 'Request not found.', 'status', 404); end if;
    -- Match the reservation functions' event -> stock -> request lock order.
    select to_jsonb(e) into ev from public.events e where e.event_id = saved.event_id for update;
    if ev is null then
        return jsonb_build_object('error', 'Event not found.', 'status', 404);
    end if;
    if p_outcome <> 'rejected' then
        select * into item from public.equipment where equipment_id = p_equipment_id for update;
        if not found then return jsonb_build_object('error', 'Select equipment to reserve.', 'status', 400); end if;
    end if;
    select * into saved from public.equipment_request where equipment_request_id = p_request_id for update;
    if not found then return jsonb_build_object('error', 'Request not found.', 'status', 404); end if;
    if saved.requested_by is distinct from auth.uid() then
        return jsonb_build_object('error', 'You can only review equipment requests submitted by your account.', 'status', 403);
    end if;
    if saved.event_id::text <> (ev->>'event_id') or saved.status <> 'pending' then
        return jsonb_build_object('error', 'This request has changed or already been reviewed. Refresh the page.', 'status', 409);
    end if;
    if p_outcome = 'rejected' then
        if nullif(btrim(p_reason), '') is null then
            return jsonb_build_object('error', 'Enter a reason for rejection.', 'status', 400);
        end if;
        amount := 0;
    else
        if lower(btrim(item.equipment_type)) <> lower(btrim(saved.equipment_type)) then
            return jsonb_build_object('error', 'Select equipment matching the requested type.', 'status', 400);
        end if;
        amount := case when p_outcome = 'accepted' then saved.quantity else p_accepted_quantity end;
        if amount is null or amount < 1 or (p_outcome = 'partially_accepted' and amount >= saved.quantity) then
            return jsonb_build_object('error', 'Partial acceptance must be greater than zero and less than the requested quantity.', 'status', 400);
        end if;
        starts := coalesce(ev->>'start_datetime', ev->>'starts_at')::timestamptz;
        ends := coalesce(ev->>'end_datetime', ev->>'ends_at')::timestamptz;
        if starts is null or ends is null or ends <= starts then
            return jsonb_build_object('error', 'Set valid event dates before reserving equipment.', 'status', 400);
        end if;
        available := greatest(0, item.total_quantity - public.equipment_peak(item.equipment_id, starts, ends));
        if amount > available then
            return jsonb_build_object('error', format('Only %s available. Reduce the accepted quantity or reject the request.', available), 'status', 409);
        end if;
    end if;
    update public.equipment_request set status = p_outcome, accepted_quantity = amount,
        equipment_id = case when p_outcome = 'rejected' then null else p_equipment_id end,
        reviewed_by = auth.uid(), reviewed_at = now(),
        reason_for_rejection = case when p_outcome = 'rejected' then btrim(p_reason) else null end
    where equipment_request_id = p_request_id returning * into saved;
    if amount > 0 then
        insert into public.equipment_reservations (
            event_id, equipment_id, equipment_request_id, quantity, starts_at, ends_at, created_by
        ) values (saved.event_id::text, p_equipment_id, p_request_id, amount, starts, ends, auth.uid())
        returning * into reservation;
    end if;
    return jsonb_build_object('equipment_request', to_jsonb(saved),
        'reservation', case when amount > 0 then to_jsonb(reservation) else null end,
        'message', case when amount > 0 then 'Equipment reserved and event request updated successfully.'
                       else 'Equipment request rejected.' end);
end;
$$;

create or replace function public.reserve_equipment(p_event_id text, p_equipment_id integer, p_quantity integer)
returns jsonb language plpgsql security definer set search_path = public as $$
declare ev jsonb; s timestamptz; f timestamptz; stock integer; available bigint; saved public.equipment_reservations;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.'); end if;
    if p_quantity is null or p_quantity <= 0 then
        return jsonb_build_object('error', 'Quantity must be a positive whole number.');
    end if;
    -- Lock the event to prevent date edits/deletion during this transaction.
    select to_jsonb(e) into ev from public.events e where e.event_id::text = p_event_id for update;
    if ev is null then return jsonb_build_object('error', 'Event not found.'); end if;
    if coalesce(ev->>'created_by', ev->>'event_organiser_id') is distinct from auth.uid()::text
       and not exists (select 1 from public.equipment_request r
           where r.event_id::text = p_event_id and r.requested_by = auth.uid()) then
        return jsonb_build_object('error', 'This event does not belong to your account.', 'status', 403);
    end if;
    s := coalesce(ev->>'start_datetime', ev->>'starts_at')::timestamptz;
    f := coalesce(ev->>'end_datetime', ev->>'ends_at')::timestamptz;
    if s is null or f is null or f <= s then
        return jsonb_build_object('error', 'Set a valid event start and end time before reserving equipment.');
    end if;
    -- Every reservation for this stock item must acquire the same row lock.
    select total_quantity into stock from public.equipment where equipment_id = p_equipment_id for update;
    if not found then return jsonb_build_object('error', 'Equipment not found.'); end if;
    if exists (select 1 from public.equipment_reservations where event_id = p_event_id and equipment_id = p_equipment_id) then
        return jsonb_build_object('error', 'This equipment is already reserved for this event.');
    end if;
    available := greatest(0, stock - public.equipment_peak(p_equipment_id, s, f));
    if p_quantity > available then
        return jsonb_build_object('error', format('Insufficient equipment: only %s available for this event.', available), 'available_quantity', available);
    end if;
    insert into public.equipment_reservations(event_id, equipment_id, quantity, starts_at, ends_at, created_by)
    values (p_event_id, p_equipment_id, p_quantity, s, f, auth.uid()) returning * into saved;
    return jsonb_build_object('reservation', to_jsonb(saved));
end;
$$;


notify pgrst, 'reload schema';
commit;
