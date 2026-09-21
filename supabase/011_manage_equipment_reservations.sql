-- Apply after 010. Existing reservations and stock are preserved.
begin;

create function public.my_equipment_reservations() returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(jsonb_build_object(
        'reservation_id', r.reservation_id, 'event_id', r.event_id,
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

-- Shared mutation implementation. Follow creation's event -> stock -> reservation
-- lock order; re-read ownership after acquiring locks to handle concurrent changes.
create function public.change_equipment_reservation(p_reservation_id uuid, p_quantity integer, p_cancel boolean)
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

create function public.update_equipment_reservation(p_reservation_id uuid, p_quantity integer)
returns jsonb language sql security definer set search_path = public as $$
    select public.change_equipment_reservation(p_reservation_id, p_quantity, false);
$$;

create function public.cancel_equipment_reservation(p_reservation_id uuid)
returns jsonb language sql security definer set search_path = public as $$
    select public.change_equipment_reservation(p_reservation_id, null, true);
$$;

revoke all on function public.change_equipment_reservation(uuid,integer,boolean),
public.my_equipment_reservations(), public.update_equipment_reservation(uuid,integer),
public.cancel_equipment_reservation(uuid) from public, anon, authenticated;
grant execute on function public.my_equipment_reservations(),
public.update_equipment_reservation(uuid,integer), public.cancel_equipment_reservation(uuid) to authenticated;

notify pgrst, 'reload schema';
commit;
