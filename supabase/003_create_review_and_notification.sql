-- ConnectSphere EMS: Event review outcomes and notifications
-- Run this file in the Supabase SQL Editor.
--
-- Supports the "Event Review and Approval" story: an Event Coordinator
-- approves, rejects, or asks the Event Organiser for clarification, adds
-- comments, and the people involved are notified of the outcome.

-- The three outcomes are fixed by the customer requirements, so a PostgreSQL
-- enum is appropriate. Requesting clarification deliberately has no status of
-- its own: the customer confirmed it "can be a sub-state of under_review".
do $$
begin
    if not exists (select 1 from pg_type where typname = 'review_outcome') then
        create type public.review_outcome as enum (
            'approved',
            'rejected',
            'clarification_requested'
        );
    end if;
end
$$;

-- One row per review action, never overwritten. A request that goes through
-- two rounds of clarification keeps both, which is what the customer meant by
-- "important actions should be recorded... co-ordinator and organiser should
-- be able to view".
create table if not exists public.event_request_review (
    review_id bigint generated always as identity primary key,

    event_request_id bigint not null
        references public.event_request(event_request_id) on delete cascade,

    -- The Event Coordinator who carried out the review.
    reviewer_id bigint not null references public.users(user_id),

    outcome public.review_outcome not null,

    -- Optional when approving; required otherwise, so an Organiser is never
    -- told "rejected" or "please clarify" with no explanation.
    comments text,

    created_at timestamptz not null default now(),

    constraint event_request_review_reason_required check (
        outcome = 'approved'
        or (comments is not null and btrim(comments) <> '')
    )
);

create index if not exists event_request_review_request_idx
    on public.event_request_review (event_request_id, created_at desc);

comment on table public.event_request_review is
    'Audit trail of Event Coordinator decisions on event requests. Append only.';

-- One row per recipient: a single decision notifies both the Organiser and
-- the Coordinator, and each of them reads or dismisses it independently.
create table if not exists public.notification (
    notification_id bigint generated always as identity primary key,

    recipient_id bigint not null
        references public.users(user_id) on delete cascade,

    -- Nullable: later stories will notify about venue bookings, equipment and
    -- registrations, which will each add their own nullable foreign key here
    -- rather than a generic entity id, so referential integrity is kept.
    event_request_id bigint
        references public.event_request(event_request_id) on delete cascade,

    -- Free text rather than an enum: the set of notification types grows with
    -- every new story, and adding an enum value is a schema migration.
    notification_type text not null check (btrim(notification_type) <> ''),

    message text not null check (btrim(message) <> ''),

    is_read boolean not null default false,

    created_at timestamptz not null default now()
);

-- Supports the common query: my unread notifications, newest first.
create index if not exists notification_recipient_idx
    on public.notification (recipient_id, is_read, created_at desc);

comment on table public.notification is
    'In-app notifications. One row per recipient per event.';

-- Row Level Security, with no policies: nothing reaches these tables using
-- the publishable key, which is public by design and ships in browser code.
--
-- This does not affect the Flask backend. It connects with the secret key,
-- which bypasses RLS. Nothing else talks to Supabase directly: the React app
-- goes through the Flask API.
--
-- Policies get added when the User Authorisation story introduces real
-- Supabase Auth sessions. Until then, deny by default.
alter table public.event_request_review enable row level security;
alter table public.notification enable row level security;
