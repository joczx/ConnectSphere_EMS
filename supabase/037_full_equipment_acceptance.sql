-- Apply after 036. Equipment requests support full acceptance or rejection only.
begin;
create or replace function public.reserve_equipment_for_request(p_request_id integer, p_equipment_id integer, p_quantity integer)
returns jsonb language plpgsql security definer set search_path = public as $$
declare req public.equipment_request; ev public.events; stock public.equipment;
    booking public.equipment_reservations; event_key public.equipment_reservations.event_id%type; available bigint;
begin
    if auth.uid() is null then return jsonb_build_object('error','Please sign in again.','status',401); end if;
    if not public.can_reserve_equipment() then return jsonb_build_object('error','Only Technical Support Staff can reserve equipment.','status',403); end if;
    select * into req from public.equipment_request where equipment_request_id=p_request_id;
    if not found then return jsonb_build_object('error','Request not found.','status',404); end if;
    -- Shared write lock order: event, stock, request, reservation.
    select * into ev from public.events where event_id::text=req.event_id::text for update;
    if not found or ev.technical_support_id is distinct from auth.uid() then
        return jsonb_build_object('error','Only the assigned Technical Support Staff can reserve for this request.','status',403); end if;
    if ev.status::text <> 'planning' then return jsonb_build_object('error','Equipment can only be reserved during planning.','status',409); end if;
    select * into stock from public.equipment where equipment_id=p_equipment_id for update;
    if not found then return jsonb_build_object('error','Select valid equipment.','status',400); end if;
    select * into req from public.equipment_request where equipment_request_id=p_request_id for update;
    if req.event_id::text <> ev.event_id::text or req.status <> 'pending' then
        return jsonb_build_object('error','Only pending requests can be reserved. Refresh the page.','status',409); end if;
    if p_quantity is null or p_quantity < 1 or p_quantity <> req.quantity then
        return jsonb_build_object('error','Reserve the full requested quantity. Partial reservations are not supported.','status',400); end if;
    if lower(btrim(stock.equipment_type)) <> lower(btrim(req.equipment_type)) then
        return jsonb_build_object('error','Select equipment matching the requested type.','status',400); end if;
    if ev.start_datetime is null or ev.end_datetime is null or ev.end_datetime <= ev.start_datetime then
        return jsonb_build_object('error','Valid event dates are required.','status',409); end if;
    if exists(select 1 from public.equipment_reservations where equipment_request_id=p_request_id) then
        return jsonb_build_object('error','This request already has a reservation. Update or cancel it first.','status',409); end if;
    available := greatest(0, stock.total_quantity-public.equipment_peak(p_equipment_id,ev.start_datetime,ev.end_datetime));
    if p_quantity > available then return jsonb_build_object('error',format('Only %s available.',available),'status',409); end if;
    event_key := ev.event_id;
    insert into public.equipment_reservations(event_id,equipment_id,equipment_request_id,quantity,starts_at,ends_at,created_by)
    values(event_key,p_equipment_id,p_request_id,p_quantity,ev.start_datetime,ev.end_datetime,auth.uid()) returning * into booking;
    return jsonb_build_object('reservation',to_jsonb(booking),'equipment_request',to_jsonb(req),
        'message','Equipment reserved. The request is still pending; accept it separately.');
end;
$$;

create or replace function public.guard_equipment_request_acceptance() returns trigger
language plpgsql security definer set search_path = public as $$
declare ev public.events; booking public.equipment_reservations; model_type text;
begin
    if new.status = 'partially_accepted' then
        raise check_violation using message='Partial acceptance is not supported.';
    end if;
    if new.status = 'accepted' then
        select * into ev from public.events where event_id::text=new.event_id::text for update;
        if not public.can_reserve_equipment() or ev.technical_support_id is distinct from auth.uid() then
            raise insufficient_privilege using message='Only assigned Technical Support Staff can accept this request.'; end if;
        select * into booking from public.equipment_reservations where equipment_request_id=new.equipment_request_id for update;
        if not found or booking.event_id::text <> new.event_id::text or booking.equipment_id is distinct from new.equipment_id
           or booking.quantity is distinct from new.accepted_quantity or booking.starts_at > ev.start_datetime
           or booking.ends_at < ev.end_datetime or ev.start_datetime is null or ev.end_datetime is null then
            raise check_violation using message='Reserve equipment linked to this request before accepting it.'; end if;
        select equipment_type into model_type from public.equipment where equipment_id=booking.equipment_id;
        if lower(btrim(model_type)) is distinct from lower(btrim(new.equipment_type))
           or new.accepted_quantity < 1 or new.accepted_quantity > new.quantity
           or (new.status='accepted' and new.accepted_quantity <> new.quantity)
           or (new.status='partially_accepted' and new.accepted_quantity >= new.quantity) then
            raise check_violation using message='Acceptance must match the reserved type and quantity.'; end if;
    end if;
    return new;
end;
$$;
create or replace function public.review_equipment_request(p_request_id integer,p_outcome text,p_equipment_id integer,p_accepted_quantity integer,p_reason text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare req public.equipment_request; ev public.events; booking public.equipment_reservations; amount integer;
begin
    if auth.uid() is null then return jsonb_build_object('error','Please sign in again.','status',401); end if;
    select * into req from public.equipment_request where equipment_request_id=p_request_id;
    if not found then return jsonb_build_object('error','Request not found.','status',404); end if;
    select * into ev from public.events where event_id::text=req.event_id::text for update;
    if not public.can_reserve_equipment() or ev.technical_support_id is distinct from auth.uid() then
        return jsonb_build_object('error','Only the assigned Technical Support Staff can review this request.','status',403); end if;
    select * into req from public.equipment_request where equipment_request_id=p_request_id for update;
    if req.status <> 'pending' or req.event_id::text <> ev.event_id::text then
        return jsonb_build_object('error','This request has already been reviewed or changed.','status',409); end if;
    if p_outcome is null or p_outcome not in ('accepted','rejected') then
        return jsonb_build_object('error','Choose Accept or Reject. Partial acceptance is not supported.','status',400); end if;
    select * into booking from public.equipment_reservations where equipment_request_id=p_request_id for update;
    if p_outcome='rejected' then
        if nullif(btrim(p_reason),'') is null then return jsonb_build_object('error','Enter a reason for rejection.','status',400); end if;
        if booking.reservation_id is not null then return jsonb_build_object('error','Cancel the linked reservation before rejecting this request.','status',409); end if;
        amount := 0;
    else
        amount := case when p_outcome='accepted' then req.quantity else p_accepted_quantity end;
        if booking.reservation_id is null or booking.equipment_id is distinct from p_equipment_id
           or booking.quantity is distinct from amount or booking.event_id::text <> req.event_id::text
           or booking.starts_at > ev.start_datetime or booking.ends_at < ev.end_datetime then
            return jsonb_build_object('error','Reserve matching equipment linked to this request before accepting it.','status',409); end if;
        if amount is null or amount < 1 or amount > req.quantity or (p_outcome='partially_accepted' and amount>=req.quantity) then
            return jsonb_build_object('error','Accepted quantity must match a valid full or partial reservation.','status',400); end if;
    end if;
    update public.equipment_request set status=p_outcome, accepted_quantity=amount,
        equipment_id=case when p_outcome='rejected' then null else booking.equipment_id end,
        reviewed_by=auth.uid(),reviewed_at=now(),
        reason_for_rejection=case when p_outcome='rejected' then btrim(p_reason) else null end
    where equipment_request_id=p_request_id returning * into req;
    return jsonb_build_object('equipment_request',to_jsonb(req),'reservation',to_jsonb(booking),'message','Decision recorded.');
end;
$$;
create or replace function public.change_equipment_reservation(p_reservation_id uuid, p_quantity integer, p_cancel boolean)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
    saved public.equipment_reservations;
    linked public.equipment_request;
    stock integer;
    maximum bigint;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if p_cancel is null or (not p_cancel and (p_quantity is null or p_quantity <= 0)) then
        return jsonb_build_object('error', 'Quantity must be a positive whole number.', 'status', 400);
    end if;
    select * into saved from public.equipment_reservations
    where reservation_id = p_reservation_id and created_by = auth.uid();
    if not found then
        return jsonb_build_object('error', 'Reservation not found or access unavailable.', 'status', 404);
    end if;
    -- Match review/reserve lock order: event -> stock -> request -> reservation.
    perform 1 from public.events where event_id::text = saved.event_id::text for update;
    select total_quantity into stock from public.equipment
    where equipment_id = saved.equipment_id for update;
    if saved.equipment_request_id is not null then
        select * into linked from public.equipment_request
        where equipment_request_id = saved.equipment_request_id for update;
        if not found then
            return jsonb_build_object('error', 'Linked equipment request not found.', 'status', 409);
        end if;
    end if;
    select * into saved from public.equipment_reservations
    where reservation_id = p_reservation_id and created_by = auth.uid() for update;
    if not found then
        return jsonb_build_object('error', 'Reservation not found or access unavailable.', 'status', 404);
    end if;
    if p_cancel then
        if saved.equipment_request_id is not null then
            update public.equipment_request set status = case when linked.status = 'pending' then 'pending' else 'cancelled' end, accepted_quantity = 0
            where equipment_request_id = saved.equipment_request_id returning * into linked;
        end if;
        -- The cancelled request must not re-enter the legacy stock calculation.
        delete from public.equipment_reservations where reservation_id = p_reservation_id;
        return jsonb_build_object('cancelled', true, 'reservation_id', p_reservation_id,
            'equipment_request', case when saved.equipment_request_id is not null then to_jsonb(linked) else null end);
    end if;
    if saved.equipment_request_id is not null and p_quantity <> linked.quantity then
        return jsonb_build_object('error','A linked reservation must cover the full requested quantity.','status',409); end if;
    maximum := greatest(0, stock - public.equipment_peak(saved.equipment_id, saved.starts_at, saved.ends_at) + saved.quantity);
    if p_quantity > saved.quantity and p_quantity > maximum then
        return jsonb_build_object('error', format('Insufficient equipment: you can reserve at most %s for this event.', maximum),
            'maximum_quantity', maximum, 'status', 409);
    end if;
    update public.equipment_reservations set quantity = p_quantity
    where reservation_id = p_reservation_id returning * into saved;
    if saved.equipment_request_id is not null and linked.status <> 'pending' then
        update public.equipment_request set accepted_quantity = p_quantity,
            status = case when p_quantity < quantity then 'partially_accepted' else 'accepted' end
        where equipment_request_id = saved.equipment_request_id returning * into linked;
    end if;
    return jsonb_build_object('reservation', to_jsonb(saved),
        'equipment_request', case when saved.equipment_request_id is not null then to_jsonb(linked) else null end);
end;
$$;


notify pgrst, 'reload schema';
commit;
