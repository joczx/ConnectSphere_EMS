-- ConnectSphere EMS: One status vocabulary for the event lifecycle
-- Run this file in the Supabase SQL Editor.
--
-- The customer's status list treats an event as a single thing moving through
--     Draft -> Submitted -> Planning -> Confirmed -> Completed
-- with Rejected returning it to the Organiser and Cancelled reachable at any
-- stage. The schema splits that across two tables: public.event_request holds
-- the approval phase, and public.events (created from an approved request via
-- events.event_request_id) holds the operational phase.
--
-- Rather than give each table its own vocabulary and duplicate 'rejected' and
-- 'cancelled' across both, one enum covers the whole lifecycle:
--
--   event_request : draft -> submitted -> planning | rejected   (| cancelled)
--   events        : planning -> confirmed -> completed          (| cancelled)
--
-- 'under_review' is retired. The customer confirmed that asking for
-- clarification "can be a sub-state of under_review", and that sub-state is
-- already derived from the latest public.event_request_review row rather than
-- stored, so the status column never needed to distinguish it from 'submitted'.
--
-- 'approved' is retired in favour of 'planning'. They described the same state
-- from two angles -- the Coordinator's decision, and what happens next -- and
-- public.events already defaulted to 'planning' for exactly that state.
--
-- public.review_outcome is deliberately untouched: it records what a reviewer
-- DID (approved / rejected / clarification_requested), which is a different
-- thing from where the request now IS.

begin;

create type public.event_status as enum (
    'draft',
    'submitted',
    'planning',
    'rejected',
    'confirmed',
    'completed',
    'cancelled'
);

-- public.create_event_after_request_approval pins the old type in its WHEN
-- clause ('approved'::request_status), so PostgreSQL refuses to alter the
-- column while it exists. It comes back at the end of this file keyed on
-- 'planning' instead, which is the same moment in the lifecycle under the new
-- vocabulary: the Coordinator has approved, and the event now needs planning.
--
-- Its function, create_event_from_approved_request(), needs no change: it
-- already inserts the literal 'planning' into events.status, so it was written
-- against this vocabulary before the enum caught up with it.
drop trigger if exists create_event_after_request_approval on public.event_request;

-- complete_before_submit pins the old type the same way, in 'draft'::request_status.
-- It is recreated verbatim below with only that cast changed, so which requests
-- the database accepts does not move with this migration.
alter table public.event_request
    drop constraint if exists complete_before_submit;

-- public.event_request: currently public.request_status.
alter table public.event_request
    alter column status drop default;

alter table public.event_request
    alter column status type public.event_status
    using (case status::text
               -- No row currently holds 'under_review', but the value exists in
               -- the old type, so map it rather than let a late write fail the
               -- cast: a request being clarified is still awaiting a decision.
               when 'under_review' then 'submitted'
               when 'approved'     then 'planning'
               else status::text
           end)::public.event_status;

alter table public.event_request
    alter column status set default 'draft'::public.event_status;

-- public.events: currently character varying, defaulting to 'planning'.
--
-- The live table has this column; 002_create_events.sql does not create it.
-- That file no longer describes the deployed table at all (different primary
-- key type, different timestamp column names, a dozen columns missing), so it
-- cannot rebuild production either way. This guard is here only so the
-- migration is a no-op rather than an error against a database where the
-- column is absent. It changes nothing against the live instance.
alter table public.events
    add column if not exists status text not null default 'planning';

alter table public.events
    alter column status drop default;

alter table public.events
    alter column status type public.event_status
    using btrim(lower(status))::public.event_status;

alter table public.events
    alter column status set default 'planning'::public.event_status;

-- Nothing else references the old type now that the trigger is gone. Dropping
-- it is what stops 'approved' and 'under_review' coming back.
drop type public.request_status;

-- Back on the new vocabulary, otherwise character for character as it was: a
-- request may be incomplete only while it is a draft.
--
-- Note for whoever implements cancellation: 'cancelled' is NOT exempt here, so
-- cancelling an incomplete draft would fail this check. That is deliberate --
-- this migration changes the vocabulary, not the rules -- and it costs nothing
-- today because nothing writes 'cancelled' to a request, and an unwanted draft
-- is deleted rather than cancelled. If cancelling a draft becomes a real
-- action, widen this to (status in ('draft', 'cancelled')) as its own change.
alter table public.event_request
    add constraint complete_before_submit check (
        status = 'draft'::public.event_status
        or (
            event_name is not null
            and purpose is not null
            and start_datetime is not null
            and end_datetime is not null
            and capacity_needed is not null
        )
    );

-- Back on the new vocabulary. Approving an event request still creates the
-- events row exactly once: the function's "on conflict (event_request_id) do
-- nothing" means a request that returns to planning never duplicates it.
create trigger create_event_after_request_approval
    after update of status on public.event_request
    for each row
    when (
        new.status = 'planning'::public.event_status
        and old.status is distinct from 'planning'::public.event_status
    )
    execute function public.create_event_from_approved_request();

comment on column public.event_request.status is
    'Approval phase of the event lifecycle. A request leaves this table''s '
    'care at ''planning'' (approved, an events row now exists) or ''rejected'' '
    '(returned to the Organiser to amend and resubmit).';

comment on column public.events.status is
    'Operational phase of the event lifecycle. ''planning'' while essential '
    'arrangements are still changing, ''confirmed'' once they are settled '
    '(arrangements and coordinator are then fixed), ''completed'' once the '
    'event is over. ''cancelled'' is reachable from any stage.';

commit;
