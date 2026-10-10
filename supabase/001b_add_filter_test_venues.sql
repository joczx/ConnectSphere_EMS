-- ConnectSphere EMS: dummy venues for testing the Venue Search filters
-- Run this only after 001_create_venues.sql. Safe to re-run: each insert checks
-- the venue name first.
--
-- Built against the events in planning as of 2026-10-08. Five venues meet at
-- least one event's requirements; five are near misses that each fail exactly
-- one requirement, so every kind of filter can be seen working:
--
--   capacity ............ Small Boardroom              (event 3)
--   room layout ......... Lecture Theatre              (event 1)
--   wheelchair access ... Upstairs U-Shape Room        (events 4, 5)
--   facilities .......... U-Shape Room without Stage   (event 5)
--   operating day ....... Training Hall, closed Saturdays (event 6)
--
-- Each venue's accessibility_notes says which events it was built to meet or
-- fail. If those events change, the venues no longer prove anything.
--
-- Shared Conference Hall meets events 5 and 6, for testing that approving one
-- of two overlapping requests blocks the other.
--
-- No venue can meet event 2: it expects 3,213,123 attendees and requires a
-- microphone and a whiteboard, which the venue catalogue has no facility for.
--
-- TO REMOVE
--     delete from public.venues where venue_name like 'ConnectSphere Test - %';

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'ConnectSphere Test - Executive Boardroom', 60, '138601',
    '10', 'Test Avenue', 'ConnectSphere Filter Test Block',
    null, true, true,
    'Dummy venue for testing filters. Meets events 3, 4 and 5.',
    array['projector', 'stage', 'sound_system', 'wifi']::text[],
    array['boardroom', 'u_shape']::text[],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"08:00","close":"22:00"},"sunday":{"open":"08:00","close":"22:00"}}'::jsonb,
    30, 30
where not exists (
    select 1 from public.venues where venue_name = 'ConnectSphere Test - Executive Boardroom'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'ConnectSphere Test - Accessible U-Shape Suite', 30, '138602',
    '11', 'Test Avenue', 'ConnectSphere Filter Test Block',
    null, true, true,
    'Dummy venue for testing filters. Meets events 4 and 5.',
    array['stage', 'projector', 'sound_system', 'wifi']::text[],
    array['u_shape']::text[],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"08:00","close":"22:00"},"sunday":{"open":"08:00","close":"22:00"}}'::jsonb,
    30, 30
where not exists (
    select 1 from public.venues where venue_name = 'ConnectSphere Test - Accessible U-Shape Suite'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'ConnectSphere Test - Boardroom 24/7', 80, '138603',
    '12', 'Test Avenue', 'ConnectSphere Filter Test Block',
    null, true, false,
    'Dummy venue for testing filters. Meets event 3, which runs every day of the week.',
    array['projector', 'stage', 'wifi']::text[],
    array['boardroom']::text[],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"08:00","close":"22:00"},"sunday":{"open":"08:00","close":"22:00"}}'::jsonb,
    30, 30
where not exists (
    select 1 from public.venues where venue_name = 'ConnectSphere Test - Boardroom 24/7'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'ConnectSphere Test - Learning Studio', 120, '138604',
    '13', 'Test Avenue', 'ConnectSphere Filter Test Block',
    null, false, false,
    'Dummy venue for testing filters. Meets event 1. Closed Sundays, which event 1 does not touch.',
    array['projector', 'wifi', 'air_conditioning']::text[],
    array['classroom']::text[],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"08:00","close":"22:00"},"sunday":{"closed":true}}'::jsonb,
    30, 30
where not exists (
    select 1 from public.venues where venue_name = 'ConnectSphere Test - Learning Studio'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'ConnectSphere Test - Full-Service Training Hall', 45, '138605',
    '14', 'Test Avenue', 'ConnectSphere Filter Test Block',
    null, false, false,
    'Dummy venue for testing filters. Meets event 6: every catalogue facility, open Saturdays.',
    array['stage', 'projector', 'sound_system', 'video_conferencing', 'wifi', 'parking', 'catering_area', 'air_conditioning']::text[],
    array['classroom']::text[],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"08:00","close":"22:00"},"sunday":{"open":"08:00","close":"22:00"}}'::jsonb,
    30, 30
where not exists (
    select 1 from public.venues where venue_name = 'ConnectSphere Test - Full-Service Training Hall'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'ConnectSphere Test - Small Boardroom', 20, '138606',
    '15', 'Test Avenue', 'ConnectSphere Filter Test Block',
    null, true, false,
    'Dummy venue for testing filters. Fails event 3 on capacity only (20 seats, 50 expected).',
    array['projector', 'stage', 'wifi']::text[],
    array['boardroom']::text[],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"08:00","close":"22:00"},"sunday":{"open":"08:00","close":"22:00"}}'::jsonb,
    30, 30
where not exists (
    select 1 from public.venues where venue_name = 'ConnectSphere Test - Small Boardroom'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'ConnectSphere Test - Lecture Theatre', 150, '138607',
    '16', 'Test Avenue', 'ConnectSphere Filter Test Block',
    null, false, false,
    'Dummy venue for testing filters. Fails event 1 on room layout only (theatre, not classroom).',
    array['projector', 'wifi']::text[],
    array['theatre']::text[],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"08:00","close":"22:00"},"sunday":{"closed":true}}'::jsonb,
    30, 30
where not exists (
    select 1 from public.venues where venue_name = 'ConnectSphere Test - Lecture Theatre'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'ConnectSphere Test - Upstairs U-Shape Room', 30, '138608',
    '17', 'Test Avenue', 'ConnectSphere Filter Test Block',
    null, false, true,
    'Dummy venue for testing filters. Fails events 4 and 5 on wheelchair access only.',
    array['stage', 'projector', 'sound_system', 'wifi']::text[],
    array['u_shape']::text[],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"08:00","close":"22:00"},"sunday":{"open":"08:00","close":"22:00"}}'::jsonb,
    30, 30
where not exists (
    select 1 from public.venues where venue_name = 'ConnectSphere Test - Upstairs U-Shape Room'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'ConnectSphere Test - U-Shape Room without Stage', 30, '138609',
    '18', 'Test Avenue', 'ConnectSphere Filter Test Block',
    null, true, true,
    'Dummy venue for testing filters. Fails event 5 on facilities only (no stage). Still meets event 4.',
    array['projector', 'sound_system', 'wifi']::text[],
    array['u_shape']::text[],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"08:00","close":"22:00"},"sunday":{"open":"08:00","close":"22:00"}}'::jsonb,
    30, 30
where not exists (
    select 1 from public.venues where venue_name = 'ConnectSphere Test - U-Shape Room without Stage'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'ConnectSphere Test - Training Hall, closed Saturdays', 45, '138610',
    '19', 'Test Avenue', 'ConnectSphere Filter Test Block',
    null, false, false,
    'Dummy venue for testing filters. Fails event 6 on operating day only (event 6 is a Saturday).',
    array['stage', 'projector', 'sound_system', 'video_conferencing', 'wifi', 'parking', 'catering_area', 'air_conditioning']::text[],
    array['classroom']::text[],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"closed":true},"sunday":{"open":"08:00","close":"22:00"}}'::jsonb,
    30, 30
where not exists (
    select 1 from public.venues where venue_name = 'ConnectSphere Test - Training Hall, closed Saturdays'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'ConnectSphere Test - Shared Conference Hall', 60, '138611',
    '20', 'Test Avenue', 'ConnectSphere Filter Test Block',
    null, true, true,
    'Dummy venue for testing filters. Meets events 5 and 6, so both can request it for overlapping times and approving one blocks the other.',
    array['stage', 'projector', 'sound_system', 'video_conferencing', 'wifi', 'parking', 'catering_area', 'air_conditioning']::text[],
    array['classroom', 'u_shape']::text[],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"08:00","close":"22:00"},"sunday":{"open":"08:00","close":"22:00"}}'::jsonb,
    30, 30
where not exists (
    select 1 from public.venues where venue_name = 'ConnectSphere Test - Shared Conference Hall'
);
