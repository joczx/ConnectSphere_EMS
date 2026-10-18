import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PGlite } from '../node_modules/.event-status-qa/node_modules/@electric-sql/pglite/dist/index.js';
const actor = '00000000-0000-0000-0000-000000000001';
const other = '00000000-0000-0000-0000-000000000002';
for (const type of ['text', 'integer']) test(`full acceptance only with ${type} event IDs`, async () => {
  const db = new PGlite();
  try {
    await db.exec(`
      create role anon; create role authenticated;
      create schema auth;
      create function auth.uid() returns uuid language sql as $$ select nullif(current_setting('test.actor', true), '')::uuid $$;
      create table roles(role_id integer primary key, role_name text);
      create table user_roles(user_id uuid, role_id integer);
      insert into roles values (1, 'Technical Support Staff'), (2, 'Event Coordinator');
      insert into user_roles values ('${actor}', 1);
      create table events(event_id integer primary key, event_name text, technical_support_id uuid, start_datetime timestamptz, end_datetime timestamptz, status text default 'planning');
      create table equipment(equipment_id integer primary key, total_quantity integer, equipment_type text default 'Projector', equipment_model text);
      create table equipment_request(equipment_request_id integer primary key, equipment_id integer, event_id integer, quantity integer, accepted_quantity integer default 0, status text default 'pending', equipment_type text default 'Projector', requested_by uuid, requested_at timestamptz default now(), reviewed_by uuid, reviewed_at timestamptz, reason_for_rejection text);
      create table equipment_reservations(reservation_id uuid primary key default gen_random_uuid(), event_id ${type}, equipment_id integer, equipment_request_id integer unique,
        quantity integer, starts_at timestamptz, ends_at timestamptz, created_by uuid);
      insert into events(event_id,event_name,technical_support_id,start_datetime,end_datetime) values (1, 'Mine', '${actor}', '2030-01-01', '2030-01-02'), (2, 'Other', '${other}', '2030-01-01', '2030-01-02'), (3, 'Second', '${actor}', '2030-01-01', '2030-01-02');
      insert into equipment(equipment_id,total_quantity) values (1, 10);
      set test.actor = '${actor}';
    `);
    const legacy = await readFile(new URL('../../supabase/013_link_equipment_request_reservations.sql', import.meta.url), 'utf8');
    await db.exec(legacy.slice(legacy.indexOf('create or replace function public.equipment_peak('), legacy.indexOf('create or replace function public.review_equipment_request(')));
    const repair = await readFile(new URL('../../supabase/035_reserve_equipment_event_ids.sql', import.meta.url), 'utf8');
    await db.exec(repair); await db.exec(repair);

    await db.exec(await readFile(new URL('../../supabase/036_reserve_before_equipment_acceptance.sql', import.meta.url), 'utf8'));
    await db.exec(await readFile(new URL('../../supabase/036_reserve_before_equipment_acceptance.sql', import.meta.url), 'utf8'));
    await db.exec(await readFile(new URL('../../supabase/037_full_equipment_acceptance.sql', import.meta.url), 'utf8'));
    await db.exec(await readFile(new URL('../../supabase/037_full_equipment_acceptance.sql', import.meta.url), 'utf8'));
    await db.exec(`insert into equipment_request(equipment_request_id,event_id,quantity,requested_by) values
      (11,1,3,'${other}'),(12,3,4,'${other}'),(13,3,2,'${other}'),(14,2,1,'${other}'),(15,3,1,'${other}'),(16,3,5,'${other}');`);
    const reserve = async (id, qty) => (await db.query('select reserve_equipment_for_request($1,1,$2) as result',[id,qty])).rows[0].result;
    const review = async (id, outcome='accepted', qty=null) => (await db.query("select review_equipment_request($1,$2,1,$3,'Not needed') as result",[id,outcome,qty])).rows[0].result;
    const peak = async () => Number((await db.query("select equipment_peak(1,'2030-01-01','2030-01-02') as qty")).rows[0].qty);
    assert.equal((await review(11)).status,409);
    // Direct reservations are intentionally not associated with a request.
    await db.query("select reserve_equipment('1',1,1)");
    assert.equal((await review(11)).status,409);
    await db.exec('update user_roles set role_id=2');
    assert.equal((await reserve(11,3)).status,403);
    assert.equal((await review(11)).status,403);
    await db.exec('update user_roles set role_id=1');
    assert.equal((await reserve(14,1)).status,403);
    const hold=await reserve(11,3);
    assert.equal(hold.equipment_request.status,'pending');
    assert.equal(hold.reservation.equipment_request_id,11);
    assert.equal(await peak(),4);
    assert.equal((await reserve(11,3)).status,409);
    const accepted=await review(11);
    assert.equal(accepted.equipment_request.status,'accepted');
    assert.equal(await peak(),4); // Acceptance does not reserve again.
    assert.equal((await review(11)).status,409);
    assert.equal((await db.query('select count(*)::integer as n from equipment_reservations')).rows[0].n,2);
    assert.equal((await reserve(12,2)).status,400);
    assert.equal((await review(12,'partially_accepted',2)).status,400);
    await reserve(12,4);
    assert.equal((await review(12)).equipment_request.accepted_quantity,4);
    assert.equal(await peak(),8);
    assert.equal((await reserve(16,5)).status,409);
    const pending=await reserve(13,2);
    // Rejection cannot leave an outstanding hold.
    assert.equal((await review(13,'rejected')).status,409);
    assert.equal((await db.query('select change_equipment_reservation($1,1,false) as result',[pending.reservation.reservation_id])).rows[0].result.status,409);
    assert.equal((await db.query('select status from equipment_request where equipment_request_id=13')).rows[0].status,'pending');
    await db.query('select change_equipment_reservation($1,null,true)',[pending.reservation.reservation_id]);
    assert.equal((await db.query('select status from equipment_request where equipment_request_id=13')).rows[0].status,'pending');
    assert.equal((await review(13)).status,409);
    assert.equal((await review(13,'rejected')).equipment_request.status,'rejected');
    assert.equal(await peak(),8);
    await assert.rejects(db.exec("update equipment_request set status='accepted',equipment_id=1,accepted_quantity=1 where equipment_request_id=15"),/Reserve equipment linked/);
    const queue=(await db.query('select equipment_request_review_queue() as rows')).rows[0].rows;
    assert.equal(queue.some(row=>row.equipment_request_id===14),false);
    assert.equal(queue.find(row=>row.equipment_request_id===11).linked_reservation.quantity,3);
    await db.exec("set test.actor=''");
    assert.equal((await reserve(15,1)).status,401);
  } finally { await db.close(); }
});
