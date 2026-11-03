begin;

-- Registration windows and attendee registration remain supported. This
-- removes only the obsolete free-text registration_needs field.
create or replace function public.create_event_from_approved_request()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.events (
        event_request_id,
        event_name,
        purpose,
        description,
        start_datetime,
        end_datetime,
        capacity_needed,
        room_layout,
        required_facilities,
        need_wheelchair_accessibility,
        need_blind_accessibility,
        equipment_requirements,
        status,
        event_organiser_id,
        event_coordinator_id
    )
    values (
        new.event_request_id,
        new.event_name,
        new.purpose,
        new.description,
        new.start_datetime,
        new.end_datetime,
        new.capacity_needed,
        new.room_layout,
        coalesce(new.required_facilities, '{}'::public.facility[]),
        new.need_wheelchair_accessibility,
        new.need_blind_accessibility,
        coalesce(new.equipment_requirements, '[]'::jsonb),
        'planning',
        new.event_organiser_id,
        new.event_coordinator_id
    )
    on conflict (event_request_id) do nothing;

    return new;
end;
$$;

alter table public.event_request drop column if exists registration_needs;
alter table public.events drop column if exists registration_needs;

commit;
