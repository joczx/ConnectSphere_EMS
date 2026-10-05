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
alter table public.events
    alter column status drop default;

alter table public.events
    alter column status type public.event_status
    using btrim(lower(status))::public.event_status;

alter table public.events
    alter column status set default 'planning'::public.event_status;

-- Nothing else references the old type: no function, view or other column uses
-- it. Dropping it is what stops 'approved' and 'under_review' coming back.
drop type public.request_status;

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
