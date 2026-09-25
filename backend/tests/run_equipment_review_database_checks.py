"""Run against an EMPTY disposable postgres:13 container named connectsphere-review-test."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CONTAINER = 'connectsphere-review-test'
ACTOR = '00000000-0000-0000-0000-000000000001'
OTHER = '00000000-0000-0000-0000-000000000002'


def sql(query):
    result = subprocess.run(['docker', 'exec', '-i', CONTAINER, 'psql', '-U', 'postgres', '-Atq', '-v', 'ON_ERROR_STOP=1'], input=query, text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def user(query, actor=ACTOR):
    return json.loads(sql(f"set role authenticated; set request.jwt.claim.sub = '{actor}'; {query}"))


def review(request_id, outcome, quantity='null', actor=ACTOR):
    return user(f"select review_equipment_request({request_id}, '{outcome}', 10, {quantity}, 'Not suitable');", actor)


def change(reservation_id, quantity=None, actor=ACTOR):
    operation = f"cancel_equipment_reservation('{reservation_id}')" if quantity is None else f"update_equipment_reservation('{reservation_id}', {quantity})"
    return user(f'select {operation};', actor)


def availability(event_id):
    return user(f"select equipment_availability('{event_id}');")['equipment'][0]['available_quantity']


def request_row(request_id):
    return json.loads(sql(f'select row_to_json(r) from equipment_request r where equipment_request_id = {request_id};'))


def main():
    sql("""
        create role anon; create role authenticated;
        create schema auth;
        create table auth.users(id uuid primary key);
        create function auth.uid() returns uuid language sql stable as
        $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
        grant usage on schema auth to authenticated;
        grant execute on function auth.uid() to authenticated;
        create table users(user_id uuid primary key);
        create table events(event_id integer primary key, event_name text,
            start_datetime timestamptz, end_datetime timestamptz,
            technical_support_id uuid, event_organiser_id uuid);
    """)
    for file in ['006_create_equipment', '005_create_equipment_request.sql',
                 '010_equipment_reservations_existing_catalogue.sql', '011_manage_equipment_reservations.sql',
                 '012_review_equipment_requests.sql', '013_link_equipment_request_reservations.sql',
                 '015_account_equipment_requests.sql', '016_manage_linked_equipment_reservations.sql']:
        sql((ROOT / 'supabase' / file).read_text())
    sql(f"""
        insert into auth.users values ('{ACTOR}'), ('{OTHER}');
        insert into users values ('{ACTOR}'), ('{OTHER}');
        insert into equipment values (10, 'Projector', 'Test model', 5);
        insert into events values
            (1, 'Workshop', '2030-01-01 09:00Z', '2030-01-01 10:00Z', '{OTHER}', '{ACTOR}'),
            (2, 'Conference', '2030-01-01 09:00Z', '2030-01-01 10:00Z', '{OTHER}', '{ACTOR}'),
            (3, 'Later event', '2030-01-01 10:00Z', '2030-01-01 11:00Z', null, '{ACTOR}'),
            (4, 'Growth', '2030-01-02 09:00Z', '2030-01-02 10:00Z', null, '{ACTOR}'),
            (5, 'Standalone', '2030-01-03 09:00Z', '2030-01-03 10:00Z', null, '{ACTOR}'),
            (6, 'Other account', '2030-01-04 09:00Z', '2030-01-04 10:00Z', null, '{OTHER}');
        insert into equipment_request(event_id, requested_by, quantity, equipment_type)
            values (1, '{ACTOR}', 5, 'Projector'), (2, '{ACTOR}', 4, 'Projector'),
                   (3, '{ACTOR}', 5, 'Projector'), (2, '{ACTOR}', 2, 'Projector'),
                   (4, '{ACTOR}', 2, 'Projector');
    """)
    assert len(user('select equipment_request_review_queue();')) == 5
    assert user('select equipment_request_review_queue();', OTHER) == []
    assert {row['event_id'] for row in user('select my_equipment_request_events();')} == {'1', '2', '3', '4', '5'}
    assert review(1, 'accepted', actor=OTHER)['status'] == 403
    assert review(1, 'partially_accepted', 5)['status'] == 400
    first = review(1, 'partially_accepted', 3)['reservation']['reservation_id']
    assert review(1, 'accepted')['status'] == 409
    assert review(2, 'accepted')['status'] == 409
    assert request_row(2)['status'] == 'pending'
    second = review(2, 'partially_accepted', 2)['reservation']['reservation_id']
    assert availability(1) == 0
    assert availability(3) == 5  # Adjacent events do not overlap.
    assert review(3, 'accepted')['reservation']['quantity'] == 5
    assert review(4, 'rejected')['equipment_request']['accepted_quantity'] == 0
    assert user('select my_equipment_reservations();', OTHER) == []
    assert change(first, 1, OTHER)['status'] == 404
    assert change(first, actor=OTHER)['status'] == 404
    assert change(first, 0)['status'] == 400
    assert change(first, 1)['equipment_request']['accepted_quantity'] == 1
    assert availability(2) == 2
    assert change(second, 4)['equipment_request']['status'] == 'accepted'
    assert availability(1) == 0
    assert change(first, 2)['status'] == 409
    assert request_row(1)['accepted_quantity'] == 1
    assert change(second, 2)['equipment_request']['status'] == 'partially_accepted'
    assert change(first, 3)['reservation']['quantity'] == 3
    cancelled = change(second)
    assert cancelled['cancelled'] and cancelled['equipment_request']['status'] == 'cancelled'
    assert request_row(2)['accepted_quantity'] == 0 and request_row(2)['quantity'] == 4
    assert availability(1) == 2
    assert change(first, 5)['equipment_request']['status'] == 'accepted'
    assert change(first)['cancelled'] and availability(1) == 5
    assert change(first, 1)['status'] == 404
    assert change(first)['status'] == 404
    # Increasing above the original request preserves that original quantity.
    growth = review(5, 'accepted')['reservation']['reservation_id']
    updated = change(growth, 4)
    assert updated['reservation']['quantity'] == 4
    assert updated['equipment_request']['quantity'] == 2
    assert updated['equipment_request']['accepted_quantity'] == 4
    assert availability(4) == 1
    # Both writes roll back together if synchronization fails.
    sql("""
        create function fail_test_sync() returns trigger language plpgsql as $$
        begin if new.equipment_request_id = 5 and new.accepted_quantity = 3 then
          raise exception 'Test synchronization failure'; end if; return new; end; $$;
        create trigger fail_test_sync before update on equipment_request for each row execute function fail_test_sync();
    """)
    try:
        change(growth, 3)
        raise AssertionError('Expected synchronization failure')
    except AssertionError as exc:
        assert 'Test synchronization failure' in str(exc)
    assert request_row(5)['accepted_quantity'] == 4
    assert sql(f"select quantity from equipment_reservations where reservation_id = '{growth}';") == '4'
    sql('drop trigger fail_test_sync on equipment_request; drop function fail_test_sync();')
    standalone = user("select reserve_equipment('5', 10, 2);")['reservation']['reservation_id']
    assert change(standalone, 3)['reservation']['quantity'] == 3
    assert change(standalone)['cancelled'] and availability(5) == 5
    # Simultaneous increases share the same stock lock, so only one fits.
    sql(f"""
        insert into events values
            (7, 'Race one', '2030-02-01 09:00Z', '2030-02-01 10:00Z', null, '{ACTOR}'),
            (8, 'Race two', '2030-02-01 09:00Z', '2030-02-01 10:00Z', null, '{ACTOR}');
        insert into equipment_request(event_id, requested_by, quantity, equipment_type)
            values (7, '{ACTOR}', 2, 'Projector'), (8, '{ACTOR}', 2, 'Projector');
    """)
    race = [review(i, 'accepted')['reservation']['reservation_id'] for i in (6, 7)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda reservation_id: change(reservation_id, 3), race))
    assert sum('reservation' in result for result in results) == 1
    assert sum(result.get('status') == 409 for result in results) == 1
    assert availability(7) == 0
    assert sum(request_row(i)['accepted_quantity'] for i in (6, 7)) == 5
    assert user('select my_equipment_request_events();', '') == []
    assert change(growth, 2, actor='')['status'] == 401
    # Reproduce the event-page insert failure, then verify the account policy fix.
    sql('alter table equipment_request enable row level security; grant select, insert on equipment_request to authenticated; grant usage on sequence equipment_request_equipment_request_id_seq to authenticated;')
    insert_own = f"insert into equipment_request(event_id, requested_by, quantity, equipment_type, status) values (1, '{ACTOR}', 1, 'Projector', 'pending') returning equipment_request_id;"
    try:
        user(insert_own)
        raise AssertionError('Insert should fail without an insert policy')
    except AssertionError as exc:
        assert 'row-level security' in str(exc)
    sql((ROOT / 'supabase/017_allow_own_equipment_requests.sql').read_text())
    new_id = user(insert_own)
    assert request_row(new_id)['requested_by'] == ACTOR
    assert user(f"select count(*) from equipment_request where equipment_request_id = {new_id};") == 1
    assert user(f"select count(*) from equipment_request where equipment_request_id = {new_id};", OTHER) == 0
    try:
        user(insert_own, OTHER)
        raise AssertionError('Cannot submit a request under another account')
    except AssertionError as exc:
        assert 'row-level security' in str(exc)
    try:
        user(insert_own.replace("'pending'", "'accepted'"))
        raise AssertionError('Cannot bypass review on submission')
    except AssertionError as exc:
        assert 'Use the equipment review action' in str(exc)
    print('Database checks passed: own request submission with RLS and RETURNING, spoofed ownership blocked, review/management synchronization, stock release and concurrency.')



if __name__ == '__main__':
    main()
