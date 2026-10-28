-- ConnectSphere EMS: Notification service
-- Run in the Supabase SQL Editor after 045.
--
-- Replaces the old notification system with shared infrastructure that every
-- notification-worthy event uses, and adds the first such event.
--
-- 1. THE OLD SYSTEM IS RETIRED
--    public.notification is emptied and now discards anything written to it.
--    Existing producers (venue booking reviews, holds and unavailability,
--    coordinator assignment 029/030, safety decisions 035, event change
--    requests 037/038, and two backend services) keep working but notify no
--    one, until each event is re-added on the new service. Drop the table once
--    nothing writes to it.
--
-- 2. THE NEW SERVICE
--    public.notifications holds every notification ever sent. Database code
--    creates them with notify_user() or notify_role(); clients cannot. Users
--    read their own through list_my_notifications() and mark one read with
--    mark_notification_read(); the table itself is not reachable by clients.
--
-- 3. FIRST EVENT: an event request is submitted
--    Every Event Coordinator Lead is told, with a link to Assign Event
--    Coordinators. A trigger covers every way a request becomes submitted.

begin;

-- 1. Retire the old system -------------------------------------------------

delete from public.notification;

create or replace function public.discard_legacy_notification() returns trigger
language plpgsql as $$ begin return null; end; $$;
drop trigger if exists discard_legacy_notification on public.notification;
create trigger discard_legacy_notification before insert on public.notification
    for each row execute function public.discard_legacy_notification();

drop function if exists public.venue_booking_alerts();
drop function if exists public.dismiss_venue_booking_alerts(bigint[]);

-- 2. The new service --------------------------------------------------------

create table if not exists public.notifications (
    notification_id bigint generated always as identity primary key,
    recipient_id uuid not null references auth.users(id) on delete cascade,
    kind text not null check (btrim(kind) <> ''),
    title text not null check (btrim(title) <> ''),
    body text not null check (btrim(body) <> ''),
    link text,  -- in-app path to the item the notification is about
    created_at timestamptz not null default now(),
    read_at timestamptz
);
create index if not exists notifications_recipient_idx on public.notifications (recipient_id, created_at desc);
alter table public.notifications enable row level security;
revoke all on public.notifications from anon, authenticated;

create or replace function public.notify_user(
    p_recipient uuid, p_kind text, p_title text, p_body text, p_link text default null
) returns void
language sql security definer set search_path = public as $$
    insert into public.notifications (recipient_id, kind, title, body, link)
    select p_recipient, p_kind, p_title, p_body, p_link
    where exists (select 1 from auth.users where id = p_recipient);
$$;

-- Everyone holding a role, matched as has_booking_role() does (017).
create or replace function public.notify_role(
    p_role text, p_kind text, p_title text, p_body text, p_link text default null
) returns void
language sql security definer set search_path = public as $$
    insert into public.notifications (recipient_id, kind, title, body, link)
    select distinct ur.user_id, p_kind, p_title, p_body, p_link
    from public.user_roles ur join public.roles r using (role_id)
    join auth.users u on u.id = ur.user_id
    where replace(lower(trim(r.role_name)), ' ', '_') = p_role;
$$;

-- Newest first. p_days limits how far back (the full page shows 14 days).
create or replace function public.list_my_notifications(p_limit integer, p_offset integer default 0, p_days integer default null)
returns jsonb
language sql stable security definer set search_path = public as $$
    with mine as (
        select * from public.notifications
        where recipient_id = auth.uid()
          and (p_days is null or created_at > now() - make_interval(days => p_days))
    )
    select case when auth.uid() is null
        then jsonb_build_object('error', 'Please sign in again.', 'status', 401)
        else jsonb_build_object(
            'items', coalesce((select jsonb_agg(to_jsonb(page) - 'recipient_id' order by page.created_at desc)
                               from (select * from mine order by created_at desc
                                     limit least(greatest(p_limit, 1), 50) offset greatest(p_offset, 0)) page), '[]'::jsonb),
            'total', (select count(*) from mine),
            'unread', (select count(*) from public.notifications where recipient_id = auth.uid() and read_at is null))
    end;
$$;

create or replace function public.mark_notification_read(p_notification_id bigint) returns jsonb
language plpgsql security definer set search_path = public as $$
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    update public.notifications set read_at = coalesce(read_at, now())
    where notification_id = p_notification_id and recipient_id = auth.uid();
    if not found then
        return jsonb_build_object('error', 'Notification not found.', 'status', 404);
    end if;
    return jsonb_build_object('notification_id', p_notification_id);
end;
$$;

-- 3. First event: an event request is submitted ---------------------------

create or replace function public.notify_event_request_submitted() returns trigger
language plpgsql security definer set search_path = public as $$
begin
    if new.status = 'submitted' and (tg_op = 'INSERT' or old.status is distinct from 'submitted') then
        perform public.notify_role('event_coordinator_lead', 'event_request_submitted', 'New event request',
            format('Event request for %s by %s received and pending coordinator assignment.',
                   coalesce(new.event_name, 'an unnamed event'),
                   coalesce((select name from public.users where user_id = new.event_organiser_id), 'an Event Organiser')),
            '/assign-event-coordinators?request=' || new.event_request_id);
    end if;
    return null;
end;
$$;
drop trigger if exists notify_event_request_submitted on public.event_request;
create trigger notify_event_request_submitted after insert or update of status on public.event_request
    for each row execute function public.notify_event_request_submitted();

revoke all on function public.notify_user(uuid, text, text, text, text), public.notify_role(text, text, text, text, text),
    public.discard_legacy_notification(), public.notify_event_request_submitted() from public, anon, authenticated;
revoke all on function public.list_my_notifications(integer, integer, integer), public.mark_notification_read(bigint)
    from public, anon;
grant execute on function public.list_my_notifications(integer, integer, integer), public.mark_notification_read(bigint)
    to authenticated;

commit;
