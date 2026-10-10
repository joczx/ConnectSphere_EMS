-- ConnectSphere EMS: Approve only what the event and the venue still are
-- Run this file in the Supabase SQL Editor. Apply after
-- 027_venue_booking_conflicts.sql.
--
-- Closes three gaps in review_venue_booking() found in review:
--
-- 1. THE EVENT MOVED AFTER THE REQUEST
--    A request copies the event's period and attendance when it is made. If
--    the coordinator then moves the event (a critical edit, which warns that it
--    "may invalidate a venue booking"), approval used to book the OLD period:
--    the requirements were rechecked against the event, but the period being
--    booked was never compared with it. Approval now refuses a request whose
--    period or attendance no longer matches its event. Rejecting it lets the
--    coordinator request again for the new time.
--
-- 2. THE EVENT OR VENUE CHANGED DURING APPROVAL
--    The event and venue were read, checked, and then the booking written, in
--    separate statements. An edit committing in between could slip past the
--    checks. Both rows are now read FOR SHARE, which holds off any edit to them
--    until the approval has committed, so what was checked is what was booked.
--    The lock lasts only as long as the approval itself.
--
-- 3. THE VENUE WAS DELETED
--    Venues are soft deleted, so a request for a deleted venue stayed in the
--    queue and could still be approved. Approval now refuses it, and the queue
--    says the venue was removed. Rejecting it remains possible.
--
-- Deleting a venue that has approved bookings ahead is refused by the venue
-- deletion endpoint (backend/app/routes/venues.py), alongside the scheduled
-- events it already checked.
--
-- TO REVERT
--     re-apply review_venue_booking() and visible_venue_bookings() from 027.

begin;

create or replace function public.visible_venue_bookings()
returns setof jsonb
language sql stable security definer set search_path = public as $$
    select to_jsonb(b) || jsonb_build_object(
        'venue_name', v.venue_name,
        -- A deleted venue keeps its row, so its requests stay readable; this
        -- is what lets the page say why one can no longer be approved.
        'venue_deleted', v.deleted_at is not null,
        'event_status', e.status,
        'requested_by_name', requester.name,
        'reviewed_by_name', reviewer.name,
        'current_shortfalls', case
            when b.status = 'submitted' and e.event_id is not null
            then to_jsonb(public.venue_shortfalls_for_event(v, e))
        end,
        -- Whether the event still has the period and headcount this request
        -- was made for. False means it moved, and approval would book the old
        -- time, so it is refused.
        'matches_event', case
            when e.event_id is null then null
            else b.starts_at = e.start_datetime
                 and b.ends_at = e.end_datetime
                 and (e.capacity_needed is null or b.attendance = e.capacity_needed)
        end,
        'conflicts', case
            when b.status in ('submitted', 'approved')
            then public.venue_booking_conflicts(b.venue_id, b.starts_at, b.ends_at, b.booking_id)
            else '[]'::jsonb
        end
    )
    from public.venue_booking_requests b
    join public.venues v on v.venue_id = b.venue_id
    left join public.events e on e.event_id = b.event_id
    left join public.users requester on requester.user_id = b.requested_by
    left join public.users reviewer on reviewer.user_id = b.reviewed_by
    where auth.uid() is not null
      and (public.has_booking_role('venue_staff') or b.requested_by = auth.uid())
    order by b.submitted_at desc;
$$;

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
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can approve or reject venue bookings.', 'status', 403);
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

    select * into pending from public.venue_booking_requests where booking_id = p_booking_id;
    if not found then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    if pending.status <> 'submitted' then
        return jsonb_build_object(
            'error', 'This request has already been ' || pending.status || '.', 'status', 409
        );
    end if;

    if p_outcome = 'approved' then
        -- FOR SHARE: no edit to this venue can commit until this approval has,
        -- so the venue checked below is the venue booked.
        select * into chosen from public.venues where venue_id = pending.venue_id for share;
        if not found or chosen.deleted_at is not null then
            return jsonb_build_object(
                'error', 'This venue has been removed from the catalogue, so it can no longer be approved. Reject the request instead.',
                'status', 409
            );
        end if;

        if pending.event_id is not null then
            -- And the same for the event: a critical edit waits for this.
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

revoke all on function public.visible_venue_bookings(), public.review_venue_booking(uuid, text, text)
    from public, anon;
grant execute on function public.visible_venue_bookings(), public.review_venue_booking(uuid, text, text)
    to authenticated;

commit;
