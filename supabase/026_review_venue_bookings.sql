-- ConnectSphere EMS: Venue Staff approve or reject venue booking requests
-- Run this file in the Supabase SQL Editor. Apply after
-- 025_event_venue_booking_flow.sql, whose venue_shortfalls_for_event() this
-- uses.
--
-- Backs the "Approve or reject pending venue booking requests" story:
--   * Venue Staff view pending requests with their full details.
--   * Venue Staff approve or reject, with a reason required to reject.
--   * The Event Coordinator is alerted to the outcome and the comments.
--
-- A DECISION IS FINAL, AND MADE ONCE
-- The decision is written by a single update that only matches a request still
-- awaiting review, so two staff members deciding at the same moment cannot
-- both succeed, and a decided request cannot be quietly re-decided.
--
-- APPROVAL RECHECKS THE EVENT
-- A request was checked against the event when it was submitted, but the event
-- can be edited afterwards; the planning page warns that a critical edit "may
-- invalidate a venue booking". Approval therefore rechecks the venue against
-- the event as it is now, and refuses while the event is no longer in planning.
-- Rejection is always allowed: it is the way out of a request that no longer
-- fits.
--
-- THE ALERT IS BEST EFFORT
-- notification.recipient_id references public.users, and a coordinator missing
-- from that table would make the insert fail. Losing the alert is bad; undoing
-- a decision the reviewer was told had been recorded is worse. So a failed
-- alert is skipped, and the coordinator still sees the outcome and comments on
-- their own request, which is where the decision actually lives.
--
-- TO REVERT
--     drop function if exists public.review_venue_booking(uuid, text, text);
--     drop function if exists public.get_venue_booking(uuid);
--     drop function if exists public.venue_booking_alerts();
--     drop function if exists public.dismiss_venue_booking_alerts(bigint[]);
--     alter table public.notification drop column venue_booking_id;
--     alter table public.venue_booking_requests
--         drop column reviewed_by, drop column reviewed_at, drop column review_comments;
--     then re-apply list_venue_bookings() from 025.

begin;

-- 1. The decision, on the request it decides ------------------------------

-- 017 pinned status to 'submitted' with an unnamed check, so it is found by
-- what it constrains rather than guessed at by name.
do $$
declare constraint_name text;
begin
    for constraint_name in
        select conname from pg_constraint
        where conrelid = 'public.venue_booking_requests'::regclass
          and contype = 'c'
          and pg_get_constraintdef(oid) ilike '%status%'
    loop
        execute format('alter table public.venue_booking_requests drop constraint %I', constraint_name);
    end loop;
end $$;

alter table public.venue_booking_requests
    add column if not exists reviewed_by uuid references auth.users(id),
    add column if not exists reviewed_at timestamptz,
    add column if not exists review_comments text;

alter table public.venue_booking_requests
    add constraint venue_booking_status_known
        check (status in ('submitted', 'approved', 'rejected')),
    -- Decided exactly when a reviewer and a time are recorded, so a request can
    -- never look decided without saying by whom.
    add constraint venue_booking_decision_recorded
        check ((status = 'submitted') = (reviewed_at is null and reviewed_by is null)),
    add constraint venue_booking_rejection_has_reason
        check (status <> 'rejected' or length(trim(coalesce(review_comments, ''))) > 0),
    add constraint venue_booking_comments_length
        check (review_comments is null or length(review_comments) <= 2000);

-- The review queue: what is waiting, oldest first.
create index if not exists venue_booking_status_idx
    on public.venue_booking_requests(status, submitted_at);

-- 2. The alert's link to the request it is about -------------------------

-- 003 anticipated this: each story adds its own nullable foreign key rather
-- than a generic entity id, so referential integrity is kept.
alter table public.notification
    add column if not exists venue_booking_id uuid
        references public.venue_booking_requests(booking_id) on delete cascade;

create index if not exists notification_venue_booking_unread_idx
    on public.notification(recipient_id, created_at desc)
    where venue_booking_id is not null and not is_read;

-- 3. What a request looks like to the people allowed to see it ----------

-- One definition shared by the list and the single-request read, so the two
-- can never disagree about who may see what. Venue Staff see every request; a
-- coordinator sees their own.
create or replace function public.visible_venue_bookings()
returns setof jsonb
language sql stable security definer set search_path = public as $$
    select to_jsonb(b) || jsonb_build_object(
        'venue_name', v.venue_name,
        'event_status', e.status,
        'requested_by_name', requester.name,
        'reviewed_by_name', reviewer.name,
        -- Only meaningful while the request is still waiting: it is what the
        -- reviewer needs to know before deciding, and what approval rechecks.
        'current_shortfalls', case
            when b.status = 'submitted' and e.event_id is not null
            then to_jsonb(public.venue_shortfalls_for_event(v, e))
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
revoke all on function public.visible_venue_bookings() from public, anon;
grant execute on function public.visible_venue_bookings() to authenticated;

create or replace function public.list_venue_bookings() returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare staff boolean := public.has_booking_role('venue_staff');
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not staff and not public.has_booking_role('event_coordinator') then
        return jsonb_build_object('error', 'Venue bookings are available to Event Coordinators and Venue Staff.', 'status', 403);
    end if;
    return jsonb_build_object(
        'bookings', coalesce((
            select jsonb_agg(item order by item->>'submitted_at' desc)
            from public.visible_venue_bookings() as item
        ), '[]'::jsonb),
        'can_submit', public.has_booking_role('event_coordinator'),
        'can_review', staff
    );
end;
$$;

create or replace function public.get_venue_booking(p_booking_id uuid) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare found_booking jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    select item into found_booking
    from public.visible_venue_bookings() as item
    where (item->>'booking_id')::uuid = p_booking_id;

    -- Not found and not permitted read the same, so a request's existence is
    -- not disclosed to someone who may not see it.
    if found_booking is null then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    return jsonb_build_object(
        'booking', found_booking,
        'can_review', public.has_booking_role('venue_staff')
    );
end;
$$;

-- 4. The decision ---------------------------------------------------------

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

    -- The only write. Matching on status as well as id is what makes the
    -- decision once-only under concurrency: the second reviewer's update finds
    -- nothing to change.
    update public.venue_booking_requests
    set status = p_outcome,
        reviewed_by = auth.uid(),
        reviewed_at = now(),
        review_comments = comments
    where booking_id = p_booking_id and status = 'submitted'
    returning * into decided;

    if not found then
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
        -- See "THE ALERT IS BEST EFFORT" above.
        null;
    end;

    return jsonb_build_object('booking', to_jsonb(decided));
end;
$$;

-- 5. The coordinator's alerts ---------------------------------------------

-- Read through functions rather than table policies: notification has row
-- level security with no policies in this repository, and these two are
-- scoped to the caller whatever the table's policies turn out to be.
create or replace function public.venue_booking_alerts() returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(jsonb_build_object(
        'notification_id', n.notification_id,
        'venue_booking_id', n.venue_booking_id,
        'notification_type', n.notification_type,
        'message', n.message,
        'created_at', n.created_at
    ) order by n.created_at desc), '[]'::jsonb)
    from public.notification n
    where auth.uid() is not null
      and n.recipient_id = auth.uid()
      and n.venue_booking_id is not null
      and not n.is_read;
$$;

create or replace function public.dismiss_venue_booking_alerts(p_notification_ids bigint[])
returns jsonb
language plpgsql security definer set search_path = public as $$
declare dismissed integer;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    -- Only the caller's own venue booking alerts, whatever ids are sent.
    update public.notification
    set is_read = true
    where notification_id = any (coalesce(p_notification_ids, array[]::bigint[]))
      and recipient_id = auth.uid()
      and venue_booking_id is not null;
    get diagnostics dismissed = row_count;
    return jsonb_build_object('dismissed', dismissed);
end;
$$;

revoke all on function
    public.list_venue_bookings(),
    public.get_venue_booking(uuid),
    public.review_venue_booking(uuid, text, text),
    public.venue_booking_alerts(),
    public.dismiss_venue_booking_alerts(bigint[])
    from public, anon;
grant execute on function
    public.list_venue_bookings(),
    public.get_venue_booking(uuid),
    public.review_venue_booking(uuid, text, text),
    public.venue_booking_alerts(),
    public.dismiss_venue_booking_alerts(bigint[])
    to authenticated;

commit;
