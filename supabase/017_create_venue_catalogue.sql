-- Venue catalogue creation support. Apply after 001_create_venues.sql.
--
-- Before applying, run the duplicate-check query documented with this
-- migration. The unique index will deliberately fail if duplicate catalogue
-- rows already exist, so no existing row is silently removed.
--
-- select lower(btrim(venue_name)) as venue_name,
--        lower(btrim(block_number)) as block_number,
--        lower(btrim(street_name)) as street_name,
--        postal_code,
--        lower(btrim(coalesce(building_name, ''))) as building_name,
--        lower(btrim(coalesce(unit_number, ''))) as unit_number,
--        count(*) as duplicate_count,
--        array_agg(venue_id) as venue_ids
-- from public.venues
-- group by 1, 2, 3, 4, 5, 6
-- having count(*) > 1;

begin;

alter table public.venues enable row level security;

revoke all on table public.venues from anon;

grant select, insert, update, delete
on table public.venues
to authenticated;

drop policy if exists authenticated_read_venues on public.venues;
drop policy if exists venue_staff_create_venues on public.venues;
drop policy if exists authenticated_manage_venues on public.venues;

create policy authenticated_manage_venues
on public.venues
for all
to authenticated
using (true)
with check (true);

create unique index if not exists venues_normalized_name_address_key
on public.venues (
    lower(btrim(venue_name)),
    lower(btrim(block_number)),
    lower(btrim(street_name)),
    postal_code,
    lower(btrim(coalesce(building_name, ''))),
    lower(btrim(coalesce(unit_number, '')))
);

commit;
