-- Apply after 022_reserve_available_equipment.sql. Direct reservations require
-- both the Technical Support Staff role and assignment to the selected event.
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

-- Retain the existing stock/assignment implementation as a private function.
alter function public.reserve_equipment(text, integer, integer)
    rename to reserve_equipment_assigned;
revoke all on function public.reserve_equipment_assigned(text, integer, integer)
    from public, anon, authenticated;

create function public.reserve_equipment(p_event_id text, p_equipment_id integer, p_quantity integer)
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

create or replace function public.reservable_equipment_events()
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare result jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.can_reserve_equipment() then
        return jsonb_build_object('error', 'Only Technical Support Staff can reserve equipment.', 'status', 403);
    end if;
    select coalesce(jsonb_agg(jsonb_build_object(
        'event_id', e.event_id::text, 'event_name', e.event_name
    ) order by e.event_name), '[]'::jsonb) into result
    from public.events e where e.technical_support_id = auth.uid();
    return result;
end;
$$;

revoke all on function public.can_reserve_equipment(), public.reserve_equipment(text, integer, integer),
    public.reservable_equipment_events() from public, anon, authenticated;
grant execute on function public.can_reserve_equipment(), public.reserve_equipment(text, integer, integer),
    public.reservable_equipment_events() to authenticated;
commit;
