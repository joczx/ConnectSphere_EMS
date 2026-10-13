-- Apply after 016_manage_linked_equipment_reservations.sql.
-- Direct reservations by the event's assigned Technical Support Staff.
begin;

create or replace function public.reservable_equipment_events() returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(jsonb_build_object(
        'event_id', e.event_id::text, 'event_name', e.event_name
    ) order by e.event_name), '[]'::jsonb)
    from public.events e
    where auth.uid() is not null
      and to_jsonb(e)->>'technical_support_id' = auth.uid()::text;
$$;

create or replace function public.reserve_equipment(p_event_id text, p_equipment_id integer, p_quantity integer)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
    ev jsonb; s timestamptz; f timestamptz; stock integer;
    available bigint; saved public.equipment_reservations;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if p_quantity is null or p_quantity <= 0 then
        return jsonb_build_object('error', 'Quantity must be a positive whole number.', 'status', 400);
    end if;
    select to_jsonb(e) into ev from public.events e where e.event_id::text = p_event_id for update;
    if ev is null then return jsonb_build_object('error', 'Event not found.', 'status', 404); end if;
    if ev->>'technical_support_id' is distinct from auth.uid()::text then
        return jsonb_build_object('error', 'Only the assigned Technical Support Staff can reserve equipment for this event.', 'status', 403);
    end if;
    s := coalesce(ev->>'start_datetime', ev->>'starts_at')::timestamptz;
    f := coalesce(ev->>'end_datetime', ev->>'ends_at')::timestamptz;
    if s is null or f is null or f <= s then
        return jsonb_build_object('error', 'Set valid event dates before reserving equipment.', 'status', 400);
    end if;
    -- Stock row lock serializes all writers sharing equipment_peak, including
    -- accepted equipment requests and reservation quantity changes.
    select total_quantity into stock from public.equipment where equipment_id = p_equipment_id for update;
    if not found then return jsonb_build_object('error', 'Equipment not found.', 'status', 404); end if;
    if exists (select 1 from public.equipment_reservations
        where event_id = p_event_id and equipment_id = p_equipment_id and equipment_request_id is null) then
        return jsonb_build_object('error', 'This equipment is already reserved directly for this event. Update the existing reservation instead.', 'status', 409);
    end if;
    -- Same calculation as equipment_window_availability and equipment_availability.
    -- Half-open windows: an event ending at the next event's start does not overlap.
    available := greatest(0, stock - public.equipment_peak(p_equipment_id, s, f));
    if p_quantity > available then
        return jsonb_build_object('error', format('Insufficient equipment: only %s available for this event.', available),
            'available_quantity', available, 'status', 409);
    end if;
    insert into public.equipment_reservations(event_id, equipment_id, quantity, starts_at, ends_at, created_by)
    values (p_event_id, p_equipment_id, p_quantity, s, f, auth.uid()) returning * into saved;
    return jsonb_build_object('reservation', to_jsonb(saved), 'message', 'Equipment reserved successfully.');
end;
$$;

create or replace function public.equipment_availability(p_event_id text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare ev jsonb; s timestamptz; f timestamptz; items jsonb;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.'); end if;
    select to_jsonb(e) into ev from public.events e where e.event_id::text = p_event_id;
    if ev is null then return jsonb_build_object('error', 'Event not found.'); end if;
    s := coalesce(ev->>'start_datetime', ev->>'starts_at')::timestamptz;
    f := coalesce(ev->>'end_datetime', ev->>'ends_at')::timestamptz;
    if s is null or f is null or f <= s then
        return jsonb_build_object('error', 'Set a valid event start and end time before reserving equipment.');
    end if;
    select coalesce(jsonb_agg(jsonb_build_object(
        'equipment_id', q.equipment_id, 'name', concat_ws(' - ', q.equipment_type, q.equipment_model),
        'total_quantity', q.total_quantity,
        'available_quantity', greatest(0, q.total_quantity - public.equipment_peak(q.equipment_id, s, f)),
        'reserved_quantity', coalesce(r.quantity, 0), 'standalone_reserved', coalesce(r.standalone, false)
    ) order by q.equipment_type, q.equipment_model), '[]'::jsonb) into items
    from public.equipment q left join (
        select equipment_id, sum(quantity) as quantity, bool_or(equipment_request_id is null) as standalone
        from public.equipment_reservations where event_id = p_event_id group by equipment_id
    ) r on r.equipment_id = q.equipment_id;
    return jsonb_build_object('equipment', items, 'starts_at', s, 'ends_at', f);
end;
$$;

revoke all on function public.reservable_equipment_events() from public, anon;
grant execute on function public.reservable_equipment_events() to authenticated;
notify pgrst, 'reload schema';
commit;
