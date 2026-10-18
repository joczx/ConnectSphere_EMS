-- Repair equipment page readers in deployments using integer reservation event IDs.
-- Compatible with both legacy text and integer columns. Ownership filters and
-- existing function grants are preserved; no rows or column types are changed.
-- Apply after 016 and the later equipment migrations in the Supabase SQL Editor.
begin;
create or replace function public.equipment_request_review_queue() returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(to_jsonb(r) || jsonb_build_object(
        'event_name', e.event_name) order by e.event_name, r.requested_at), '[]'::jsonb)
    from public.equipment_request r join public.events e on e.event_id::text = r.event_id::text
    where r.requested_by = auth.uid();
$$;

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
    join public.events e on e.event_id::text = r.event_id::text
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
            where r.event_id::text = e.event_id::text and r.requested_by = auth.uid())
        or exists (select 1 from public.equipment_reservations r
            where r.event_id::text = e.event_id::text and r.created_by = auth.uid())
    );
$$;

notify pgrst, 'reload schema';
commit;
