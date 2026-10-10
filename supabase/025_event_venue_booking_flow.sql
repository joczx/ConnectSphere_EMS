-- ConnectSphere EMS: A venue booking request belongs to the event it is for
-- Run this file in the Supabase SQL Editor. Apply after 017_venue_bookings.sql
-- and 024_tighten_write_access.sql.
--
-- WHY THIS CHANGES AN EXISTING STORY
-- 017 let a coordinator open "Venue Bookings" and type an event name, a period
-- and an attendance by hand. The event being planned already records all three,
-- plus the room layout, facilities and accessibility the venue has to provide,
-- so retyping them invited a request that disagreed with its own event and gave
-- the database nothing to check a venue against.
--
-- The flow now starts from the event: Events -> the event in planning -> find
-- venues for this event -> request a booking. A request therefore names its
-- event, and the details it carries must match that event rather than compete
-- with it.
--
-- WHAT THIS ENFORCES, AND WHY IT IS HERE RATHER THAN ONLY IN THE UI
-- The search page greys out a venue that cannot meet the event's requirements,
-- but the coordinator is allowed to clear the filters and read the whole
-- catalogue, so unsuitable venues are on screen by design. A greyed-out button
-- is not a rule. The rule is below: an event-linked request is refused unless
-- the venue meets every requirement the event records.
--
-- event_id is nullable because the requests taken under 017 have no event to
-- point at. New submissions must supply one.
--
-- TO REVERT
--     alter table public.venue_booking_requests drop column event_id;
--     then re-apply the two functions from 017_venue_bookings.sql.

begin;

alter table public.venue_booking_requests
    add column if not exists event_id integer references public.events(event_id);

comment on column public.venue_booking_requests.event_id is
    'The event in planning this venue is being requested for. Null only for '
    'requests taken before the planning-first flow existed.';

create index if not exists venue_booking_event_idx
    on public.venue_booking_requests(event_id);

-- Which of the event's venue requirements this venue fails, worded for the
-- coordinator. Empty means the venue may be requested for the event.
--
-- Mirrors unmet_requirements() in backend/app/services/event_venue_criteria.py.
-- Two copies of one rule is a cost worth paying here: the Python copy explains
-- the verdict on every search result, and this copy is the one that actually
-- stops a bad request, including one that never went through the page.
create or replace function public.venue_shortfalls_for_event(
    p_venue public.venues, p_event public.events
) returns text[]
language sql stable set search_path = public as $$
    select coalesce(array_agg(shortfall), array[]::text[])
    from (
        select 'Holds ' || p_venue.capacity || ', but ' || p_event.capacity_needed
               || ' are expected.' as shortfall
        where p_event.capacity_needed is not null
          and p_venue.capacity < p_event.capacity_needed

        union all
        select 'Does not support a ' || replace(p_event.room_layout::text, '_', ' ')
               || ' layout.'
        where p_event.room_layout is not null
          and not (p_event.room_layout::text = any (p_venue.supported_room_layouts))

        union all
        select 'Missing ' || array_to_string(
                   array(
                       select replace(facility, '_', ' ')
                       from unnest(p_event.required_facilities::text[]) as facility
                       where not (facility = any (p_venue.facilities))
                       order by facility
                   ), ', ') || '.'
        where p_event.required_facilities is not null
          and not (p_event.required_facilities::text[] <@ p_venue.facilities)

        union all
        select 'This venue is not wheelchair accessible.'
        where p_event.need_wheelchair_accessibility
          and not p_venue.wheelchair_accessible

        union all
        select 'This venue is not accessible for blind attendees.'
        where p_event.need_blind_accessibility
          and not p_venue.blind_accessible

        -- The catalogue's weekly hours, checked against each Singapore-time day
        -- the event runs on. A day the catalogue does not describe counts as
        -- closed, because booking it would be guesswork.
        union all
        select 'Closed on ' || array_to_string(closed_days, ', ') || '.'
        from (
            select array(
                select distinct initcap(day_name)
                from (
                    select lower(to_char(day, 'FMDay')) as day_name
                    from generate_series(
                        (p_event.start_datetime at time zone 'Asia/Singapore')::date,
                        (p_event.end_datetime at time zone 'Asia/Singapore')::date,
                        interval '1 day'
                    ) as day
                ) as days
                where not (p_venue.operating_hours ? day_name)
                   or coalesce(
                        (p_venue.operating_hours -> day_name ->> 'closed')::boolean,
                        false
                      )
                order by 1
            ) as closed_days
        ) as hours
        where cardinality(closed_days) > 0
    ) as shortfalls;
$$;
revoke all on function public.venue_shortfalls_for_event(public.venues, public.events)
    from public, anon;
grant execute on function public.venue_shortfalls_for_event(public.venues, public.events)
    to authenticated;

create or replace function public.submit_venue_booking(p_booking jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    saved public.venue_booking_requests;
    planned public.events;
    chosen public.venues;
    shortfalls text[];
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

    -- Read directly rather than through the policy, because this function is
    -- security definer: the coordinator check below is what row level security
    -- would otherwise have done.
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

    -- The period and the headcount belong to the event, so a request may not
    -- quietly carry different ones. The coordinator changes the event if they
    -- need to move it, which is the path that warns them about the
    -- arrangements already made against it.
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

-- Unchanged except for the event each request names, which the coordinator
-- needs in order to tell two requests apart once they are listed.
create or replace function public.list_venue_bookings() returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare staff boolean := public.has_booking_role('venue_staff'); result jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not staff and not public.has_booking_role('event_coordinator') then
        return jsonb_build_object('error', 'Venue bookings are available to Event Coordinators and Venue Staff.', 'status', 403);
    end if;
    select coalesce(jsonb_agg(to_jsonb(b) || jsonb_build_object(
            'venue_name', v.venue_name,
            'event_status', e.status
        ) order by b.submitted_at desc), '[]'::jsonb) into result
    from public.venue_booking_requests b
    join public.venues v using (venue_id)
    left join public.events e on e.event_id = b.event_id
    where staff or b.requested_by = auth.uid();
    return jsonb_build_object('bookings', result, 'can_submit', public.has_booking_role('event_coordinator'), 'can_review', staff);
end;
$$;

revoke all on function public.submit_venue_booking(jsonb), public.list_venue_bookings() from public, anon;
grant execute on function public.submit_venue_booking(jsonb), public.list_venue_bookings() to authenticated;

commit;
