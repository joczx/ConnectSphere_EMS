-- ConnectSphere EMS: Event request amendments
-- Run this file in the Supabase SQL Editor.
--
-- Supports the "Amend Event Request" story: when an Event Coordinator asks for
-- clarification, the Event Organiser updates the request and resubmits it.
-- The customer was clear that an Organiser "cannot directly edit after
-- submission" - this table records the sanctioned exception, so every change
-- made after submission is accounted for.

create table if not exists public.event_request_amendment (
    amendment_id bigint generated always as identity primary key,

    event_request_id bigint not null
        references public.event_request(event_request_id) on delete cascade,

    -- The Event Organiser who made the change.
    amended_by bigint not null references public.users(user_id),

    -- What actually changed, as {"field": {"from": old, "to": new}}. This is
    -- the "records the updated information" half of the requirement: the
    -- before value is otherwise lost the moment the row is updated.
    changes jsonb not null default '{}'::jsonb,

    -- Optional reply to the Coordinator's question. The field changes often
    -- speak for themselves, so this is not forced.
    note text,

    created_at timestamptz not null default now(),

    constraint event_request_amendment_changes_is_object
        check (jsonb_typeof(changes) = 'object')
);

create index if not exists event_request_amendment_request_idx
    on public.event_request_amendment (event_request_id, created_at desc);

comment on table public.event_request_amendment is
    'Changes made by an Event Organiser after submission, in response to a '
    'Coordinator request for clarification. Append only.';

-- Deny by default, as with the other tables: the Flask backend uses the
-- secret key and bypasses RLS, and nothing else reaches Supabase directly.
alter table public.event_request_amendment enable row level security;
