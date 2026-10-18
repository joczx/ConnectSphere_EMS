-- Enforce event assignment in the booking RPCs as well as in the Flask API.
-- This is function-level authorization, not row-level security.

begin;

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
        end
    )
    from public.venue_booking_requests b
    join public.venues v on v.venue_id = b.venue_id
    join public.events e on e.event_id = b.event_id
    left join public.users requester on requester.user_id = b.requested_by
    left join public.users reviewer on reviewer.user_id = b.reviewed_by
    where auth.uid() is not null
      and (
          (public.has_booking_role('event_coordinator')
              and e.event_coordinator_id = auth.uid())
          or
          (public.has_booking_role('venue_staff')
              and e.venue_staff_id = auth.uid())
      )
    order by b.submitted_at desc;
$$;
revoke all on function public.visible_venue_bookings() from public, anon;
grant execute on function public.visible_venue_bookings() to authenticated;

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

    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object(
            'error', 'Only Venue Staff can approve or reject venue bookings.',
            'status', 403
        );
    end if;

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
