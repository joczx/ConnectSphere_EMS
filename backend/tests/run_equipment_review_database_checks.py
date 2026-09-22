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
    return sql(f"set role authenticated; set request.jwt.claim.sub = '{actor}'; {query}")


def review(request_id, outcome, quantity='null', actor=ACTOR):
    return json.loads(user(f"select review_equipment_request({request_id}, '{outcome}', 10, {quantity}, 'Not enough equipment');", actor))


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
            start_datetime timestamptz, end_datetime timestamptz, technical_support_id uuid);
    """)
    for file in ['006_create_equipment', '005_create_equipment_request.sql',
                 '010_equipment_reservations_existing_catalogue.sql', '011_manage_equipment_reservations.sql',
                 '012_review_equipment_requests.sql', '013_link_equipment_request_reservations.sql', '014_equipment_access_without_roles.sql']:
        sql((ROOT / 'supabase' / file).read_text())
    sql(f"""
        insert into auth.users values ('{ACTOR}'), ('{OTHER}');
        insert into users values ('{ACTOR}'), ('{OTHER}');
        insert into events values
            (1, 'Workshop', '2030-01-01 09:00Z', '2030-01-01 10:00Z', '{ACTOR}'),
            (2, 'Conference', '2030-01-01 09:00Z', '2030-01-01 10:00Z', '{ACTOR}'),
            (3, 'Later event', '2030-01-01 10:00Z', '2030-01-01 11:00Z', '{ACTOR}');
        insert into equipment values (10, 'Projector', 'Test model', 5);
        insert into equipment_request(event_id, requested_by, quantity, equipment_type)
            values (1, '{OTHER}', 5, 'Projector'), (2, '{OTHER}', 4, 'Projector'),
                   (3, '{OTHER}', 5, 'Projector'), (2, '{OTHER}', 2, 'Projector');
    """)
    assert len(json.loads(user('select equipment_request_review_queue();'))) == 4
    assert len(json.loads(user('select equipment_request_review_queue();', OTHER))) == 4
    assert len(json.loads(user('select equipment_events();', OTHER))) == 3
    assert review(1, 'partially_accepted', 5)['status'] == 400
    result = review(1, 'partially_accepted', 3, actor=OTHER)['equipment_request']
    assert result['quantity'] == 5 and result['accepted_quantity'] == 3
    assert result['reviewed_by'] == OTHER and result['reviewed_at']
    assert review(1, 'accepted')['status'] == 409
    assert review(2, 'accepted')['status'] == 409
    assert sql('select count(*) from equipment_reservations where equipment_request_id = 2;') == '0'
    assert sql('select status from equipment_request where equipment_request_id = 2;') == 'pending'
    assert review(2, 'partially_accepted', 2)['equipment_request']['accepted_quantity'] == 2
    assert review(3, 'accepted')['equipment_request']['accepted_quantity'] == 5
    assert review(4, 'rejected')['equipment_request']['accepted_quantity'] == 0
    assert sql("select equipment_peak(10, '2030-01-01 09:00Z', '2030-01-01 10:00Z');") == '5'
    assert sql('select count(*) from equipment_reservations;') == '3'
    reserved = json.loads(sql("select row_to_json(r) from equipment_reservations r where equipment_request_id = 1;"))
    assert reserved['event_id'] == '1' and reserved['equipment_id'] == 10
    assert reserved['quantity'] == 3 and reserved['created_by'] == OTHER
    assert reserved['starts_at'].startswith('2030-01-01T09:00:00')
    assert sql('select count(*) from equipment_reservations where equipment_request_id = 4;') == '0'
    assert json.loads(user(f"select update_equipment_reservation('{reserved['reservation_id']}', 1);", OTHER))['status'] == 409
    assert json.loads(user(f"select cancel_equipment_reservation('{reserved['reservation_id']}');", OTHER))['status'] == 409
    assert 'already reserved' in json.loads(user("select reserve_equipment('2', 10, 1);", OTHER))['error']
    assert json.loads(user("select equipment_availability('2');"))['equipment'][0]['available_quantity'] == 0
    try:
        sql("update events set end_datetime = end_datetime + interval '1 hour' where event_id = 1;")
        raise AssertionError('Date edits must be blocked')
    except AssertionError as exc:
        assert 'Release equipment reservations' in str(exc)
    sql('grant select, update on equipment_request to authenticated;')
    try:
        user("update equipment_request set accepted_quantity = 5 where equipment_request_id = 1;")
        raise AssertionError('Direct review mutation must be blocked')
    except AssertionError as exc:
        assert 'Use the equipment review action' in str(exc)
    # Competing event requests must serialize on the catalogue item lock.
    sql(f"""
        insert into events values
            (4, 'Race one', '2030-01-02 09:00Z', '2030-01-02 10:00Z', '{ACTOR}'),
            (5, 'Race two', '2030-01-02 09:00Z', '2030-01-02 10:00Z', '{ACTOR}');
        insert into equipment_request(event_id, requested_by, quantity, equipment_type)
            values (4, '{OTHER}', 4, 'Projector'), (5, '{OTHER}', 4, 'Projector');
    """)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda request_id: review(request_id, 'accepted'), [5, 6]))
    assert sum('equipment_request' in result for result in results) == 1
    assert sum(result.get('status') == 409 for result in results) == 1
    # Separate requests for the same event/model get separate linked reservations.
    sql(f"""
        insert into events values (6, 'Multiple requests', '2030-01-03 09:00Z', '2030-01-03 10:00Z', '{ACTOR}');
        insert into equipment_request(event_id, requested_by, quantity, equipment_type)
            values (6, '{OTHER}', 2, 'Projector'), (6, '{OTHER}', 3, 'Projector');
    """)
    assert review(7, 'accepted')['reservation']['quantity'] == 2
    assert review(8, 'accepted')['reservation']['quantity'] == 3
    assert sql("select count(*) from equipment_reservations where event_id = '6';") == '2'
    assert sql("select equipment_peak(10, '2030-01-03 09:00Z', '2030-01-03 10:00Z');") == '5'
    availability = json.loads(user("select equipment_availability('6');"))['equipment']
    assert len(availability) == 1
    assert availability[0]['reserved_quantity'] == 5 and availability[0]['available_quantity'] == 0
    # Older accepted rows without a linked reservation continue consuming stock.
    sql(f"""
        insert into events values (7, 'Legacy', '2030-01-04 09:00Z', '2030-01-04 10:00Z', '{ACTOR}');
        insert into equipment_request(event_id, requested_by, quantity, accepted_quantity, equipment_type, equipment_id, status)
            values (7, '{OTHER}', 4, 2, 'Projector', 10, 'partially_accepted');
    """)
    assert sql("select equipment_peak(10, '2030-01-04 09:00Z', '2030-01-04 10:00Z');") == '2'
    # Upgrade from unrestricted signed-in access to account ownership filtering.
    sql((ROOT / 'supabase/015_account_equipment_requests.sql').read_text())
    sql(f"""
        alter table events add column event_organiser_id uuid;
        insert into events values
            (8, 'My empty event', '2030-01-05 09:00Z', '2030-01-05 10:00Z', null, '{ACTOR}'),
            (9, 'Other empty event', '2030-01-06 09:00Z', '2030-01-06 10:00Z', null, '{OTHER}'),
            (10, 'Requested event', '2030-01-07 09:00Z', '2030-01-07 10:00Z', null, '{OTHER}');
    """)
    request_id = int(sql(f"insert into equipment_request(event_id, requested_by, quantity, equipment_type) values (10, '{ACTOR}', 2, 'Projector') returning equipment_request_id;"))
    mine = json.loads(user('select equipment_request_review_queue();'))
    assert [row['equipment_request_id'] for row in mine] == [request_id]
    own_events = json.loads(user('select my_equipment_request_events();'))
    assert {row['event_id'] for row in own_events} == {'8', '10'}
    assert all(row['requested_by'] == OTHER for row in json.loads(user('select equipment_request_review_queue();', OTHER)))
    assert review(request_id, 'accepted', actor=OTHER)['status'] == 403
    assert review(request_id, 'accepted')['reservation']['quantity'] == 2
    assert json.loads(user("select reserve_equipment('9', 10, 1);"))['status'] == 403
    assert json.loads(user("select reserve_equipment('8', 10, 1);"))['reservation']['quantity'] == 1
    assert sql("set role authenticated; select my_equipment_request_events();") == '[]'
    print('Database checks passed: account-owned events, own requests, cross-account review protection, linked reservations, overlap and concurrency checks.')



if __name__ == '__main__':
    main()
