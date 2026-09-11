-- ConnectSphere EMS: Venue catalogue
-- Run this file in the Supabase SQL Editor or apply it through a Supabase migration.
-- This migration creates the venue catalogue only; it does not insert seed data.

create table if not exists public.venues (
    venue_id uuid primary key default gen_random_uuid(),
    venue_name text not null check (btrim(venue_name) <> ''),
    capacity integer not null check (capacity > 0),

    -- Singapore address components
    postal_code text not null check (postal_code ~ '^[0-9]{6}$'),
    block_number text not null check (btrim(block_number) <> ''),
    street_name text not null check (btrim(street_name) <> ''),
    building_name text,
    unit_number text,

    wheelchair_accessible boolean not null,
    blind_accessible boolean not null,
    accessibility_notes text, --optional, e.g. braille signage and tactile paving available

    -- Examples: stage, projector, sound_system, wifi, pool.
    facilities text[] not null,
    -- Examples: theatre, classroom, boardroom, banquet, exhibition.
    supported_room_layouts text[] not null,

    -- One entry is required for each weekday. A closed day may use:
    -- {"sunday": {"closed": true}}
    -- An open day may use:
    -- {"monday": {"open": "08:00", "close": "22:00"}}
    operating_hours jsonb not null
        check (jsonb_typeof(operating_hours) = 'object')
        check (
            operating_hours ?& array[
                'monday', 'tuesday', 'wednesday', 'thursday',
                'friday', 'saturday', 'sunday'
            ]
        ),

    default_setup_minutes integer not null check (default_setup_minutes >= 0),
    default_turnaround_minutes integer not null check (default_turnaround_minutes >= 0)
);

comment on table public.venues is
    'Catalogue of ConnectSphere event spaces and their operational characteristics.';

-- Future work (intentionally not created in this migration):
--   1. venue_bookings: stores event-specific booking requests and approvals.
--   2. venue_unavailability: stores maintenance, safety, renovation, and internal blocks.
-- These future tables will support the availability calendar and booking-conflict detection.
