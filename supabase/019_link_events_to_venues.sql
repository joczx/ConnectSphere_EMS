-- Venue deletion support. Apply after 018_add_venue_update_tracking.sql.
--
-- The relationship keeps venue assignment optional. Deleting a venue clears
-- existing links so catalogue cleanup is not blocked by historical event rows.
-- Existing events remain unassigned (NULL) until a venue is selected for them.

begin;

alter table public.events
    add column if not exists venue_id uuid references public.venues(venue_id) on delete set null;

create index if not exists events_venue_start_datetime_idx
    on public.events (venue_id, start_datetime);

commit;
