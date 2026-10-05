-- Preserve historical event-to-venue links while removing unusable venues from
-- the active catalogue. Apply after 019_link_events_to_venues.sql.
--
-- A normal catalogue deletion records a timestamp instead of physically
-- deleting the venue row. The application excludes rows with `deleted_at`,
-- while completed and past events retain their original venue_id.

begin;

alter table public.venues
    add column if not exists deleted_at timestamptz;

create index if not exists venues_active_catalogue_idx
    on public.venues (venue_name)
    where deleted_at is null;

commit;
