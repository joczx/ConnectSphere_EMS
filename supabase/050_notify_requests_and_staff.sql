-- ConnectSphere EMS: Notify the Event Organiser of their request's progress, and
-- staff and the Coordinator when staff are assigned to an event.
-- Run in the Supabase SQL Editor after 049.
--
-- 1. notify_event_request_submitted (046) now also tells the Organiser when their
--    request is submitted, approved or rejected. The reviewer and reason come from
--    the latest review, which is recorded before the status changes. On approval
--    the event already exists: create_event_after_request_approval fires first.
-- 2. Staff are assigned only when an event is created from an approved request
--    (auto_assign_event_staff, 043, before insert), so this notifies after insert.

begin;

create or replace function public.notify_event_request_submitted() returns trigger
language plpgsql security definer set search_path = public as $$
declare
    request text := coalesce(new.event_name, 'an unnamed event');
    latest public.event_request_review;
    reviewer text;
    event_link text;
begin
    if new.status = 'submitted' and (tg_op = 'INSERT' or old.status is distinct from 'submitted') then
        perform public.notify_role('event_coordinator_lead', 'event_request_submitted', 'New event request',
            format('Event request for %s by %s received and pending coordinator assignment.', request,
                   coalesce((select name from public.users where user_id = new.event_organiser_id), 'an Event Organiser')),
            '/assign-event-coordinators?request=' || new.event_request_id);
        perform public.notify_user(new.event_organiser_id, 'event_request_submitted', 'Event request submitted',
            format('Your event request %s has been submitted and is awaiting review.', request),
            '/event-requests/' || new.event_request_id);
    elsif tg_op = 'UPDATE' and new.status in ('planning', 'rejected') and old.status is distinct from new.status then
        select * into latest from public.event_request_review
        where event_request_id = new.event_request_id order by created_at desc, review_id desc limit 1;
        reviewer := coalesce((select name from public.users
                              where user_id = coalesce(latest.reviewer_id, new.event_coordinator_id)), 'the Event Coordinator');
        if new.status = 'planning' then
            select '/events/' || event_id into event_link from public.events where event_request_id = new.event_request_id;
            perform public.notify_user(new.event_organiser_id, 'event_request_approved', 'Event request approved',
                format('Your event request %s has been approved by %s. It is now in planning.', request, reviewer),
                coalesce(event_link, '/event-requests/' || new.event_request_id));
        else
            perform public.notify_user(new.event_organiser_id, 'event_request_rejected', 'Event request rejected',
                format('Your event request %s has been rejected by %s. Reason: %s', request, reviewer,
                       coalesce(latest.comments, 'none given')),
                '/event-requests/' || new.event_request_id);
        end if;
    end if;
    return null;
end;
$$;

create or replace function public.notify_event_staff_assigned() returns trigger
language plpgsql security definer set search_path = public as $$
declare
    coordinator text := coalesce((select name from public.users where user_id = new.event_coordinator_id), 'not assigned');
    details text := format('%s by %s (%s – %s SGT)', coalesce(new.event_name, 'an unnamed event'),
        coalesce((select name from public.users where user_id = new.event_organiser_id), 'an Event Organiser'),
        to_char(new.start_datetime at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
        to_char(new.end_datetime at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'));
    staff record;
    assigned text[] := '{}';
begin
    for staff in select * from (values
        (new.venue_staff_id, 'Venue Staff', '/events/' || new.event_id),
        (new.technical_support_id, 'Technical Support', '/events/' || new.event_id),
        (new.safety_officer_id, 'Safety Officer', '/operational-safety-reviews')) as s(user_id, role, link)
    loop
        assigned := assigned || format('%s %s', staff.role,
            coalesce((select name from public.users where user_id = staff.user_id), 'not assigned'));
        if staff.user_id is not null then
            perform public.notify_user(staff.user_id, 'event_staff_assigned', 'Event assigned to you',
                format('Event %s has been assigned to you as %s. Event Coordinator: %s.', details, staff.role, coordinator),
                staff.link);
        end if;
    end loop;
    if new.event_coordinator_id is not null
       and coalesce(new.venue_staff_id, new.technical_support_id, new.safety_officer_id) is not null then
        perform public.notify_user(new.event_coordinator_id, 'event_staff_assigned', 'Staff assigned to your event',
            format('Staff assigned to %s: %s.', coalesce(new.event_name, 'an unnamed event'), array_to_string(assigned, ', ')),
            '/events/' || new.event_id);
    end if;
    return null;
end;
$$;
drop trigger if exists notify_event_staff_assigned on public.events;
create trigger notify_event_staff_assigned after insert on public.events
    for each row execute function public.notify_event_staff_assigned();

revoke all on function public.notify_event_request_submitted(), public.notify_event_staff_assigned()
    from public, anon, authenticated;

commit;
