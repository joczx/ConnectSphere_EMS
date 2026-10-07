-- Venue catalogue update support. Apply after 017_create_venue_catalogue.sql.
--
-- `version` lets the API make an optimistic, compare-and-swap update. The
-- trigger increases it for every successful edit, and also records when the
-- catalogue information last changed.

begin;

alter table public.venues
    add column if not exists version integer not null default 1
        check (version >= 1),
    add column if not exists updated_at timestamptz not null default clock_timestamp();

create or replace function public.track_venue_update()
returns trigger
language plpgsql
as $$
begin
    new.version := old.version + 1;
    new.updated_at := clock_timestamp();
    return new;
end;
$$;

drop trigger if exists venues_track_update on public.venues;
create trigger venues_track_update
before update on public.venues
for each row execute function public.track_venue_update();

commit;
