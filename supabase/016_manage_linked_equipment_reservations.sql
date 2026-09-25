-- Apply after 015. Modify/cancel your own standalone or request-linked reservations.
begin;
-- A reservation may grow beyond the original request when stock allows.
-- Keep the original requested quantity unchanged for comparison.
alter table public.equipment_request drop constraint equipment_request_accepted_quantity_check;
alter table public.equipment_request add constraint equipment_request_accepted_quantity_check
    check (accepted_quantity >= 0);

create or replace function public.my_equipment_reservations() returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(jsonb_build_object(
        'reservation_id', r.reservation_id, 'event_id', r.event_id,
        'equipment_request_id', r.equipment_request_id,
        'event_name', e.event_name, 'equipment_id', r.equipment_id,
        'name', concat_ws(' - ', q.equipment_type, q.equipment_model),
        'quantity', r.quantity, 'starts_at', r.starts_at, 'ends_at', r.ends_at,
        'maximum_quantity', greatest(0, q.total_quantity -
            public.equipment_peak(r.equipment_id, r.starts_at, r.ends_at) + r.quantity)
    ) order by r.starts_at, r.created_at), '[]'::jsonb)
    from public.equipment_reservations r
    join public.equipment q on q.equipment_id = r.equipment_id
    join public.events e on e.event_id::text = r.event_id
    where r.created_by = auth.uid();
$$;

create or replace function public.my_equipment_request_events() returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(jsonb_build_object(
        'event_id', e.event_id::text, 'event_name', e.event_name
    ) order by e.event_name), '[]'::jsonb)
    from public.events e
    where auth.uid() is not null and (
        coalesce(to_jsonb(e)->>'created_by', to_jsonb(e)->>'event_organiser_id') = auth.uid()::text
        or exists (select 1 from public.equipment_request r
            where r.event_id = e.event_id and r.requested_by = auth.uid())
        or exists (select 1 from public.equipment_reservations r
            where r.event_id = e.event_id::text and r.created_by = auth.uid())
    );
$$;

create or replace function public.change_equipment_reservation(p_reservation_id uuid, p_quantity integer, p_cancel boolean)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
    saved public.equipment_reservations;
    linked public.equipment_request;
    stock integer;
    maximum bigint;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if p_cancel is null or (not p_cancel and (p_quantity is null or p_quantity <= 0)) then
        return jsonb_build_object('error', 'Quantity must be a positive whole number.', 'status', 400);
    end if;
    select * into saved from public.equipment_reservations
    where reservation_id = p_reservation_id and created_by = auth.uid();
    if not found then
        return jsonb_build_object('error', 'Reservation not found or access unavailable.', 'status', 404);
    end if;
    -- Match review/reserve lock order: event -> stock -> request -> reservation.
    perform 1 from public.events where event_id::text = saved.event_id for update;
    select total_quantity into stock from public.equipment
    where equipment_id = saved.equipment_id for update;
    if saved.equipment_request_id is not null then
        select * into linked from public.equipment_request
        where equipment_request_id = saved.equipment_request_id for update;
        if not found then
            return jsonb_build_object('error', 'Linked equipment request not found.', 'status', 409);
        end if;
    end if;
    select * into saved from public.equipment_reservations
    where reservation_id = p_reservation_id and created_by = auth.uid() for update;
    if not found then
        return jsonb_build_object('error', 'Reservation not found or access unavailable.', 'status', 404);
    end if;
    if p_cancel then
        if saved.equipment_request_id is not null then
            update public.equipment_request set status = 'cancelled', accepted_quantity = 0
            where equipment_request_id = saved.equipment_request_id returning * into linked;
        end if;
        -- The cancelled request must not re-enter the legacy stock calculation.
        delete from public.equipment_reservations where reservation_id = p_reservation_id;
        return jsonb_build_object('cancelled', true, 'reservation_id', p_reservation_id,
            'equipment_request', case when saved.equipment_request_id is not null then to_jsonb(linked) else null end);
    end if;
    maximum := greatest(0, stock - public.equipment_peak(saved.equipment_id, saved.starts_at, saved.ends_at) + saved.quantity);
    if p_quantity > saved.quantity and p_quantity > maximum then
        return jsonb_build_object('error', format('Insufficient equipment: you can reserve at most %s for this event.', maximum),
            'maximum_quantity', maximum, 'status', 409);
    end if;
    update public.equipment_reservations set quantity = p_quantity
    where reservation_id = p_reservation_id returning * into saved;
    if saved.equipment_request_id is not null then
        update public.equipment_request set accepted_quantity = p_quantity,
            status = case when p_quantity < quantity then 'partially_accepted' else 'accepted' end
        where equipment_request_id = saved.equipment_request_id returning * into linked;
    end if;
    return jsonb_build_object('reservation', to_jsonb(saved),
        'equipment_request', case when saved.equipment_request_id is not null then to_jsonb(linked) else null end);
end;
$$;

notify pgrst, 'reload schema';
commit;
