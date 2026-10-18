import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PGlite } from '../node_modules/.event-status-qa/node_modules/@electric-sql/pglite/dist/index.js';
const actor = '00000000-0000-0000-0000-000000000001';
const other = '00000000-0000-0000-0000-000000000002';
for (const type of ['text', 'integer']) test(`direct reservations support ${type} IDs and enforce role, assignment, duplicate and stock rules`, async () => {
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
      create table events(event_id integer primary key, event_name text, technical_support_id uuid, start_datetime timestamptz, end_datetime timestamptz);
      create table equipment(equipment_id integer primary key, total_quantity integer);
      create table equipment_request(equipment_request_id integer, equipment_id integer, event_id integer, quantity integer, accepted_quantity integer, status text);
      create table equipment_reservations(reservation_id serial primary key, event_id ${type}, equipment_id integer, equipment_request_id integer,
        quantity integer, starts_at timestamptz, ends_at timestamptz, created_by uuid);
      insert into events values (1, 'Mine', '${actor}', '2030-01-01', '2030-01-02'), (2, 'Other', '${other}', '2030-01-01', '2030-01-02'), (3, 'Second', '${actor}', '2030-01-01', '2030-01-02');
      insert into equipment values (1, 10);
      set test.actor = '${actor}';
    `);
    const legacy = await readFile(new URL('../../supabase/013_link_equipment_request_reservations.sql', import.meta.url), 'utf8');
    await db.exec(legacy.slice(legacy.indexOf('create or replace function public.equipment_peak('), legacy.indexOf('create or replace function public.review_equipment_request(')));
    const repair = await readFile(new URL('../../supabase/035_reserve_equipment_event_ids.sql', import.meta.url), 'utf8');
    await db.exec(repair); await db.exec(repair);
    const reserve = async (id, quantity) => (await db.query('select reserve_equipment($1, 1, $2) as result', [String(id), quantity])).rows[0].result;
    await db.exec("update user_roles set role_id = 2");
    assert.equal((await reserve(1, 3)).status, 403);
    await db.exec("update user_roles set role_id = 1");
    assert.equal((await reserve(2, 3)).status, 403);
    assert.equal((await reserve(999, 3)).status, 404);
    const saved = await reserve(1, 3);
    assert.equal(saved.reservation.quantity, 3);
    assert.equal(String(saved.reservation.event_id), '1');
    assert.equal((await reserve(1, 1)).status, 409);
    const shortage = await reserve(3, 8);
    assert.equal(shortage.status, 409);
    assert.equal(shortage.available_quantity, 7);
    assert.equal((await reserve(3, 7)).reservation.quantity, 7);
    assert.equal((await db.query("select has_function_privilege('authenticated', 'reserve_equipment_assigned(text,integer,integer)', 'EXECUTE') as allowed")).rows[0].allowed, false);
    await db.exec("set test.actor = ''");
    assert.equal((await reserve(1, 1)).status, 401);
  } finally { await db.close(); }
});
