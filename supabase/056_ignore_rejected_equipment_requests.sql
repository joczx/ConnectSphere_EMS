-- ConnectSphere EMS: equipment requests and the safety-check / confirmation gate.
-- Run in the Supabase SQL Editor after 055.
-- event_confirmation_blockers (053) required every equipment request to be
-- fully reserved. That was wrong both ways:
--   * a rejected request is never reserved, and a cancelled one (its reservation
--     cancelled, 036) no longer is, so either blocked the event even when its
--     equipment requirements were met;
--   * Technical Support reserve before recording acceptance (036), so a request
--     still pending passed as soon as it was reserved.
-- Copied from 053; only the final check changes: rejected and cancelled
-- requests are ignored, and every other request must be accepted as well as
-- fully reserved. The event's own equipment requirements are still checked
-- against its reservations above.

begin;

create or replace function public.event_confirmation_blockers(p_event public.events)
returns text[] language plpgsql volatile security definer set search_path = public as $$
declare blockers text[] := '{}'; item jsonb; reserved bigint;
begin
    if p_event.event_coordinator_id is null then
        blockers := array_append(blockers, 'An Event Coordinator must be assigned.');
    end if;
    if p_event.start_datetime is null or p_event.end_datetime is null
        or p_event.end_datetime <= p_event.start_datetime then
        blockers := array_append(blockers, 'Valid event dates are required.');
    end if;
    if not exists (
        select 1 from public.venue_booking_requests b join public.venues v using (venue_id)
        where b.event_id = p_event.event_id and b.status = 'approved'
          and b.starts_at = p_event.start_datetime and b.ends_at = p_event.end_datetime
          and (p_event.capacity_needed is null or b.attendance = p_event.capacity_needed)
          and v.deleted_at is null
          and cardinality(public.venue_shortfalls_for_event(v, p_event)) = 0
    ) then
        blockers := array_append(blockers, 'An approved venue booking matching the event is required.');
    end if;
    if p_event.equipment_requirements is null then
        blockers := array_append(blockers, 'Record equipment requirements, or an empty list if none are needed.');
    elsif jsonb_typeof(p_event.equipment_requirements) <> 'array' then
        blockers := array_append(blockers, 'Equipment requirements must be a list of types and quantities.');
    else
        for item in select value from jsonb_array_elements(p_event.equipment_requirements) loop
            if jsonb_typeof(item) <> 'object'
                or jsonb_typeof(item->'equipment_type') is distinct from 'string'
                or jsonb_typeof(item->'quantity') is distinct from 'number'
                or nullif(btrim(item->>'equipment_type'), '') is null
                or coalesce(item->>'quantity', '') !~ '^[1-9][0-9]*$' then
                blockers := array_append(blockers, 'Each equipment requirement needs a type and positive quantity.');
                continue;
            end if;
            select coalesce(sum(r.quantity), 0) into reserved
            from public.equipment_reservations r join public.equipment q using (equipment_id)
            where r.event_id = p_event.event_id
              and lower(btrim(q.equipment_type)) = lower(btrim(item->>'equipment_type'))
              and r.starts_at <= p_event.start_datetime and r.ends_at >= p_event.end_datetime;
            if reserved < (item->>'quantity')::numeric then
                blockers := array_append(blockers, 'Reserve all required ' || (item->>'equipment_type') || '.');
            end if;
        end loop;
    end if;
    if exists (
        select 1 from public.equipment_request q where q.event_id = p_event.event_id
        and q.status not in ('rejected', 'cancelled')
        and (q.status <> 'accepted' or not exists (select 1 from public.equipment_reservations r
            where r.equipment_request_id = q.equipment_request_id
              and r.quantity >= q.quantity
              and r.starts_at <= p_event.start_datetime and r.ends_at >= p_event.end_datetime))
    ) then
        blockers := array_append(blockers, 'Every equipment request must be accepted and fully reserved.');
    end if;
    return blockers;
end;
$$;

commit;
