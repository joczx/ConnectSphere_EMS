-- Apply after 049_withdraw_event_registration.sql.
-- Read only the signed-in attendee's records, including withdrawn and past events.
begin;
create function public.my_event_registrations() returns jsonb
language plpgsql stable security definer set search_path = public as $$
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('attendee') then
        return jsonb_build_object('error', 'Only attendees can view their registrations.', 'status', 403);
    end if;
    return (select jsonb_build_object('registrations', coalesce(jsonb_agg(
        jsonb_build_object(
            'event_id', e.event_id, 'event_name', e.event_name,
            'start_datetime', e.start_datetime, 'end_datetime', e.end_datetime,
            'event_status', e.status, 'status', r.status,
            'registered_at', r.created_at, 'withdrawn_at', r.withdrawn_at,
            'venues', coalesce((
                select jsonb_agg(distinct v.venue_name order by v.venue_name)
                from public.venues v
                where exists (select 1 from public.venue_booking_requests b
                    where b.event_id = e.event_id and b.venue_id = v.venue_id and b.status = 'approved')
                or (v.venue_id::text = to_jsonb(e)->>'venue_id'
                    and not exists (select 1 from public.venue_booking_requests b
                        where b.event_id = e.event_id and b.status = 'approved'))
            ), '[]'::jsonb)
        ) order by e.start_datetime desc nulls last, e.event_id desc
    ), '[]'::jsonb))
    from public.event_registration r
    join public.events e on e.event_id = r.event_id
    where r.attendee_id = auth.uid());
end;
$$;
revoke all on function public.my_event_registrations() from public, anon;
grant execute on function public.my_event_registrations() to authenticated;
notify pgrst, 'reload schema';
commit;
