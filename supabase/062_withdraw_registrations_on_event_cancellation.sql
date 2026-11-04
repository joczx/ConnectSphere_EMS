-- Apply after 061. Cancellation withdraws active registrations atomically.
begin;

create or replace function public.withdraw_cancelled_event_registrations()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    update public.event_registration
        set status = 'withdrawn', withdrawn_at = clock_timestamp()
        where event_id = new.event_id and status in ('registered', 'waiting_list');
    return null;
end;
$$;

-- AFTER triggers run alphabetically: notify_event_cancelled (057) first tells
-- active attendees why the event disappeared, then this withdraws their rows.
drop trigger if exists withdraw_cancelled_event_registrations on public.events;
create trigger withdraw_cancelled_event_registrations after update of status on public.events
    for each row when (new.status = 'cancelled' and old.status is distinct from new.status)
    execute function public.withdraw_cancelled_event_registrations();

revoke all on function public.withdraw_cancelled_event_registrations() from public, anon, authenticated;

-- Repair registrations belonging to events cancelled before this migration.
-- Already withdrawn records retain their original withdrawal timestamp.
update public.event_registration r
    set status = 'withdrawn', withdrawn_at = clock_timestamp()
    from public.events e
    where r.event_id = e.event_id and e.status = 'cancelled'
        and r.status in ('registered', 'waiting_list');

notify pgrst, 'reload schema';
commit;
