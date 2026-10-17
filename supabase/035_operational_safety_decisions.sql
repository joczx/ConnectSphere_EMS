-- Safety Officer decisions. Apply after 034_operational_safety_reviews.sql.
begin;

create table public.operational_safety_decision (
    safety_decision_id bigint generated always as identity primary key,
    event_id integer not null references public.events(event_id) on delete cascade,
    safety_officer_id uuid not null references public.users(user_id),
    outcome text not null check (outcome in ('approved', 'rejected', 'changes_requested')),
    remarks text,
    affected_arrangements text[] not null default array[]::text[]
        check (affected_arrangements <@ array['venue', 'technical']::text[]),
    created_at timestamptz not null default clock_timestamp(),
    constraint safety_decision_remarks_required check (
        outcome = 'approved' or nullif(btrim(remarks), '') is not null
    ),
    constraint safety_decision_remarks_length check (
        remarks is null or length(remarks) <= 2000
    )
);
create index operational_safety_decision_event_idx
    on public.operational_safety_decision(event_id, created_at desc);

alter table public.events
    add column if not exists safety_rework_required boolean not null default false,
    add column if not exists safety_rework_requested_at timestamptz,
    add column if not exists safety_rework_arrangements text[] not null default array[]::text[],
    -- Written only by the safety decision workflow. It lets a previously
    -- approved safety review satisfy confirmation once registration is ready.
    add column if not exists safety_approved_at timestamptz;

alter table public.notification
    add column if not exists safety_decision_id bigint
        references public.operational_safety_decision(safety_decision_id) on delete cascade;
create index if not exists notification_safety_decision_idx
    on public.notification(recipient_id, created_at desc)
    where safety_decision_id is not null;

-- The prior safety check's base requirements still apply. After a Safety
-- Officer sends an event back, an actual update is required; where the officer
-- identified venue or technical arrangements, the replacement approval or
-- reservation must also be newer than that decision.
create or replace function public.event_safety_check_blockers(p_event public.events)
returns text[] language plpgsql volatile security definer set search_path = public as $$
declare blockers text[]; requirements text[] := coalesce(p_event.safety_rework_arrangements, array[]::text[]);
begin
    blockers := public.event_confirmation_blockers(p_event);
    blockers := array_remove(blockers, 'An Event Coordinator must be assigned.');
    blockers := array_remove(blockers, 'The Event Coordinator must confirm registration readiness.');
    if p_event.safety_rework_required then
        blockers := array_append(blockers, 'Address the requested safety changes before another safety check.');
    end if;
    if 'venue' = any(requirements) and not exists (
        select 1 from public.venue_booking_requests b
        join public.venues v using (venue_id)
        where b.event_id = p_event.event_id and b.status = 'approved'
          and b.reviewed_at >= p_event.safety_rework_requested_at
          and b.starts_at = p_event.start_datetime and b.ends_at = p_event.end_datetime
          and (p_event.capacity_needed is null or b.attendance = p_event.capacity_needed)
          and v.deleted_at is null
          and cardinality(public.venue_shortfalls_for_event(v, p_event)) = 0
    ) then
        blockers := array_append(blockers, 'The affected venue arrangement must be reviewed and confirmed again.');
    end if;
    if 'technical' = any(requirements) and not exists (
        select 1 from public.equipment_reservations r
        where r.event_id = p_event.event_id
          and r.created_at >= p_event.safety_rework_requested_at
    ) then
        blockers := array_append(blockers, 'The affected technical arrangement must be reviewed and confirmed again.');
    end if;
    return coalesce(blockers, array[]::text[]);
end;
$$;

-- An arrangement update is the acknowledgement that requested work has been
-- addressed. The timestamp checks above still make an affected venue or
-- technical arrangement obtain a fresh confirmation before it can re-enter
-- Pending Safety Checks.
create or replace function public.refresh_arranged_event()
returns trigger language plpgsql security definer set search_path = public as $$
declare previous_id text; next_id text;
begin
    if TG_OP <> 'INSERT' then previous_id := old.event_id::text; end if;
    if TG_OP <> 'DELETE' then next_id := new.event_id::text; end if;
    -- This trigger is a trusted workflow write. A changed arrangement must be
    -- checked by Safety again, even if the event was previously confirmed.
    perform set_config('connectsphere.safety_workflow', 'true', true);
    update public.events set updated_at = clock_timestamp(), safety_rework_required = false,
        safety_approved_at = null
    where event_id::text in (previous_id, next_id)
      and status in ('planning', 'pending_safety_checks', 'confirmed');
    return null;
end;
$$;

create or replace function public.guard_event_lifecycle()
returns trigger language plpgsql security definer set search_path = public as $$
declare blockers text[];
begin
    if TG_OP = 'INSERT' then
        new.registration_ready := false;
        if new.status <> 'planning' then
            raise check_violation using message = 'New operational events start in Planning.';
        end if;
    else
        -- The rework/approval fields are workflow state, not arrangement data.
        -- RLS lets assigned users edit event details, so refusing direct writes
        -- here closes the otherwise available PostgREST bypass. Trusted RPCs
        -- and arrangement triggers set this transaction-local flag themselves.
        if (new.safety_rework_required is distinct from old.safety_rework_required
            or new.safety_rework_requested_at is distinct from old.safety_rework_requested_at
            or new.safety_rework_arrangements is distinct from old.safety_rework_arrangements
            or new.safety_approved_at is distinct from old.safety_approved_at)
            and current_setting('connectsphere.safety_workflow', true) is distinct from 'true' then
            raise insufficient_privilege using message = 'Safety workflow fields can only be changed by the safety workflow.';
        end if;
        if old.status = 'confirmed' and
            (to_jsonb(new) - array['status', 'registration_ready', 'updated_at',
                                   'safety_rework_required', 'safety_rework_requested_at',
                                   'safety_rework_arrangements', 'safety_approved_at']) is distinct from
            (to_jsonb(old) - array['status', 'registration_ready', 'updated_at',
                                   'safety_rework_required', 'safety_rework_requested_at',
                                   'safety_rework_arrangements', 'safety_approved_at']) then
            raise check_violation using message = 'Confirmed event arrangements cannot be edited.';
        end if;
        if new.registration_ready is distinct from old.registration_ready
            and auth.uid() is distinct from old.event_coordinator_id then
            raise insufficient_privilege using message = 'Only the assigned coordinator can confirm registration readiness.';
        end if;
        if new.registration_needs is distinct from old.registration_needs then
            new.registration_ready := false;
        end if;
        if (to_jsonb(new) - array['status', 'updated_at', 'registration_ready',
                                  'safety_rework_required', 'safety_rework_requested_at',
                                  'safety_rework_arrangements', 'safety_approved_at'])
                is distinct from
                (to_jsonb(old) - array['status', 'updated_at', 'registration_ready',
                                       'safety_rework_required', 'safety_rework_requested_at',
                                       'safety_rework_arrangements', 'safety_approved_at']) then
            -- A real event-detail change addresses a general change request,
            -- but always invalidates a previous safety approval.
            new.safety_rework_required := false;
            new.safety_approved_at := null;
        end if;
        if old.status in ('completed', 'cancelled') and new is distinct from old then
            raise check_violation using message = 'Completed and cancelled events cannot be changed.';
        end if;
        if new.status is distinct from old.status and not (
            (old.status = 'planning' and new.status = 'cancelled')
            or (old.status = 'pending_safety_checks' and new.status in ('planning', 'confirmed', 'cancelled'))
            or (old.status = 'confirmed' and new.status in ('planning', 'completed', 'cancelled'))
        ) then
            raise check_violation using message = 'Invalid event status transition.';
        end if;
        if old.status = 'pending_safety_checks' and new.status = 'confirmed' and not exists (
            select 1 from public.operational_safety_decision d
            where d.event_id = old.event_id and d.safety_officer_id = auth.uid()
              and d.outcome = 'approved' and d.created_at >= old.updated_at
        ) then
            raise insufficient_privilege using message = 'A Safety Officer approval is required before confirming this event.';
        end if;
        if new.status = 'cancelled' and old.status <> 'cancelled'
            and auth.uid() is distinct from old.event_coordinator_id
            and auth.uid() is distinct from old.event_organiser_id then
            raise insufficient_privilege using message = 'Only the organiser or coordinator can cancel an event.';
        end if;
        if new.status = 'completed' and old.status <> 'completed'
            and (new.end_datetime is null or new.end_datetime > now()) then
            raise check_violation using message = 'An event cannot complete before its end time.';
        end if;
    end if;
    if new.status in ('planning', 'pending_safety_checks') then
        blockers := public.event_safety_check_blockers(new);
        if cardinality(blockers) > 0 then
            new.status := 'planning'::public.event_status;
        elsif new.safety_approved_at is not null
            and cardinality(public.event_confirmation_blockers(new)) = 0 then
            new.status := 'confirmed'::public.event_status;
        else
            new.status := 'pending_safety_checks'::public.event_status;
        end if;
    elsif new.status = 'confirmed' and cardinality(public.event_confirmation_blockers(new)) > 0 then
        -- Safety approval remains recorded, but no longer bypasses the
        -- established registration-readiness and full-arrangement checks.
        new.status := case when cardinality(public.event_safety_check_blockers(new)) = 0
                           then 'pending_safety_checks'::public.event_status
                           else 'planning'::public.event_status end;
    end if;
    if TG_OP = 'UPDATE' then new.updated_at := clock_timestamp(); end if;
    return new;
end;
$$;

create or replace function public.record_safety_decision(
    p_event_id integer, p_outcome text, p_remarks text, p_affected_arrangements text[]
) returns jsonb language plpgsql security definer set search_path = public as $$
declare planned public.events; saved public.operational_safety_decision; outcome text := lower(btrim(coalesce(p_outcome, '')));
        remarks text := nullif(btrim(coalesce(p_remarks, '')), ''); affected text[] := coalesce(p_affected_arrangements, array[]::text[]); note text;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_safety_officer_role() then return jsonb_build_object('error', 'Only Safety Officers can record operational safety decisions.', 'status', 403); end if;
    if outcome not in ('approved', 'rejected', 'changes_requested') then return jsonb_build_object('error', 'Choose Approve, Reject, or Request changes.', 'status', 400); end if;
    if outcome <> 'approved' and remarks is null then return jsonb_build_object('error', 'Remarks are required when rejecting or requesting changes.', 'status', 400); end if;
    if remarks is not null and length(remarks) > 2000 then return jsonb_build_object('error', 'Remarks must be 2000 characters or fewer.', 'status', 400); end if;
    if not (affected <@ array['venue', 'technical']::text[]) then return jsonb_build_object('error', 'Affected arrangements must be venue or technical.', 'status', 400); end if;

    select * into planned from public.events where event_id = p_event_id for update;
    if not found or planned.status <> 'pending_safety_checks' then return jsonb_build_object('error', 'Event not found or no longer awaiting safety checks.', 'status', 404); end if;
    if outcome = 'approved' and cardinality(public.event_safety_check_blockers(planned)) > 0 then
        return jsonb_build_object('error', 'The event arrangements changed and must be completed before approval.', 'status', 409);
    end if;
    if planned.event_coordinator_id is null then return jsonb_build_object('error', 'Assign an Event Coordinator before recording a safety decision.', 'status', 409); end if;

    insert into public.operational_safety_decision (event_id, safety_officer_id, outcome, remarks, affected_arrangements)
    values (planned.event_id, auth.uid(), outcome, remarks, affected) returning * into saved;
    perform set_config('connectsphere.safety_workflow', 'true', true);
    if outcome = 'approved' then
        update public.events set status = 'confirmed', safety_rework_required = false,
            safety_rework_arrangements = array[]::text[], safety_approved_at = saved.created_at
        where event_id = planned.event_id returning * into planned;
        note := case when planned.status = 'confirmed' then 'Safety arrangements approved. The event is confirmed.'
                     else 'Safety arrangements approved. The event will be confirmed once its remaining readiness checks are complete.' end;
    else
        update public.events set status = 'planning', safety_rework_required = true,
            safety_rework_requested_at = saved.created_at, safety_rework_arrangements = affected,
            safety_approved_at = null
        where event_id = planned.event_id returning * into planned;
        note := case when outcome = 'rejected' then 'Safety arrangements rejected. Address the remarks before proceeding.'
                     else 'Safety changes requested. Address the remarks before proceeding.' end;
    end if;
    -- Recording the safety decision is more important than a notification row.
    -- This matches the venue-review workflow: a missing profile/notification
    -- constraint must not make the officer lose a successfully made decision.
    begin
        insert into public.notification (recipient_id, safety_decision_id, notification_type, message)
        values (planned.event_coordinator_id, saved.safety_decision_id, 'operational_safety_' || outcome,
            'Safety decision for ' || coalesce(planned.event_name, 'your event') || ': ' || note
            || case when remarks is null then '' else ' Remarks: ' || remarks end);
    exception when foreign_key_violation or check_violation or not_null_violation then
        null;
    end;
    return jsonb_build_object('event', to_jsonb(planned), 'decision', to_jsonb(saved), 'message', note);
end;
$$;

revoke all on table public.operational_safety_decision from anon, authenticated;
revoke all on function public.event_safety_check_blockers(public.events), public.refresh_arranged_event(),
    public.record_safety_decision(integer, text, text, text[]) from public, anon, authenticated;
grant execute on function public.record_safety_decision(integer, text, text, text[]) to authenticated;

notify pgrst, 'reload schema';
commit;
