-- Apply after 001. Provision events and membership through trusted admin tools.
create table public.events (
 event_id uuid primary key default gen_random_uuid(),
 event_name text not null check (btrim(event_name) <> ''),
 purpose text, description text,
 starts_at timestamptz, ends_at timestamptz,
 expected_attendance integer check (expected_attendance >= 0),
 venue_requirements text, accessibility_needs text, equipment_requirements text,
 registration_required boolean, registration_needs text,
 version integer not null default 1,
 updated_at timestamptz not null default now(),
 check (ends_at >= starts_at)
);
create table public.event_members (
 event_id uuid references public.events on delete cascade,
 user_id uuid references auth.users on delete cascade,
 role text not null check (role in ('event_organiser', 'event_coordinator')),
 primary key (event_id, user_id)
);
create index event_members_user_idx on public.event_members(user_id);
create function public.stamp_event_update() returns trigger
language plpgsql set search_path = public as $$
begin
 new.version := old.version + 1;
 new.updated_at := clock_timestamp();
 return new;
end;
$$;
create trigger stamp_event_update before update on public.events
for each row execute function public.stamp_event_update();
alter table public.events enable row level security;
alter table public.event_members enable row level security;
revoke all on public.events, public.event_members from anon, authenticated;
grant select on public.events, public.event_members to authenticated;
create policy own_memberships on public.event_members for select to authenticated
using (user_id = (select auth.uid()));
create policy assigned_events on public.events for select to authenticated
using (exists (select 1 from public.event_members m
 where m.event_id = events.event_id and m.user_id = (select auth.uid())));
