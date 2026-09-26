-- Apply after 010 and 011, against the existing equipment_request catalogue schema.
begin;
alter table public.equipment_request
    add column accepted_quantity integer,
    add column reviewed_at timestamptz,
    add constraint equipment_request_accepted_quantity_check
        check (accepted_quantity >= 0 and accepted_quantity <= quantity);

-- Preserve the stock commitments of previously reviewed requests.
update public.equipment_request set accepted_quantity = quantity
where status in ('accepted', 'partially_accepted', 'in_progress', 'completed');
update public.equipment_request set accepted_quantity = 0 where status = 'rejected';

create or replace function public.equipment_peak(p_equipment_id integer, p_start timestamptz, p_end timestamptz)
returns bigint language sql stable set search_path = public as $$
    with commitments as (
        select equipment_id, quantity, starts_at, ends_at from public.equipment_reservations
        union all
        select r.equipment_id, coalesce(r.accepted_quantity, r.quantity),
            coalesce(to_jsonb(e)->>'start_datetime', to_jsonb(e)->>'starts_at')::timestamptz,
            coalesce(to_jsonb(e)->>'end_datetime', to_jsonb(e)->>'ends_at')::timestamptz
        from public.equipment_request r join public.events e on e.event_id = r.event_id
        where r.status in ('accepted', 'in_progress', 'partially_accepted', 'completed')
    ), changes as (
        select greatest(starts_at, p_start) as moment, quantity::bigint as delta
        from commitments
        where equipment_id = p_equipment_id and starts_at < p_end and ends_at > p_start
        union all
        select least(ends_at, p_end), -quantity::bigint
        from commitments
        where equipment_id = p_equipment_id and starts_at < p_end and ends_at > p_start
    ), usage as (
        select sum(sum(delta)) over (order by moment) as used from changes group by moment
    ) select coalesce(max(used), 0)::bigint from usage;
$$;


create function public.equipment_request_review_queue() returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(to_jsonb(r) || jsonb_build_object(
        'event_name', e.event_name) order by e.event_name, r.requested_at), '[]'::jsonb)
    from public.equipment_request r join public.events e on e.event_id = r.event_id
    where auth.uid() is not null
      and to_jsonb(e)->>'technical_support_id' = auth.uid()::text;
$$;

create function public.review_equipment_request(
    p_request_id integer, p_outcome text, p_equipment_id integer,
    p_accepted_quantity integer, p_reason text
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    saved public.equipment_request;
    ev jsonb;
    item public.equipment;
    starts timestamptz;
    ends timestamptz;
    amount integer;
    available bigint;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if p_outcome is null or p_outcome not in ('accepted', 'rejected', 'partially_accepted') then
        return jsonb_build_object('error', 'Choose a valid review outcome.', 'status', 400);
    end if;
    select * into saved from public.equipment_request where equipment_request_id = p_request_id;
    if not found then return jsonb_build_object('error', 'Request not found.', 'status', 404); end if;
    -- Match the reservation functions' event -> stock -> request lock order.
    select to_jsonb(e) into ev from public.events e where e.event_id = saved.event_id for update;
    if ev is null or (ev->>'technical_support_id') is distinct from auth.uid()::text then
        return jsonb_build_object('error', 'Only the assigned technical support staff can review this request.', 'status', 403);
    end if;
    if p_outcome <> 'rejected' then
        select * into item from public.equipment where equipment_id = p_equipment_id for update;
        if not found then return jsonb_build_object('error', 'Select equipment to reserve.', 'status', 400); end if;
    end if;
    select * into saved from public.equipment_request where equipment_request_id = p_request_id for update;
    if not found then return jsonb_build_object('error', 'Request not found.', 'status', 404); end if;
    if saved.event_id::text <> (ev->>'event_id') or saved.status <> 'pending' then
        return jsonb_build_object('error', 'This request has changed or already been reviewed. Refresh the page.', 'status', 409);
    end if;
    if p_outcome = 'rejected' then
        if nullif(btrim(p_reason), '') is null then
            return jsonb_build_object('error', 'Enter a reason for rejection.', 'status', 400);
        end if;
        amount := 0;
    else
        if lower(btrim(item.equipment_type)) <> lower(btrim(saved.equipment_type)) then
            return jsonb_build_object('error', 'Select equipment matching the requested type.', 'status', 400);
        end if;
        amount := case when p_outcome = 'accepted' then saved.quantity else p_accepted_quantity end;
        if amount is null or amount < 1 or (p_outcome = 'partially_accepted' and amount >= saved.quantity) then
            return jsonb_build_object('error', 'Partial acceptance must be greater than zero and less than the requested quantity.', 'status', 400);
        end if;
        starts := coalesce(ev->>'start_datetime', ev->>'starts_at')::timestamptz;
        ends := coalesce(ev->>'end_datetime', ev->>'ends_at')::timestamptz;
        if starts is null or ends is null or ends <= starts then
            return jsonb_build_object('error', 'Set valid event dates before reserving equipment.', 'status', 400);
        end if;
        available := greatest(0, item.total_quantity - public.equipment_peak(item.equipment_id, starts, ends));
        if amount > available then
            return jsonb_build_object('error', format('Only %s available. Reduce the accepted quantity or reject the request.', available), 'status', 409);
        end if;
    end if;
    -- Accepted requests already participate in equipment_peak. Do not also
    -- insert a reservation row, which would count this commitment twice.
    update public.equipment_request set status = p_outcome, accepted_quantity = amount,
        equipment_id = case when p_outcome = 'rejected' then null else p_equipment_id end,
        reviewed_by = auth.uid(), reviewed_at = now(),
        reason_for_rejection = case when p_outcome = 'rejected' then btrim(p_reason) else null end
    where equipment_request_id = p_request_id returning * into saved;
    return jsonb_build_object('equipment_request', to_jsonb(saved), 'message', 'Equipment request reviewed successfully.');
end;
$$;

-- Accepted request commitments must keep their event dates until released.
create function public.guard_reviewed_equipment_event() returns trigger
language plpgsql security definer set search_path = public as $$
begin
    if exists (select 1 from public.equipment_request r where r.event_id = old.event_id
        and r.status in ('accepted', 'partially_accepted', 'in_progress', 'completed'))
        and (coalesce(to_jsonb(new)->>'start_datetime', to_jsonb(new)->>'starts_at')
             is distinct from coalesce(to_jsonb(old)->>'start_datetime', to_jsonb(old)->>'starts_at')
          or coalesce(to_jsonb(new)->>'end_datetime', to_jsonb(new)->>'ends_at')
             is distinct from coalesce(to_jsonb(old)->>'end_datetime', to_jsonb(old)->>'ends_at')) then
        raise exception 'Release accepted equipment requests before changing event dates.';
    end if;
    return new;
end;
$$;
create trigger guard_reviewed_equipment_event before update on public.events
for each row execute function public.guard_reviewed_equipment_event();

-- Public table writes must not bypass the review RPC's assignment and stock checks.
create function public.guard_equipment_request_review() returns trigger
language plpgsql set search_path = public as $$
begin
    if current_user in ('authenticated', 'anon') then
        if tg_op = 'INSERT' then
            if new.status <> 'pending' or new.accepted_quantity is not null
                or new.reviewed_by is not null or new.reviewed_at is not null then
                raise exception 'Use the equipment review action to record a decision.';
            end if;
        elsif tg_op = 'DELETE' then
            if old.status <> 'pending' then raise exception 'Reviewed requests cannot be deleted directly.'; end if;
            return old;
        elsif old.status <> 'pending' or new.status <> 'pending'
            or new.accepted_quantity is distinct from old.accepted_quantity
            or new.reviewed_by is distinct from old.reviewed_by
            or new.reviewed_at is distinct from old.reviewed_at then
            raise exception 'Use the equipment review action to record a decision.';
        end if;
    end if;
    return new;
end;
$$;
create trigger guard_equipment_request_review before insert or update or delete on public.equipment_request
for each row execute function public.guard_equipment_request_review();

revoke all on function public.equipment_request_review_queue(),
    public.review_equipment_request(integer,text,integer,integer,text),
    public.guard_reviewed_equipment_event(), public.guard_equipment_request_review() from public, anon, authenticated;
grant execute on function public.equipment_request_review_queue(),
    public.review_equipment_request(integer,text,integer,integer,text) to authenticated;
notify pgrst, 'reload schema';
commit;
