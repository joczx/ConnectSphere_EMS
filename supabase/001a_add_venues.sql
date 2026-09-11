-- ConnectSphere EMS: development venue seed data
-- Run this only after 001_create_venues.sql.
--
-- Venue names, addresses, and headline capacities are based on public venue
-- information. Operating hours, facilities, setup/turnaround times, and detailed
-- accessibility notes are development assumptions to verify before production use.
-- Each insert checks the venue name, so this file may be rerun without duplicates.

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'Suntec Singapore Convention Hall - Level 4', 10000, '039593', '1',
    'Raffles Boulevard', 'Suntec Singapore Convention & Exhibition Centre',
    'Level 4 - Convention Hall', true, true,
    'Development assumption: confirm venue-specific accessibility services.',
    array['stage', 'built_in_av', 'wifi', 'catering', 'parking', 'air_conditioning'],
    array['theatre', 'classroom', 'banquet', 'exhibition', 'cocktail'],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"09:00","close":"18:00"},"sunday":{"closed":true}}'::jsonb,
    120, 60
where not exists (
    select 1 from public.venues
    where venue_name = 'Suntec Singapore Convention Hall - Level 4'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'Suntec Singapore Auditorium - Halls 602 to 604', 4200, '039593', '1',
    'Raffles Boulevard', 'Suntec Singapore Convention & Exhibition Centre',
    'Level 6 - Halls 602 to 604', true, true,
    'Development assumption: confirm venue-specific accessibility services.',
    array['stage', 'sound_system', 'lighting', 'built_in_av', 'wifi', 'catering', 'parking', 'air_conditioning'],
    array['theatre'],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"09:00","close":"18:00"},"sunday":{"closed":true}}'::jsonb,
    90, 45
where not exists (
    select 1 from public.venues
    where venue_name = 'Suntec Singapore Auditorium - Halls 602 to 604'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'Singapore EXPO Hall 1', 9000, '486150', '1', 'Expo Drive', 'Singapore EXPO',
    'Hall 1', true, true,
    'Development assumption: confirm venue-specific accessibility services.',
    array['stage', 'built_in_av', 'wifi', 'parking', 'loading_bay', 'air_conditioning'],
    array['theatre', 'banquet', 'exhibition', 'cocktail'],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"09:00","close":"18:00"},"sunday":{"closed":true}}'::jsonb,
    120, 60
where not exists (
    select 1 from public.venues
    where venue_name = 'Singapore EXPO Hall 1'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'Singapore EXPO Halls G, H and J', 220, '486150', '1', 'Expo Drive', 'Singapore EXPO',
    'Halls G, H and J', true, false,
    'Development assumption: visual-accessibility support requires confirmation.',
    array['wifi', 'power_outlets', 'air_conditioning'],
    array['classroom', 'theatre', 'boardroom'],
    '{"monday":{"open":"08:00","close":"22:00"},"tuesday":{"open":"08:00","close":"22:00"},"wednesday":{"open":"08:00","close":"22:00"},"thursday":{"open":"08:00","close":"22:00"},"friday":{"open":"08:00","close":"22:00"},"saturday":{"open":"09:00","close":"18:00"},"sunday":{"closed":true}}'::jsonb,
    45, 30
where not exists (
    select 1 from public.venues
    where venue_name = 'Singapore EXPO Halls G, H and J'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'Sands Grand Ballroom', 8000, '018956', '10', 'Bayfront Avenue',
    'Marina Bay Sands Expo & Convention Centre', 'Level 5 - Sands Grand Ballroom',
    true, true,
    'Development assumption: confirm venue-specific accessibility services.',
    array['stage', 'audio_visual', 'wifi', 'catering', 'parking', 'air_conditioning'],
    array['theatre', 'classroom', 'banquet', 'cocktail'],
    '{"monday":{"open":"08:00","close":"23:00"},"tuesday":{"open":"08:00","close":"23:00"},"wednesday":{"open":"08:00","close":"23:00"},"thursday":{"open":"08:00","close":"23:00"},"friday":{"open":"08:00","close":"23:00"},"saturday":{"open":"09:00","close":"23:00"},"sunday":{"open":"09:00","close":"20:00"}}'::jsonb,
    120, 60
where not exists (
    select 1 from public.venues
    where venue_name = 'Sands Grand Ballroom'
);

insert into public.venues (
    venue_name, capacity, postal_code, block_number, street_name, building_name,
    unit_number, wheelchair_accessible, blind_accessible, accessibility_notes,
    facilities, supported_room_layouts, operating_hours,
    default_setup_minutes, default_turnaround_minutes
)
select
    'Fairmont Ballroom', 3000, '189560', '80', 'Bras Basah Road', 'Fairmont Singapore',
    'Fairmont Ballroom', true, true,
    'Development assumption: confirm venue-specific accessibility services.',
    array['stage', 'audio_visual', 'wifi', 'catering', 'parking', 'air_conditioning'],
    array['theatre', 'classroom', 'banquet', 'cabaret', 'cocktail'],
    '{"monday":{"open":"08:00","close":"23:00"},"tuesday":{"open":"08:00","close":"23:00"},"wednesday":{"open":"08:00","close":"23:00"},"thursday":{"open":"08:00","close":"23:00"},"friday":{"open":"08:00","close":"23:00"},"saturday":{"open":"09:00","close":"23:00"},"sunday":{"open":"09:00","close":"20:00"}}'::jsonb,
    90, 45
where not exists (
    select 1 from public.venues
    where venue_name = 'Fairmont Ballroom'
);
