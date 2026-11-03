-- Remove obsolete registration-arrangement text from requests and events.
-- Requires 053_remove_registration_readiness.sql first.
-- Existing values in these two columns are permanently removed. No CASCADE.
begin;
do $$
begin
    if exists (select 1 from information_schema.columns where table_schema='public'
        and table_name='events' and column_name='registration_ready') then
        raise exception 'Apply 053_remove_registration_readiness.sql before removing registration_needs.';
    end if;
end;
$$;

create or replace function public.guard_event_lifecycle()
returns trigger language plpgsql security definer set search_path = public as $$
declare
    blockers text[];
    change_request_workflow boolean := coalesce(current_setting('connectsphere.change_request_workflow', true), '') = 'true';
    non_important_workflow boolean := coalesce(current_setting('connectsphere.change_request_importance', true), '') = 'non_important';
    safety_submission boolean := coalesce(current_setting('connectsphere.safety_submission', true), '') = 'true';
begin
    if TG_OP = 'INSERT' then
        if new.status <> 'planning' then
            raise check_violation using message = 'New operational events start in Planning.';
        end if;
    else
        if (new.safety_rework_required is distinct from old.safety_rework_required
            or new.safety_rework_requested_at is distinct from old.safety_rework_requested_at
            or new.safety_rework_arrangements is distinct from old.safety_rework_arrangements
            or new.safety_approved_at is distinct from old.safety_approved_at)
            and current_setting('connectsphere.safety_workflow', true) is distinct from 'true' then
            raise insufficient_privilege using message = 'Safety workflow fields can only be changed by the safety workflow.';
        end if;
        if old.status = 'confirmed' and not change_request_workflow and
            (to_jsonb(new) - array['registration_opens_at', 'registration_closes_at',
                                   'waiting_list_enabled', 'status', 'updated_at',
                                   'safety_rework_required', 'safety_rework_requested_at',
                                   'safety_rework_arrangements', 'safety_approved_at']) is distinct from
            (to_jsonb(old) - array['registration_opens_at', 'registration_closes_at',
                                   'waiting_list_enabled', 'status', 'updated_at',
                                   'safety_rework_required', 'safety_rework_requested_at',
                                   'safety_rework_arrangements', 'safety_approved_at']) then
            raise check_violation using message = 'Confirmed event arrangements cannot be edited.';
        end if;
        if (to_jsonb(new) - array['registration_opens_at', 'registration_closes_at',
                                  'waiting_list_enabled', 'status', 'updated_at',
                                  'safety_rework_required', 'safety_rework_requested_at',
                                  'safety_rework_arrangements', 'safety_approved_at']) is distinct from
           (to_jsonb(old) - array['registration_opens_at', 'registration_closes_at',
                                  'waiting_list_enabled', 'status', 'updated_at',
                                  'safety_rework_required', 'safety_rework_requested_at',
                                  'safety_rework_arrangements', 'safety_approved_at'])
            and not (change_request_workflow and non_important_workflow) then
            new.safety_rework_required := false;
            new.safety_approved_at := null;
        end if;
        if old.status in ('completed', 'cancelled') and new is distinct from old then
            raise check_violation using message = 'Completed and cancelled events cannot be changed.';
        end if;
        if new.status is distinct from old.status and not (
            (old.status = 'planning' and new.status = 'cancelled')
            or (old.status = 'planning' and new.status = 'pending_safety_checks' and safety_submission)
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
    if TG_OP = 'UPDATE' and change_request_workflow then
        new.status := old.status;
    elsif new.status in ('planning', 'pending_safety_checks') then
        blockers := public.event_safety_check_blockers(new);
        if cardinality(blockers) > 0 then
            new.status := 'planning'::public.event_status;
        elsif new.safety_approved_at is not null
            and cardinality(public.event_confirmation_blockers(new)) = 0 then
            new.status := 'confirmed'::public.event_status;
        end if;
    elsif new.status = 'confirmed' and cardinality(public.event_confirmation_blockers(new)) > 0 then
        new.status := case when new.safety_approved_at is not null
                                and cardinality(public.event_safety_check_blockers(new)) = 0
                           then 'pending_safety_checks'::public.event_status
                           else 'planning'::public.event_status end;
    end if;
    if TG_OP = 'UPDATE' then new.updated_at := clock_timestamp(); end if;
    return new;
end;
$$;

CREATE OR REPLACE FUNCTION public.create_event_from_approved_request()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    insert into public.events (
        event_request_id,
        event_name,
        purpose,
        description,
        start_datetime,
        end_datetime,
        capacity_needed,
        room_layout,
        required_facilities,
        need_wheelchair_accessibility,
        need_blind_accessibility,
        equipment_requirements,
        status,
        event_organiser_id,
        event_coordinator_id
    )
    values (
        new.event_request_id,
        new.event_name,
        new.purpose,
        new.description,
        new.start_datetime,
        new.end_datetime,
        new.capacity_needed,
        new.room_layout,
        coalesce(
            new.required_facilities,
            '{}'::public.facility[]
        ),
        new.need_wheelchair_accessibility,
        new.need_blind_accessibility,
        coalesce(
            new.equipment_requirements,
            '[]'::jsonb
        ),
        'planning',
        new.event_organiser_id,
        new.event_coordinator_id
    )
    on conflict (event_request_id) do nothing;

    return new;
end;
$function$;

alter table public.events drop column if exists registration_needs;
alter table public.event_request drop column if exists registration_needs;
notify pgrst, 'reload schema';
commit;
