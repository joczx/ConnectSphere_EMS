-- For the existing INTEGER equipment catalogue (006_create_equipment).
-- Apply this INSTEAD OF legacy 005_equipment_reservations.sql.
-- Requires existing events, equipment, equipment_request and auth.users tables.
-- Preserves catalogue data and existing catalogue access policies.
begin;

create table public.equipment_reservations (
    reservation_id uuid primary key default gen_random_uuid(),
    event_id text not null,
    equipment_id integer not null references public.equipment(equipment_id),
    quantity integer not null check (quantity > 0),
    starts_at timestamptz not null,
    ends_at timestamptz not null check (ends_at > starts_at),
    created_by uuid not null references auth.users(id),
    created_at timestamptz not null default now(),
    unique (event_id, equipment_id)
);
create index equipment_reservation_lookup on public.equipment_reservations(equipment_id, starts_at, ends_at);
alter table public.equipment_reservations enable row level security;
revoke all on public.equipment_reservations from anon, authenticated;

-- JSON extraction accommodates both date conventions present in the repo,
-- and text event IDs accommodate UUID or integer IDs in existing deployments.
create function public.equipment_events() returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(jsonb_build_object(
        'event_id', e.event_id::text, 'event_name', e.event_name,
        'starts_at', coalesce(to_jsonb(e)->>'start_datetime', to_jsonb(e)->>'starts_at'),
        'ends_at', coalesce(to_jsonb(e)->>'end_datetime', to_jsonb(e)->>'ends_at')
    ) order by e.event_name), '[]'::jsonb) from public.events e;
$$;

-- Peak concurrent usage, not the sum of every reservation touching a window.
-- Group equal timestamps so an event ending at 10:00 frees stock at 10:00.
create function public.equipment_peak(p_equipment_id integer, p_start timestamptz, p_end timestamptz)
returns bigint language sql stable set search_path = public as $$
    with commitments as (
        select equipment_id, quantity, starts_at, ends_at from public.equipment_reservations
        union all
        select r.equipment_id, r.quantity,
            coalesce(to_jsonb(e)->>'start_datetime', to_jsonb(e)->>'starts_at')::timestamptz,
            coalesce(to_jsonb(e)->>'end_datetime', to_jsonb(e)->>'ends_at')::timestamptz
        from public.equipment_request r join public.events e on e.event_id = r.event_id
        where r.status in ('accepted', 'in_progress', 'partially_accepted', 'completed')
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

create function public.equipment_availability(p_event_id text) returns jsonb
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
    from public.equipment q left join public.equipment_reservations r
    on r.equipment_id = q.equipment_id and r.event_id = p_event_id;
    return jsonb_build_object('equipment', items, 'starts_at', s, 'ends_at', f);
end;
$$;

create function public.reserve_equipment(p_event_id text, p_equipment_id integer, p_quantity integer)
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

-- Reservation times must not silently drift away from their event.
create function public.guard_equipment_event() returns trigger
language plpgsql security definer set search_path = public as $$
begin
    if tg_op = 'DELETE' then
        delete from public.equipment_reservations where event_id = old.event_id::text;
        return old;
    end if;
    if exists (select 1 from public.equipment_reservations where event_id = old.event_id::text)
       and (new.event_id is distinct from old.event_id
       or coalesce(to_jsonb(new)->>'start_datetime', to_jsonb(new)->>'starts_at') is distinct from coalesce(to_jsonb(old)->>'start_datetime', to_jsonb(old)->>'starts_at')
       or coalesce(to_jsonb(new)->>'end_datetime', to_jsonb(new)->>'ends_at') is distinct from coalesce(to_jsonb(old)->>'end_datetime', to_jsonb(old)->>'ends_at')) then
        raise exception 'Release equipment reservations before changing event dates.';
    end if;
    return new;
end;
$$;
create trigger guard_equipment_event before update or delete on public.events
for each row execute function public.guard_equipment_event();

revoke all on function public.equipment_events(), public.equipment_peak(integer,timestamptz,timestamptz),
public.equipment_availability(text), public.reserve_equipment(text,integer,integer), public.guard_equipment_event() from public, anon, authenticated;
grant execute on function public.equipment_events(), public.equipment_availability(text), public.reserve_equipment(text,integer,integer) to authenticated;

-- Both equipment screens use the same stock calculation.
create function public.equipment_window_availability(p_start timestamptz, p_end timestamptz)
returns jsonb language plpgsql security definer set search_path = public as $$
begin
    if auth.uid() is null then raise exception 'Authentication required'; end if;
    if p_start is null or p_end is null or p_end <= p_start then
        raise exception 'A valid time window is required';
    end if;
    return (select coalesce(jsonb_agg(jsonb_build_object(
        'equipment_id', q.equipment_id, 'equipment_type', q.equipment_type,
        'equipment_model', q.equipment_model, 'total_quantity', q.total_quantity,
        'available_quantity', greatest(0, q.total_quantity - public.equipment_peak(q.equipment_id, p_start, p_end))
    ) order by q.equipment_type, q.equipment_model), '[]'::jsonb) from public.equipment q);
end;
$$;
revoke all on function public.equipment_window_availability(timestamptz,timestamptz) from public, anon;
grant execute on function public.equipment_window_availability(timestamptz,timestamptz) to authenticated;

notify pgrst, 'reload schema';
commit;
