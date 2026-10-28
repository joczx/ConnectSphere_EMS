-- Apply after 049_withdraw_event_registration.sql.
begin;
create or replace function public.event_registration_roster(p_event_id integer) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare planned public.events;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not (public.has_booking_role('event_organiser') or public.has_booking_role('event_coordinator')) then
        return jsonb_build_object('error', 'Only event organisers and coordinators can view registration information.', 'status', 403);
    end if;
    select * into planned from public.events where event_id = p_event_id;
    if not found or (
        (public.has_booking_role('event_organiser') and planned.event_organiser_id = auth.uid())
        or (public.has_booking_role('event_coordinator') and planned.event_coordinator_id = auth.uid())
    ) is not true then
        return jsonb_build_object('error', 'Event not found or access unavailable.', 'status', 404);
    end if;
    return (select jsonb_build_object(
        'event', jsonb_build_object('event_id', planned.event_id, 'event_name', planned.event_name),
        'total_registered', count(*) filter (where r.status = 'registered'),
        'total_waitlisted', count(*) filter (where r.status = 'waiting_list'),
        'total_withdrawn', count(*) filter (where r.status = 'withdrawn'),
        'registrations', coalesce(jsonb_agg(jsonb_build_object(
            'attendee_id', r.attendee_id, 'full_name', r.full_name,
            'contact_email', r.contact_email, 'contact_phone', r.contact_phone,
            'status', r.status, 'registered_at', r.created_at, 'withdrawn_at', r.withdrawn_at
        ) order by r.created_at, r.attendee_id), '[]'::jsonb)
    ) from public.event_registration r where r.event_id = p_event_id);
end;
$$;
revoke all on function public.event_registration_roster(integer) from public, anon;
grant execute on function public.event_registration_roster(integer) to authenticated;
notify pgrst, 'reload schema';
commit;
