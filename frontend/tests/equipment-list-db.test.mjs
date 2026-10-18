import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PGlite } from '../node_modules/.event-status-qa/node_modules/@electric-sql/pglite/dist/index.js';
const actor = '00000000-0000-0000-0000-000000000001';
const other = '00000000-0000-0000-0000-000000000002';
for (const type of ['text', 'integer']) test(`equipment readers support ${type} reservation event IDs and keep account ownership`, async () => {
  const db = new PGlite();
  try {
    await db.exec(`
      create schema auth;
      create function auth.uid() returns uuid language sql as $$ select '${actor}'::uuid $$;
      create table events(event_id integer primary key, event_name text, event_organiser_id uuid);
      create table equipment(equipment_id integer primary key, equipment_type text, equipment_model text, total_quantity integer);
      create table equipment_request(equipment_request_id integer, event_id integer, requested_by uuid, requested_at timestamptz);
      create table equipment_reservations(reservation_id integer, event_id ${type}, equipment_id integer, equipment_request_id integer,
        quantity integer, starts_at timestamptz, ends_at timestamptz, created_at timestamptz, created_by uuid);
      create function equipment_peak(integer, timestamptz, timestamptz) returns bigint language sql as $$ select 0::bigint $$;
      insert into events values (1, 'Mine', '${actor}'), (2, 'Other', '${other}');
      insert into equipment values (1, 'Projector', 'Model', 10);
      insert into equipment_request values (1, 1, '${actor}', now()), (2, 2, '${other}', now());
      insert into equipment_reservations values (1, '1', 1, 1, 2, now(), now()+interval '1 hour', now(), '${actor}'),
        (2, '2', 1, 2, 2, now(), now()+interval '1 hour', now(), '${other}');
    `);
    if (type === 'integer') {
      await assert.rejects(db.query('select * from events e join equipment_reservations r on e.event_id::text = r.event_id'), /operator does not exist/);
    }
    const sql = await readFile(new URL('../../supabase/033_equipment_list_event_ids.sql', import.meta.url), 'utf8');
    await db.exec(sql);
    await db.exec(sql); // Safe to apply again.
    for (const name of ['equipment_request_review_queue', 'my_equipment_request_events', 'my_equipment_reservations']) {
      const rows = (await db.query(`select ${name}() as result`)).rows[0].result;
      assert.equal(rows.length, 1);
      assert.equal(rows[0].event_name, 'Mine');
    }
  } finally { await db.close(); }
});
