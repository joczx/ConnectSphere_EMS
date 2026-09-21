"""Standalone integration checks against an isolated PostgreSQL Docker container.

Start an EMPTY disposable postgres:13 container named connectsphere-equipment-test
before running this script from the repository root. Never target a real database.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
CONTAINER = 'connectsphere-equipment-test'
ACTOR = '00000000-0000-0000-0000-000000000001'
ITEM = 10
EVENTS = [f'00000000-0000-0000-0000-{i:012d}' for i in range(10, 16)]


def sql(query):
    result = subprocess.run(['docker', 'exec', '-i', CONTAINER, 'psql', '-U', 'postgres',
                             '-v', 'ON_ERROR_STOP=1', '-Atq'], input=query,
                            text=True, capture_output=True, check=True)
    return result.stdout.strip()


def user_query(query):
    return sql(f"set role authenticated; set request.jwt.claim.sub = '{ACTOR}'; {query}")


def reserve(event, quantity):
    return json.loads(user_query(f"select public.reserve_equipment('{event}', '{ITEM}', {quantity});"))


def main():
    sql("""
        create role anon; create role authenticated;
        create schema auth;
        create table auth.users(id uuid primary key);
        create function auth.uid() returns uuid language sql stable as
        $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
        grant usage on schema auth to authenticated;
        grant execute on function auth.uid() to authenticated;
    """)
    sql((ROOT / 'supabase/002_create_events.sql').read_text())
    sql((ROOT / 'supabase/006_create_equipment').read_text())
    sql('create table public.equipment_request (equipment_id integer references equipment, event_id uuid references events, quantity integer, status text);')
    sql((ROOT / 'supabase/010_equipment_reservations_existing_catalogue.sql').read_text())
    sql((ROOT / 'supabase/011_manage_equipment_reservations.sql').read_text())
    sql((ROOT / 'backend/tests/equipment_overlap.sql').read_text())
    sql(f"insert into auth.users values ('{ACTOR}'); insert into equipment values ('{ITEM}', 'Projector', 'PX-500', 5);")
    for index, event in enumerate(EVENTS):
        start, end = ('09:00', '10:00') if index < 4 else ('10:00', '11:00')
        sql(f"insert into events(event_id, event_name, starts_at, ends_at) values ('{event}', 'Event {index}', '2030-01-01 {start}Z', '2030-01-01 {end}Z');")
    # No event_members entry: ordinary authenticated users must still have access.
    assert len(json.loads(user_query('select public.equipment_events();'))) == 6
    assert reserve(EVENTS[0], 5)['reservation']['quantity'] == 5
    assert reserve(EVENTS[1], 1)['available_quantity'] == 0
    assert 'already reserved' in reserve(EVENTS[0], 5)['error']
    assert reserve(EVENTS[4], 5)['reservation']['quantity'] == 5
    assert sql('select count(*) from equipment_reservations;') == '2'

    mine = json.loads(user_query('select my_equipment_reservations();'))
    assert len(mine) == 2
    reservation = next(row for row in mine if row['event_id'] == EVENTS[0])['reservation_id']
    def change(quantity):
        return json.loads(user_query(f"select update_equipment_reservation('{reservation}', {quantity});"))
    assert change(3)['reservation']['quantity'] == 3
    assert json.loads(user_query(f"select equipment_availability('{EVENTS[1]}');"))['equipment'][0]['available_quantity'] == 2
    assert change(6)['status'] == 409
    assert change(5)['reservation']['quantity'] == 5
    outsider = '00000000-0000-0000-0000-000000000099'
    assert json.loads(sql(f"set role authenticated; set request.jwt.claim.sub = '{outsider}'; select my_equipment_reservations();")) == []
    for call in (f"update_equipment_reservation('{reservation}', 1)", f"cancel_equipment_reservation('{reservation}')"):
        assert json.loads(sql(f"set role authenticated; set request.jwt.claim.sub = '{outsider}'; select {call};"))['status'] == 404
    assert json.loads(user_query(f"select cancel_equipment_reservation('{reservation}');"))['cancelled']
    assert json.loads(user_query(f"select equipment_availability('{EVENTS[1]}');"))['equipment'][0]['available_quantity'] == 5
    assert change(1)['status'] == 404
    assert reserve(EVENTS[0], 5)['reservation']['quantity'] == 5

    assert 'error' in reserve(EVENTS[2], 0)
    try:
        sql(f"update events set ends_at = ends_at + interval '1 hour' where event_id = '{EVENTS[0]}';")
        raise AssertionError('Reserved event dates must be protected')
    except subprocess.CalledProcessError as exc:
        assert 'Release equipment' in exc.stderr
    sql(f"delete from events where event_id in ('{EVENTS[0]}', '{EVENTS[4]}');")
    assert sql('select count(*) from equipment_reservations;') == '0'
    # Hold the stock lock to force both RPC requests to wait, then compete.
    with ThreadPoolExecutor(max_workers=3) as pool:
        blocker = pool.submit(sql, f"begin; select 1 from equipment where equipment_id = '{ITEM}' for update; select pg_sleep(2); commit;")
        time.sleep(0.4)
        requests = [pool.submit(reserve, event, 5) for event in EVENTS[1:3]]
        results = [job.result() for job in requests]
        blocker.result()
    assert sum('reservation' in result for result in results) == 1, results
    assert sum(result.get('available_quantity') == 0 for result in results) == 1, results
    assert sql('select sum(quantity) from equipment_reservations;') == '5'
    # Verify the deployed date naming convention as well as the repo migration.
    sql('alter table events rename column starts_at to start_datetime; alter table events rename column ends_at to end_datetime;')
    result = json.loads(user_query(f"select equipment_availability('{EVENTS[5]}');"))
    assert result['equipment'][0]['available_quantity'] == 5
    window = json.loads(user_query("select equipment_window_availability('2030-01-01 10:00Z', '2030-01-01 11:00Z');"))
    assert window[0]['available_quantity'] == 5
    sql(f"insert into equipment_request values ({ITEM}, '{EVENTS[3]}', 2, 'accepted');")
    assert sql(f"select equipment_peak({ITEM}, '2030-01-01 09:00Z', '2030-01-01 10:00Z');") == '7'
    sql(f"update events set end_datetime = null where event_id = '{EVENTS[5]}';")
    assert 'valid event start' in reserve(EVENTS[5], 1)['error']
    try:
        user_query('delete from equipment_reservations;')
        raise AssertionError('Direct writes must be blocked')
    except subprocess.CalledProcessError as exc:
        assert 'permission denied' in exc.stderr
    print('PASS: peak overlap, exact stock, rejection, duplicate, adjacent reuse, unrestricted roles, date guard, deletion, concurrency, both date schemas, missing dates, direct-write protection')


if __name__ == '__main__':
    main()
