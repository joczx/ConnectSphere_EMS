-- ConnectSphere EMS: notify Attendees about their event registration.
-- Run in the Supabase SQL Editor after 056.
--
-- register_for_event and withdraw_event_registration (049) write the
-- attendee's event_registration row: inserted, or updated when re-registering
-- after a withdrawal, as registered or waiting_list (when the event is full and
-- its waiting list is on), and updated to withdrawn. cancel_planned_event (034)
-- sets the event to cancelled. Triggers on those changes tell the Attendee,
-- so none of the functions is copied. The emails 049 queues are unchanged.

begin;

-- "Launch (05 Jan 2027 10:00 – 05 Jan 2027 13:00 SGT) at Hall A"; the venue is
-- the approved booking's, left out until there is one.
create or replace function public.event_registration_details(p_event public.events) returns text
language sql stable set search_path = public as $$
    select format('%s (%s – %s SGT)%s', p_event.event_name,
        to_char(p_event.start_datetime at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
        to_char(p_event.end_datetime at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
        coalesce(' at ' || (select v.venue_name from public.venue_booking_requests b join public.venues v using (venue_id)
            where b.event_id = p_event.event_id and b.status = 'approved' order by b.reviewed_at desc limit 1), ''));
$$;

create or replace function public.notify_event_registration() returns trigger
language plpgsql security definer set search_path = public as $$
declare details text := public.event_registration_details((select e from public.events e where e.event_id = new.event_id));
begin
    perform public.notify_user(new.attendee_id, 'event_registration_' || new.status,
        case new.status when 'registered' then 'Event registration confirmed'
                        when 'waiting_list' then 'Added to waiting list'
                        else 'Event registration withdrawn' end,
        case new.status when 'registered' then format('Your registration for %s is confirmed.', details)
                        when 'waiting_list' then format('%s is full, so you have been added to its waiting list instead. '
                                                        'This does not confirm a place at the event.', details)
                        else format('Your registration for %s has been withdrawn.', details) end,
        '/my-registrations');
    return null;
end;
$$;
drop trigger if exists notify_event_registration on public.event_registration;
create trigger notify_event_registration after insert or update of status on public.event_registration
    for each row execute function public.notify_event_registration();

create or replace function public.notify_event_cancelled() returns trigger
language plpgsql security definer set search_path = public as $$
declare attendee uuid; details text := public.event_registration_details(new);
begin
    for attendee in select attendee_id from public.event_registration
                    where event_id = new.event_id and status in ('registered', 'waiting_list') loop
        perform public.notify_user(attendee, 'event_cancelled', 'Event cancelled',
            format('%s has been cancelled, so your registration no longer applies.', details), '/my-registrations');
    end loop;
    return null;
end;
$$;
drop trigger if exists notify_event_cancelled on public.events;
create trigger notify_event_cancelled after update of status on public.events
    for each row when (new.status = 'cancelled' and old.status is distinct from new.status)
    execute function public.notify_event_cancelled();

revoke all on function public.event_registration_details(public.events), public.notify_event_registration(),
    public.notify_event_cancelled() from public, anon, authenticated;

commit;
