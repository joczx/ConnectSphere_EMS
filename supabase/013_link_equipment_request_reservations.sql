-- Apply after 012_review_equipment_requests.sql.
-- New acceptances create one reservation per request, in the same transaction.
-- Existing accepted requests still count as legacy commitments until linked.
begin;
alter table public.equipment_reservations
    add column equipment_request_id integer unique references public.equipment_request(equipment_request_id);

-- Multiple requests for the same model/event each retain their own reservation.
-- Preserve the existing uniqueness rule for standalone reservations.
alter table public.equipment_reservations
    drop constraint equipment_reservations_event_id_equipment_id_key;
create unique index equipment_reservations_standalone_event_equipment
    on public.equipment_reservations(event_id, equipment_id)
    where equipment_request_id is null;

create or replace function public.equipment_peak(p_equipment_id integer, p_start timestamptz, p_end timestamptz)
returns bigint language sql stable set search_path = public as $$
    with commitments as (
        select equipment_id, quantity, starts_at, ends_at from public.equipment_reservations
        union all
        select r.equipment_id, coalesce(r.accepted_quantity, r.quantity),
            coalesce(to_jsonb(e)->>'start_datetime', to_jsonb(e)->>'starts_at')::timestamptz,
            coalesce(to_jsonb(e)->>'end_datetime', to_jsonb(e)->>'ends_at')::timestamptz
        from public.equipment_request r join public.events e on e.event_id = r.event_id
        where r.status in ('accepted', 'in_progress', 'partially_accepted', 'completed')
          and not exists (select 1 from public.equipment_reservations booked
              where booked.equipment_request_id = r.equipment_request_id)
    ), changes as (
        select greatest(starts_at, p_start) as moment, quantity::bigint as delta
        from commitments
        where equipment_id = p_equipment_id and starts_at < p_end and ends_at > p_start
        union all
        select least(ends_at, p_end), -quantity::bigint
        from commitments
        where equipment_id = p_equipment_id and starts_at < p_end and ends_at > p_start
    ), usage as (
        select sum(sum(delta)) over (order by moment) as used from changes group by moment
    ) select coalesce(max(used), 0)::bigint from usage;
$$;


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
    if ev is null or (ev->>'technical_support_id') is distinct from auth.uid()::text then
        return jsonb_build_object('error', 'Only the assigned technical support staff can review this request.', 'status', 403);
    end if;
    if p_outcome <> 'rejected' then
        select * into item from public.equipment where equipment_id = p_equipment_id for update;
        if not found then return jsonb_build_object('error', 'Select equipment to reserve.', 'status', 400); end if;
    end if;
    select * into saved from public.equipment_request where equipment_request_id = p_request_id for update;
    if not found then return jsonb_build_object('error', 'Request not found.', 'status', 404); end if;
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

create or replace function public.change_equipment_reservation(p_reservation_id uuid, p_quantity integer, p_cancel boolean)
returns jsonb language plpgsql security definer set search_path = public as $$
declare saved public.equipment_reservations; stock integer; maximum bigint;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not p_cancel and (p_quantity is null or p_quantity <= 0) then
        return jsonb_build_object('error', 'Quantity must be a positive whole number.', 'status', 400);
    end if;
    select * into saved from public.equipment_reservations
    where reservation_id = p_reservation_id and created_by = auth.uid();
    if not found then
        return jsonb_build_object('error', 'Reservation not found or access unavailable.', 'status', 404);
    end if;
    perform 1 from public.events where event_id::text = saved.event_id for update;
    select total_quantity into stock from public.equipment
    where equipment_id = saved.equipment_id for update;
    select * into saved from public.equipment_reservations
    where reservation_id = p_reservation_id and created_by = auth.uid() for update;
    if not found then
        return jsonb_build_object('error', 'Reservation not found or access unavailable.', 'status', 404);
    end if;
    if saved.equipment_request_id is not null then
        return jsonb_build_object('error', 'This reservation belongs to a reviewed equipment request and cannot be changed independently.', 'status', 409);
    end if;
    if p_cancel then
        delete from public.equipment_reservations where reservation_id = p_reservation_id;
        return jsonb_build_object('cancelled', true, 'reservation_id', p_reservation_id);
    end if;
    -- This reservation occupies its entire window, so add its current quantity
    -- back when calculating the maximum replacement quantity.
    maximum := greatest(0, stock - public.equipment_peak(saved.equipment_id, saved.starts_at, saved.ends_at) + saved.quantity);
    if p_quantity > saved.quantity and p_quantity > maximum then
        return jsonb_build_object('error', format('Insufficient equipment: you can reserve at most %s for this event.', maximum),
            'maximum_quantity', maximum, 'status', 409);
    end if;
    update public.equipment_reservations set quantity = p_quantity
    where reservation_id = p_reservation_id returning * into saved;
    return jsonb_build_object('reservation', to_jsonb(saved));
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
    if (ev->>'technical_support_id') is distinct from auth.uid()::text then
        return jsonb_build_object('error', 'Only the assigned technical support staff can reserve equipment for this event.', 'status', 403);
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


create or replace function public.equipment_availability(p_event_id text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare ev jsonb; s timestamptz; f timestamptz; items jsonb;
begin
    select to_jsonb(e) into ev from public.events e where e.event_id::text = p_event_id;
    if ev is null then return jsonb_build_object('error', 'Event not found.'); end if;
    s := coalesce(ev->>'start_datetime', ev->>'starts_at')::timestamptz;
    f := coalesce(ev->>'end_datetime', ev->>'ends_at')::timestamptz;
    if s is null or f is null or f <= s then
        return jsonb_build_object('error', 'Set a valid event start and end time before reserving equipment.');
    end if;
    select coalesce(jsonb_agg(jsonb_build_object(
        'equipment_id', q.equipment_id, 'name', concat_ws(' - ', q.equipment_type, q.equipment_model), 'total_quantity', q.total_quantity,
        'available_quantity', greatest(0, q.total_quantity - public.equipment_peak(q.equipment_id, s, f)),
        'reserved_quantity', coalesce(r.quantity, 0)
    ) order by q.equipment_type, q.equipment_model), '[]'::jsonb) into items
    from public.equipment q left join (
        select equipment_id, sum(quantity) as quantity from public.equipment_reservations
        where event_id = p_event_id group by equipment_id
    ) r on r.equipment_id = q.equipment_id;
    return jsonb_build_object('equipment', items, 'starts_at', s, 'ends_at', f);
end;
$$;

notify pgrst, 'reload schema';
commit;
