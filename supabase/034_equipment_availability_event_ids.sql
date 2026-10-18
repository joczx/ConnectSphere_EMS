-- Follow-up to 033: the event-specific availability query also compares
-- reservation IDs with a text RPC parameter. Support integer and text columns.
-- No rows, column types, stock calculations or access rules are changed.
begin;
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
        from public.equipment_reservations where event_id::text = p_event_id group by equipment_id
    ) r on r.equipment_id = q.equipment_id;
    return jsonb_build_object('equipment', items, 'starts_at', s, 'ends_at', f);
end;
$$;

notify pgrst, 'reload schema';
commit;
