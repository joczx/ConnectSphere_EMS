-- ConnectSphere EMS: A venue cannot be double-booked
-- Run this file in the Supabase SQL Editor. Apply after
-- 026_review_venue_bookings.sql.
--
-- Backs the "identify overlapping or conflicting venue bookings" story.
--
-- WHAT MAKES A VENUE UNAVAILABLE
-- Only an APPROVED booking. Pending requests may overlap one another freely:
-- several coordinators can ask for the same venue at the same time, and it is
-- the first approval that settles it. Once one is approved, the venue is
-- unavailable for that period, so:
--   * a new request for an overlapping period is refused;
--   * an overlapping pending request can no longer be approved, only rejected.
--
-- WHAT COUNTS AS OVERLAPPING
-- Two periods overlap when they share any moment. Periods are half-open,
-- [start, end), so a booking that ends at 18:00 does not block one that starts
-- at 18:00. The venue's setup and turnaround minutes are not added: the story
-- defines unavailability as the period of the booking itself.
--
-- WHY A CONSTRAINT AS WELL AS THE CHECKS
-- The checks in submit_venue_booking() and review_venue_booking() give a clear
-- answer naming the conflict. They cannot, on their own, stop two staff members
-- approving two overlapping requests at the same moment: each would check,
-- find nothing approved yet, and approve. The exclusion constraint below makes
-- that second approval fail inside the database, whatever the timing.
--
-- WHO SEES WHAT ABOUT ANOTHER BOOKING
-- A conflict always shows its period, because that is what the user needs to
-- act on. The event it belongs to is shown only to Venue Staff and to the
-- coordinator who made that request; anyone else sees "another event".
-- Pending requests are shown only to Venue Staff and their own requester, since
-- they do not make a venue unavailable to anyone else.
--
-- BEFORE RUNNING
-- The constraint will refuse to be created if two approved bookings already
-- overlap. Check with:
--     select a.booking_id, b.booking_id
--     from public.venue_booking_requests a
--     join public.venue_booking_requests b
--       on a.venue_id = b.venue_id and a.booking_id < b.booking_id
--      and tstzrange(a.starts_at, a.ends_at) && tstzrange(b.starts_at, b.ends_at)
--     where a.status = 'approved' and b.status = 'approved';
--
-- TO REVERT
--     alter table public.venue_booking_requests drop constraint venue_booking_no_double_booking;
--     drop function if exists public.venue_unavailability(timestamptz, timestamptz);
--     drop function if exists public.venue_booking_conflicts(uuid, timestamptz, timestamptz, uuid, boolean);
--     drop function if exists public.venue_booking_summary(public.venue_booking_requests);
--     then re-apply submit_venue_booking() from 025 and review_venue_booking()
--     and visible_venue_bookings() from 026.

begin;

-- 1. The hard guarantee ---------------------------------------------------

-- btree_gist lets one exclusion constraint compare a uuid for equality and a
-- time range for overlap together.
create extension if not exists btree_gist with schema extensions;

alter table public.venue_booking_requests
    add constraint venue_booking_no_double_booking
    exclude using gist (
        venue_id with =,
        tstzrange(starts_at, ends_at, '[)') with &&
    )
    where (status = 'approved');

-- 2. Describing another booking without oversharing ----------------------

create or replace function public.venue_booking_summary(b public.venue_booking_requests)
returns jsonb
language sql stable security definer set search_path = public as $$
    select jsonb_build_object(
        'booking_id', b.booking_id,
        'venue_id', b.venue_id,
        'status', b.status,
        'starts_at', b.starts_at,
        'ends_at', b.ends_at
    ) || case
        when public.has_booking_role('venue_staff') or b.requested_by = auth.uid()
        then jsonb_build_object('event_id', b.event_id, 'event_name', b.event_name, 'visible', true)
        else jsonb_build_object('visible', false)
    end;
$$;

-- 3. Finding conflicts ----------------------------------------------------

-- Bookings for one venue that overlap a period, earliest first. Approved ones
-- make the venue unavailable; pending ones are competing requests, returned
-- only to those allowed to see them, and only when p_approved_only is false.
create or replace function public.venue_booking_conflicts(
    p_venue_id uuid,
    p_starts timestamptz,
    p_ends timestamptz,
    p_exclude uuid default null,
    p_approved_only boolean default false
) returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(public.venue_booking_summary(b) order by b.starts_at), '[]'::jsonb)
    from public.venue_booking_requests b
    where auth.uid() is not null
      and b.venue_id = p_venue_id
      and b.booking_id is distinct from p_exclude
      and tstzrange(b.starts_at, b.ends_at, '[)') && tstzrange(p_starts, p_ends, '[)')
      and (
          b.status = 'approved'
          or (not p_approved_only
              and b.status = 'submitted'
              and (public.has_booking_role('venue_staff') or b.requested_by = auth.uid()))
      );
$$;

-- Every approved booking overlapping a period, across all venues. One call
-- marks a whole page of search results, rather than one call per venue.
create or replace function public.venue_unavailability(p_starts timestamptz, p_ends timestamptz)
returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(public.venue_booking_summary(b) order by b.starts_at), '[]'::jsonb)
    from public.venue_booking_requests b
    where auth.uid() is not null
      and b.status = 'approved'
      and tstzrange(b.starts_at, b.ends_at, '[)') && tstzrange(p_starts, p_ends, '[)');
$$;

-- 4. Each request carries its conflicts ----------------------------------

-- As in 026, plus "conflicts": for a pending request, what blocks it and what
-- competes with it; for an approved one, the pending requests it now blocks.
create or replace function public.visible_venue_bookings()
returns setof jsonb
language sql stable security definer set search_path = public as $$
    select to_jsonb(b) || jsonb_build_object(
        'venue_name', v.venue_name,
        'event_status', e.status,
        'requested_by_name', requester.name,
        'reviewed_by_name', reviewer.name,
        'current_shortfalls', case
            when b.status = 'submitted' and e.event_id is not null
            then to_jsonb(public.venue_shortfalls_for_event(v, e))
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

-- 5. Requesting: refused when the venue is already booked ----------------

-- As in 025, with the availability check added before the insert.
create or replace function public.submit_venue_booking(p_booking jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    saved public.venue_booking_requests;
    planned public.events;
    chosen public.venues;
    shortfalls text[];
    blocking jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator') then
        return jsonb_build_object('error', 'Only Event Coordinators can submit venue bookings.', 'status', 403);
    end if;
    if jsonb_typeof(p_booking) is distinct from 'object'
        or not (p_booking ?& array['venue_id','event_id','event_name','starts_at','ends_at','attendance','venue_requirements'])
        or jsonb_typeof(p_booking->'attendance') is distinct from 'number'
        or jsonb_typeof(p_booking->'event_id') is distinct from 'number'
        or jsonb_typeof(p_booking->'event_name') is distinct from 'string'
        or jsonb_typeof(p_booking->'venue_requirements') is distinct from 'string'
        or (p_booking->>'attendance') !~ '^[0-9]+$'
        or (p_booking->>'event_id') !~ '^[0-9]+$'
        or (p_booking->>'starts_at') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$'
        or (p_booking->>'ends_at') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' then
        return jsonb_build_object('error', 'Provide all required booking details.', 'status', 400);
    end if;
    if (p_booking->>'starts_at')::timestamptz <= now() then
        return jsonb_build_object('error', 'Start must be in the future.', 'status', 400);
    end if;

    select * into planned from public.events
    where event_id = (p_booking->>'event_id')::integer;

    if not found or planned.event_coordinator_id is distinct from auth.uid() then
        return jsonb_build_object(
            'error', 'That event is not one you are planning.', 'status', 404
        );
    end if;
    if planned.status is distinct from 'planning'::public.event_status then
        return jsonb_build_object(
            'error', 'A venue can only be requested while the event is in planning.',
            'status', 409
        );
    end if;

    select * into chosen from public.venues
    where venue_id = (p_booking->>'venue_id')::uuid and deleted_at is null;

    if not found then
        return jsonb_build_object('error', 'Select an existing venue.', 'status', 400);
    end if;

    if (p_booking->>'starts_at')::timestamptz is distinct from planned.start_datetime
        or (p_booking->>'ends_at')::timestamptz is distinct from planned.end_datetime
        or (planned.capacity_needed is not null
            and (p_booking->>'attendance')::integer is distinct from planned.capacity_needed) then
        return jsonb_build_object(
            'error', 'These booking details no longer match the event. Reload the '
                     'event and try again.',
            'status', 409
        );
    end if;

    shortfalls := public.venue_shortfalls_for_event(chosen, planned);
    if cardinality(shortfalls) > 0 then
        return jsonb_build_object(
            'error', 'This venue does not meet the requirements recorded for this event.',
            'unmet_requirements', to_jsonb(shortfalls),
            'status', 409
        );
    end if;

    -- Only an approved booking makes the venue unavailable. Overlapping
    -- pending requests are allowed: none of them has the venue yet.
    blocking := public.venue_booking_conflicts(
        chosen.venue_id, planned.start_datetime, planned.end_datetime, null, true
    );
    if jsonb_array_length(blocking) > 0 then
        return jsonb_build_object(
            'error', 'This venue is already booked for part of this event''s time.',
            'conflicts', blocking,
            'status', 409
        );
    end if;

    insert into public.venue_booking_requests
        (venue_id, event_id, requested_by, event_name, starts_at, ends_at, attendance,
         venue_requirements)
    values ((p_booking->>'venue_id')::uuid, planned.event_id, auth.uid(),
        trim(p_booking->>'event_name'),
        (p_booking->>'starts_at')::timestamptz, (p_booking->>'ends_at')::timestamptz,
        (p_booking->>'attendance')::integer, trim(p_booking->>'venue_requirements'))
    returning * into saved;
    return to_jsonb(saved);
exception when invalid_text_representation or datetime_field_overflow or invalid_datetime_format
    or numeric_value_out_of_range or check_violation or not_null_violation or foreign_key_violation then
    return jsonb_build_object('error', 'Provide valid, complete booking details.', 'status', 400);
end;
$$;

-- 6. Approving: refused when the venue is already booked -----------------

-- As in 026, with the availability check before the write and the constraint
-- caught around it.
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

    if p_outcome = 'approved' and pending.event_id is not null then
        select * into planned from public.events where event_id = pending.event_id;
        if found and planned.status is distinct from 'planning'::public.event_status then
            return jsonb_build_object(
                'error', 'This event is ' || planned.status || ', so its venue can no longer be approved. Reject the request instead.',
                'status', 409
            );
        end if;
        select * into chosen from public.venues where venue_id = pending.venue_id;
        if found and planned.event_id is not null then
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

    if p_outcome = 'approved' then
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
        -- Another overlapping request was approved between the check above
        -- and this write. The constraint is what caught it.
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

revoke all on function
    public.venue_booking_summary(public.venue_booking_requests),
    public.venue_booking_conflicts(uuid, timestamptz, timestamptz, uuid, boolean),
    public.venue_unavailability(timestamptz, timestamptz),
    public.visible_venue_bookings(),
    public.submit_venue_booking(jsonb),
    public.review_venue_booking(uuid, text, text)
    from public, anon;
grant execute on function
    public.venue_booking_summary(public.venue_booking_requests),
    public.venue_booking_conflicts(uuid, timestamptz, timestamptz, uuid, boolean),
    public.venue_unavailability(timestamptz, timestamptz),
    public.visible_venue_bookings(),
    public.submit_venue_booking(jsonb),
    public.review_venue_booking(uuid, text, text)
    to authenticated;

commit;
