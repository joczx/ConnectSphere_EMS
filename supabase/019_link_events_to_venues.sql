-- Venue deletion support. Apply after 018_add_venue_update_tracking.sql.
--
-- The relationship lets the catalogue block deletion when a future event is
-- assigned to the venue. Existing events remain unassigned (NULL) until a
-- venue is selected for them.

begin;

alter table public.events
    add column if not exists venue_id uuid references public.venues(venue_id) on delete restrict;

create index if not exists events_venue_start_datetime_idx
    on public.events (venue_id, start_datetime);

commit;
