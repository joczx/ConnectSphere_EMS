-- ConnectSphere EMS: Activity History for events in planning
-- Run this file in the Supabase SQL Editor.
--
-- Supports the "Update Event Information" user story, which requires the
-- system to "log a 'Critical Edit' entry in the Activity History when the user
-- confirms the modal prompt".
--
-- public.event_request_amendment already does this for the approval phase, but
-- it is keyed on event_request_id and records an Organiser answering a
-- Coordinator's question. This table is the operational-phase equivalent: who
-- changed what on the event itself, once planning is under way.
--
-- Append only. A row is never updated or deleted, so the history stays a
-- faithful account of what happened rather than what is currently true.

create table if not exists public.event_activity (
    activity_id bigint generated always as identity primary key,

    event_id integer not null
        references public.events(event_id) on delete cascade,

    -- The signed-in user who made the change. Nullable so that a change made
    -- by a future automated process still records what happened.
    changed_by uuid,

    -- 'critical_edit' is the entry the user story names. Ordinary edits are
    -- recorded too, under 'edit': the story only requires critical ones, but a
    -- history that silently omits half the changes is worse than no history
    -- when someone is trying to work out when a detail changed.
    change_type text not null check (change_type in ('edit', 'critical_edit')),

    -- {field: {"from": old, "to": new}}, as produced by schemas/event.py diff().
    -- Stored rather than recomputed because the previous value is lost the
    -- moment the events row is updated.
    changes jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now()
);

-- The common query: this event's history, newest first.
create index if not exists event_activity_event_idx
    on public.event_activity (event_id, created_at desc);

comment on table public.event_activity is
    'Append-only record of changes made to an event during planning. '
    'change_type ''critical_edit'' marks a change the user was warned about '
    'and confirmed.';

alter table public.event_activity enable row level security;

-- Matches how public.events is read today: the Flask API passes the caller's
-- own access token, so these policies are what the browser is subject to.
-- Narrowing who may read an event's history belongs with narrowing who may
-- read the event, which 023 handles as its own decision.
drop policy if exists authenticated_read_event_activity on public.event_activity;
create policy authenticated_read_event_activity on public.event_activity
    for select to authenticated using (true);

drop policy if exists authenticated_write_event_activity on public.event_activity;
create policy authenticated_write_event_activity on public.event_activity
    for insert to authenticated with check (true);
