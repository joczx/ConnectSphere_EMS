-- ConnectSphere EMS: Equipment and registration needs on event requests
-- Run this file in the Supabase SQL Editor.
--
-- Supports the "Create and Submit Event Request" story, which requires an
-- event request to carry "equipment requirements, and registration needs
-- where relevant". Both are optional: an event may need neither.

alter table public.event_request
    -- A statement of need, not a reservation. Technical Support Staff resolve
    -- these against the equipment catalogue later, which is why the type is
    -- free text here rather than a foreign key to public.equipment.
    --
    -- Shape: [{"equipment_type": "projector", "quantity": 2, "notes": "HDMI"}]
    -- "notes" carries the per-item technical requirements and may be null.
    add column if not exists equipment_requirements jsonb not null default '[]'::jsonb,

    -- Free text. Registration itself is run by the Organiser outside
    -- ConnectSphere, so this records intent only. Null means the event does
    -- not need registration.
    add column if not exists registration_needs text;

-- Only the outer type is enforced here. PostgreSQL does not allow subqueries
-- in a check constraint, so per-item rules (non-empty type, quantity >= 1, no
-- duplicate types) are enforced in app/schemas/event_request.py, where they
-- can also produce a readable error message.
alter table public.event_request
    drop constraint if exists event_request_equipment_requirements_is_array;

alter table public.event_request
    add constraint event_request_equipment_requirements_is_array
    check (jsonb_typeof(equipment_requirements) = 'array');

comment on column public.event_request.equipment_requirements is
    'Equipment the Event Organiser expects to need, as a JSON array of '
    '{equipment_type, quantity, notes} objects. Empty array means none.';

comment on column public.event_request.registration_needs is
    'Free-text description of the event''s attendee registration needs. '
    'Null means registration is not required.';
