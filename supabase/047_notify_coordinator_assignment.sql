-- ConnectSphere EMS: Notify Event Coordinators when an event is assigned or reassigned
-- Run in the Supabase SQL Editor after 046.
--
-- Only an Event Coordinator Lead changes a coordinator: assigning a request
-- (029), reassigning a request awaiting review, or reassigning an approved
-- event (030), which also updates its request. Every event has a request, so
-- one trigger on the request's coordinator covers all three, once each.
--
-- The new coordinator is told what they now manage and who assigned it; on a
-- reassignment the previous coordinator is told it has moved and to whom. The
-- Lead is the signed-in user making the change (auth.uid()).

begin;

create or replace function public.notify_coordinator_assignment() returns trigger
language plpgsql security definer set search_path = public as $$
declare
    planned public.events;
    lead text := coalesce((select name from public.users where user_id = auth.uid()), 'an Event Coordinator Lead');
    item text;
begin
    if new.event_coordinator_id is not distinct from old.event_coordinator_id then
        return null;
    end if;
    select * into planned from public.events where event_request_id = new.event_request_id;
    -- An approved event may have been renamed since it was requested.
    item := format('%s by %s', coalesce(planned.event_name, new.event_name, 'an unnamed event'),
                   coalesce((select name from public.users where user_id = new.event_organiser_id), 'an Event Organiser'));

    if new.event_coordinator_id is not null then
        perform public.notify_user(new.event_coordinator_id, 'coordinator_assigned', 'Event assigned to you',
            case when planned.event_id is null
                then format('Event request %s has been %s to you by %s, pending review.', item,
                            case when old.event_coordinator_id is null then 'assigned' else 'reassigned' end, lead)
                else format('Event %s has been reassigned to you by %s. It is currently in %s.', item, lead,
                            replace(planned.status::text, '_', ' '))
            end,
            case when planned.event_id is null then '/review-event-requests/' || new.event_request_id
                 else '/events/' || planned.event_id end);
    end if;

    -- The previous coordinator can no longer open the item, so the link goes to their list.
    if old.event_coordinator_id is not null then
        perform public.notify_user(old.event_coordinator_id, 'coordinator_unassigned', 'Event reassigned',
            format('%s %s has been reassigned from you to %s by %s.',
                   case when planned.event_id is null then 'Event request' else 'Event' end, item,
                   coalesce((select name from public.users where user_id = new.event_coordinator_id), 'another Event Coordinator'),
                   lead),
            case when planned.event_id is null then '/review-event-requests' else '/events' end);
    end if;
    return null;
end;
$$;
revoke all on function public.notify_coordinator_assignment() from public, anon, authenticated;

drop trigger if exists notify_coordinator_assignment on public.event_request;
create trigger notify_coordinator_assignment after update of event_coordinator_id on public.event_request
    for each row execute function public.notify_coordinator_assignment();

commit;
