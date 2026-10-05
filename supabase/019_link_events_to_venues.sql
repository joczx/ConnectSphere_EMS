-- Venue deletion support. Apply after 018_add_venue_update_tracking.sql.
--
-- The application uses soft deletion in 020, so normal catalogue removal
-- preserves historic event-to-venue links. ON DELETE SET NULL remains a safe
-- fallback if an administrator physically removes a venue. Existing events
-- remain unassigned (NULL) until a venue is selected for them.

begin;

alter table public.events
    add column if not exists venue_id uuid references public.venues(venue_id) on delete set null;

create index if not exists events_venue_start_datetime_idx
    on public.events (venue_id, start_datetime);

commit;
