-- Apply after 022; also repairs deployments missing the role helper from 032. Fix direct reservation ID comparisons and inserts for
-- both integer and legacy text equipment_reservations.event_id columns.
-- Keep the public role guard and private assignment/stock implementation.
begin;
create or replace function public.can_reserve_equipment()
returns boolean language sql stable security definer set search_path = public as $$
    select auth.uid() is not null and exists (
        select 1 from public.user_roles ur join public.roles r using (role_id)
        where ur.user_id = auth.uid()
          and lower(replace(btrim(r.role_name), ' ', '_'))
              in ('technical_support_staff', 'technical_support')
    );
$$;

create or replace function public.reserve_equipment_assigned(p_event_id text, p_equipment_id integer, p_quantity integer)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
    ev jsonb; reservation_event_id public.equipment_reservations.event_id%type; s timestamptz; f timestamptz; stock integer;
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
        where event_id::text = p_event_id and equipment_id = p_equipment_id and equipment_request_id is null) then
        return jsonb_build_object('error', 'This equipment is already reserved directly for this event. Update the existing reservation instead.', 'status', 409);
    end if;
    -- Same calculation as equipment_window_availability and equipment_availability.
    -- Half-open windows: an event ending at the next event's start does not overlap.
    available := greatest(0, stock - public.equipment_peak(p_equipment_id, s, f));
    if p_quantity > available then
        return jsonb_build_object('error', format('Insufficient equipment: only %s available for this event.', available),
            'available_quantity', available, 'status', 409);
    end if;
    -- Assign the validated event ID using the actual reservation column type.
    -- PL/pgSQL assignment supports either legacy text or integer columns.
    reservation_event_id := ev->>'event_id';
    insert into public.equipment_reservations(event_id, equipment_id, quantity, starts_at, ends_at, created_by)
    values (reservation_event_id, p_equipment_id, p_quantity, s, f, auth.uid()) returning * into saved;
    return jsonb_build_object('reservation', to_jsonb(saved), 'message', 'Equipment reserved successfully.');
end;
$$;

create or replace function public.reserve_equipment(p_event_id text, p_equipment_id integer, p_quantity integer)
returns jsonb language plpgsql security definer set search_path = public as $$
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.can_reserve_equipment() then
        return jsonb_build_object('error', 'Only Technical Support Staff can reserve equipment.', 'status', 403);
    end if;
    return public.reserve_equipment_assigned(p_event_id, p_equipment_id, p_quantity);
end;
$$;

revoke all on function public.reserve_equipment_assigned(text, integer, integer)
    from public, anon, authenticated;
revoke all on function public.reserve_equipment(text, integer, integer) from public, anon;
grant execute on function public.reserve_equipment(text, integer, integer) to authenticated;
revoke all on function public.can_reserve_equipment() from public, anon, authenticated;
grant execute on function public.can_reserve_equipment() to authenticated;
notify pgrst, 'reload schema';
commit;
