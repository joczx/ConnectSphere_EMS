-- Apply after 059. Only show events during their registration window.
-- Opening is inclusive; closing is exclusive. No derived status field.
begin;

create or replace function public.attendee_registration_events()
returns jsonb
language plpgsql stable security definer set search_path to 'public' as $function$
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('attendee') then
        return jsonb_build_object('error', 'Only attendees can browse registration events.', 'status', 403);
    end if;
    return (
        select jsonb_build_object('events', coalesce(jsonb_agg(jsonb_build_object(
            'event_id', e.event_id, 'event_name', e.event_name, 'description', e.description,
            'start_datetime', e.start_datetime, 'end_datetime', e.end_datetime,
            'status', e.status, 'registration_opens_at', e.registration_opens_at,
            'registration_closes_at', e.registration_closes_at,
            'waiting_list_enabled', e.waiting_list_enabled, 'capacity', e.capacity_needed,
            'available_capacity', greatest(0, e.capacity_needed - (select count(*) from public.event_registration r
                where r.event_id = e.event_id and r.status = 'registered')),
            'my_registration', (select r.status from public.event_registration r
                where r.event_id = e.event_id and r.attendee_id = auth.uid()),
            'venues', coalesce((
                select jsonb_agg(distinct v.venue_name order by v.venue_name)
                from public.venues v
                where exists (select 1 from public.venue_booking_requests b
                    where b.event_id = e.event_id and b.venue_id = v.venue_id and b.status = 'approved')
                or (v.venue_id::text = to_jsonb(e)->>'venue_id'
                    and not exists (select 1 from public.venue_booking_requests b
                        where b.event_id = e.event_id and b.status = 'approved'))
            ), '[]'::jsonb)
        ) order by e.start_datetime), '[]'::jsonb))
        from public.events e
        where e.status = 'confirmed'
            and e.start_datetime > now()
            and e.end_datetime > now()
            and e.registration_opens_at <= now()
            and e.registration_opens_at < e.registration_closes_at
            and now() < e.registration_closes_at);
end;
$function$;

notify pgrst, 'reload schema';
commit;
