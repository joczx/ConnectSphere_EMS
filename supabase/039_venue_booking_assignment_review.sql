-- Review permission follows the Venue Staff assignment on the event. The
-- authenticated backend verifies that assignment before reaching the
-- service-role database function; a separate global role check is redundant.

begin;

create or replace function public.review_venue_booking(
    p_booking_id uuid, p_outcome text, p_comments text
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    pending public.venue_booking_requests;
    decided public.venue_booking_requests;
    planned public.events;
    chosen public.venues;
    shortfalls text[];
    blocking jsonb;
    comments text := nullif(trim(coalesce(p_comments, '')), '');
    alert text;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if p_outcome is null or p_outcome not in ('approved', 'rejected') then
        return jsonb_build_object('error', 'Choose Approve or Reject.', 'status', 400);
    end if;
    if p_outcome = 'rejected' and comments is null then
        return jsonb_build_object(
            'error', 'Enter a reason for rejecting this request.',
            'errors', jsonb_build_object('comments', 'A reason is required when rejecting.'),
            'status', 400
        );
    end if;
    if comments is not null and length(comments) > 2000 then
        return jsonb_build_object('error', 'Comments must be 2000 characters or fewer.', 'status', 400);
    end if;

    select * into pending
    from public.venue_booking_requests
    where booking_id = p_booking_id;
    if not found or not exists (
        select 1
        from public.events
        where event_id = pending.event_id
          and venue_staff_id = auth.uid()
    ) then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    if pending.status <> 'submitted' then
        return jsonb_build_object(
            'error', 'This request has already been ' || pending.status || '.', 'status', 409
        );
    end if;

    if p_outcome = 'approved' then
        select * into chosen from public.venues where venue_id = pending.venue_id for share;
        if not found or chosen.deleted_at is not null then
            return jsonb_build_object(
                'error', 'This venue has been removed from the catalogue, so it can no longer be approved. Reject the request instead.',
                'status', 409
            );
        end if;

        if pending.event_id is not null then
            select * into planned from public.events where event_id = pending.event_id for share;
            if found then
                if planned.status is distinct from 'planning'::public.event_status then
                    return jsonb_build_object(
                        'error', 'This event is ' || planned.status || ', so its venue can no longer be approved. Reject the request instead.',
                        'status', 409
                    );
                end if;
                if pending.starts_at is distinct from planned.start_datetime
                    or pending.ends_at is distinct from planned.end_datetime
                    or (planned.capacity_needed is not null
                        and pending.attendance is distinct from planned.capacity_needed) then
                    return jsonb_build_object(
                        'error', 'The event''s date, time or attendance has changed since this was requested, so approving it would book the wrong period. Reject it so the Event Coordinator can request again.',
                        'status', 409
                    );
                end if;
                shortfalls := public.venue_shortfalls_for_event(chosen, planned);
                if cardinality(shortfalls) > 0 then
                    return jsonb_build_object(
                        'error', 'The event has changed since this was requested, and the venue no longer meets its requirements. Reject the request instead.',
                        'unmet_requirements', to_jsonb(shortfalls),
                        'status', 409
                    );
                end if;
            end if;
        end if;

        blocking := public.venue_booking_conflicts(
            pending.venue_id, pending.starts_at, pending.ends_at, pending.booking_id, true
        );
        if jsonb_array_length(blocking) > 0 then
            return jsonb_build_object(
                'error', 'This venue is already booked for an overlapping period, so this request can only be rejected.',
                'conflicts', blocking,
                'status', 409
            );
        end if;
    end if;

    begin
        update public.venue_booking_requests
        set status = p_outcome,
            reviewed_by = auth.uid(),
            reviewed_at = now(),
            review_comments = comments
        where booking_id = p_booking_id and status = 'submitted'
        returning * into decided;
    exception when exclusion_violation then
        return jsonb_build_object(
            'error', 'Another booking for this venue at an overlapping time was approved just now, so this request can only be rejected.',
            'conflicts', public.venue_booking_conflicts(
                pending.venue_id, pending.starts_at, pending.ends_at, pending.booking_id, true
            ),
            'status', 409
        );
    end;

    if decided.booking_id is null then
        return jsonb_build_object('error', 'Another member of Venue Staff decided this request first.', 'status', 409);
    end if;

    select venue_name into alert from public.venues where venue_id = decided.venue_id;
    alert := 'Your booking request for ' || coalesce(alert, 'the venue')
          || ' (' || decided.event_name || ') was ' || decided.status || '.'
          || case when comments is not null then ' Comments: ' || comments else '' end;

    begin
        insert into public.notification
            (recipient_id, venue_booking_id, notification_type, message)
        values
            (decided.requested_by, decided.booking_id, 'venue_booking_' || decided.status, alert);
    exception when foreign_key_violation or check_violation or not_null_violation then
        null;
    end;

    return jsonb_build_object('booking', to_jsonb(decided));
end;
$$;

create or replace function public.review_venue_booking_for_backend(
    p_actor_id uuid,
    p_booking_id uuid,
    p_outcome text,
    p_comments text
) returns jsonb
language plpgsql security definer set search_path = public as $$
begin
    if p_actor_id is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;

    perform set_config('request.jwt.claim.sub', p_actor_id::text, true);

    if not exists (
        select 1
        from public.venue_booking_requests booking
        join public.events event on event.event_id = booking.event_id
        where booking.booking_id = p_booking_id
          and event.venue_staff_id = p_actor_id
    ) then
        return jsonb_build_object(
            'error', 'Booking request not found or access unavailable.',
            'status', 404
        );
    end if;

    return public.review_venue_booking(p_booking_id, p_outcome, p_comments);
end;
$$;

revoke all on function public.review_venue_booking(uuid, text, text)
    from public, anon, authenticated;
grant execute on function public.review_venue_booking(uuid, text, text)
    to service_role;
revoke all on function public.review_venue_booking_for_backend(uuid, uuid, text, text)
    from public, anon, authenticated;
grant execute on function public.review_venue_booking_for_backend(uuid, uuid, text, text)
    to service_role;

commit;
