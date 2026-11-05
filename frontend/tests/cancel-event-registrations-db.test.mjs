import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PGlite } from '../node_modules/.event-status-qa/node_modules/@electric-sql/pglite/dist/index.js';

// Execute the production cancellation RPC, notification triggers and migration.
test('event cancellation atomically withdraws registered and waitlisted attendees', async () => {
  const db = new PGlite();
  const owner = '00000000-0000-0000-0000-000000000001';
  const registered = '00000000-0000-0000-0000-000000000002';
  const waiting = '00000000-0000-0000-0000-000000000003';
  const withdrawn = '00000000-0000-0000-0000-000000000004';
  const actor = id => db.query("select set_config('request.jwt.claim.sub', $1, false)", [id]);
  const cancel = async id => (await db.query('select public.cancel_planned_event($1) as result', [id])).rows[0].result;
  try {
    await db.exec(`
      create role anon; create role authenticated; create schema auth;
      create function auth.uid() returns uuid language sql stable as $$
        select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
      $$;
      create table public.events(event_id integer primary key, event_name text, status text,
        event_organiser_id uuid, event_coordinator_id uuid, start_datetime timestamptz, end_datetime timestamptz);
      create table public.event_registration(event_id integer references public.events, attendee_id uuid,
        status text, withdrawn_at timestamptz, primary key(event_id, attendee_id));
      create table public.venues(venue_id uuid, venue_name text);
      create table public.venue_booking_requests(event_id integer, venue_id uuid, status text, reviewed_at timestamptz);
      create table public.notifications(recipient_id uuid, kind text, title text, body text, link text);
      create function public.notify_user(uuid,text,text,text,text) returns void language sql as $$
        insert into public.notifications values ($1,$2,$3,$4,$5);
      $$;
      insert into public.events values
        (1,'Cancelled event','confirmed','${owner}',null,now()+interval '1 day',now()+interval '2 days'),
        (2,'Unaffected event','confirmed','${owner}',null,now()+interval '1 day',now()+interval '2 days'),
        (3,'Previously cancelled','cancelled','${owner}',null,now()-interval '2 days',now()-interval '1 day');
      insert into public.event_registration values
        (1,'${registered}','registered',null), (1,'${waiting}','waiting_list',null),
        (1,'${withdrawn}','withdrawn','2026-01-01T00:00:00Z'),
        (2,'${registered}','registered',null), (3,'${registered}','registered',null);
    `);
    await db.exec(await readFile(new URL('../../supabase/057_notify_event_registration.sql', import.meta.url), 'utf8'));
    const lifecycle = await readFile(new URL('../../supabase/034_operational_safety_reviews.sql', import.meta.url), 'utf8');
    const start = lifecycle.indexOf('create or replace function public.cancel_planned_event(');
    await db.exec(lifecycle.slice(start, lifecycle.indexOf('\n$$;', start) + 4));
    const migration = await readFile(new URL('../../supabase/062_withdraw_registrations_on_event_cancellation.sql', import.meta.url), 'utf8');
    await db.exec(migration);
    const repaired = (await db.query('select * from public.event_registration where event_id=3')).rows[0];
    assert.equal(repaired.status, 'withdrawn');
    assert.ok(repaired.withdrawn_at);
    await db.exec(migration);
    assert.deepEqual((await db.query('select * from public.event_registration where event_id=3')).rows[0], repaired);
    await actor(registered);
    assert.equal((await cancel(1)).status, 404);
    assert.equal((await db.query('select status from public.events where event_id=1')).rows[0].status, 'confirmed');
    await actor(owner);
    assert.equal((await cancel(1)).event.status, 'cancelled');
    const rows = (await db.query('select * from public.event_registration where event_id=1 order by attendee_id')).rows;
    assert.deepEqual(rows.map(row => row.status), ['withdrawn', 'withdrawn', 'withdrawn']);
    assert.ok(rows[0].withdrawn_at);
    assert.ok(rows[1].withdrawn_at);
    assert.equal(new Date(rows[2].withdrawn_at).toISOString(), '2026-01-01T00:00:00.000Z');
    assert.equal((await db.query("select count(*)::int as total from public.event_registration where event_id=1 and status='registered'")).rows[0].total, 0);
    assert.equal((await db.query('select status from public.event_registration where event_id=2')).rows[0].status, 'registered');
    const cancelled = (await db.query("select recipient_id from public.notifications where kind='event_cancelled' order by recipient_id")).rows;
    assert.deepEqual(cancelled.map(row => row.recipient_id), [registered, waiting]);
    const before = (await db.query('select count(*)::int as total from public.notifications')).rows[0].total;
    assert.equal((await cancel(1)).status, 409);
    assert.deepEqual((await db.query('select * from public.event_registration where event_id=1 order by attendee_id')).rows, rows);
    assert.equal((await db.query('select count(*)::int as total from public.notifications')).rows[0].total, before);
    // A failed withdrawal must roll back the event cancellation as well.
    await db.exec(`create function public.refuse_withdrawal() returns trigger language plpgsql as $$
      begin raise exception 'test withdrawal failure'; end; $$;
      create trigger refuse_withdrawal before update on public.event_registration
      for each row when (old.event_id=2) execute function public.refuse_withdrawal();`);
    await assert.rejects(cancel(2), /test withdrawal failure/);
    assert.equal((await db.query('select status from public.events where event_id=2')).rows[0].status, 'confirmed');
    assert.equal((await db.query('select status from public.event_registration where event_id=2')).rows[0].status, 'registered');
    assert.equal((await db.query('select count(*)::int as total from public.notifications')).rows[0].total, before);
  } finally { await db.close(); }
});
