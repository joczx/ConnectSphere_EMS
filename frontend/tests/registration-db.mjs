// node --test frontend/tests/registration-db.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PGlite } from '../node_modules/.event-status-qa/node_modules/@electric-sql/pglite/dist/index.js';

test('registration migration enforces ownership, period, capacity and lifecycle compatibility', async () => {
  const db = new PGlite();
  const organiser = '00000000-0000-0000-0000-000000000001';
  const attendee = '00000000-0000-0000-0000-000000000002';
  const nextAttendee = '00000000-0000-0000-0000-000000000003';
  const actor = async id => db.query("select set_config('request.jwt.claim.sub', $1, false)", [id]);
  const rpc = async (name, args = []) => {
    if (name === 'register_for_event' && args.length === 1) args = [...args, 'Alex Tan', 'alex@example.com', '+65 8123 4567'];
    return (await db.query(`select public.${name}(${args.map((_, i) => '$' + (i + 1)).join(',')}) as result`, args)).rows[0].result;
  };
  try {
    await db.exec(`
      create role anon; create role authenticated; create role service_role bypassrls;
      create schema auth;
      create table auth.users(id uuid primary key);
      create function auth.uid() returns uuid language sql stable as $$
        select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
      $$;
      create type public.event_status as enum ('planning','pending_safety_checks','confirmed','completed','cancelled');
      create table public.events (
        event_id integer primary key, event_name text, description text,
        event_organiser_id uuid, event_coordinator_id uuid, status public.event_status,
        start_datetime timestamptz, end_datetime timestamptz, capacity_needed integer,
        registration_ready boolean default true, registration_needs text,
        safety_rework_required boolean default false, safety_rework_requested_at timestamptz,
        safety_rework_arrangements jsonb, safety_approved_at timestamptz,
        updated_at timestamptz default now()
      );
      create table public.operational_safety_decision(event_id integer, safety_officer_id uuid, outcome text, created_at timestamptz);
      create function public.has_booking_role(text) returns boolean language sql as $$
        select case when $1 = 'event_organiser' then auth.uid() = '${organiser}'::uuid
          when $1 = 'attendee' then auth.uid() in ('${attendee}'::uuid, '${nextAttendee}'::uuid)
          else false end;
      $$;
      create function public.event_safety_check_blockers(public.events) returns text[] language sql as $$ select '{}'::text[]; $$;
      create function public.event_confirmation_blockers(public.events) returns text[] language sql as $$ select '{}'::text[]; $$;
      insert into auth.users values ('${organiser}'), ('${attendee}'), ('${nextAttendee}');
      insert into public.events(event_id,event_name,description,event_organiser_id,status,start_datetime,end_datetime,capacity_needed,safety_approved_at)
      values (1,'Conference','Public description','${organiser}','confirmed',now()+interval '10 days',now()+interval '11 days',1,now());
    `);
    await db.exec(await readFile(new URL('../../supabase/046_event_registration.sql', import.meta.url), 'utf8'));
    await db.exec(await readFile(new URL('../../supabase/047_attendee_registration_access.sql', import.meta.url), 'utf8'));
    await db.exec(await readFile(new URL('../../supabase/048_attendee_registration_details.sql', import.meta.url), 'utf8'));
    // Install the actual updated lifecycle function as on the deployed database.
    await db.exec('create trigger guard_event_lifecycle before insert or update on public.events for each row execute function public.guard_event_lifecycle()');
    const future = new Date(Date.now() + 86400000).toISOString();
    const later = new Date(Date.now() + 172800000).toISOString();
    const past = new Date(Date.now() - 86400000).toISOString();
    await actor(attendee);
    for (const details of [ ['', 'alex@example.com', '+65 8123 4567'], ['Alex', 'invalid', '+65 8123 4567'], ['Alex', 'alex@example.com', '-------'], ['Alex', 'alex@example.com', null] ]) {
      assert.equal((await rpc('register_for_event', [1, ...details])).status, 400);
    }
    assert.equal((await rpc('set_event_registration_period', [1, future, later, true])).status, 403);
    await actor(organiser);
    assert.equal((await rpc('attendee_registration_events')).status, 403);
    assert.equal((await rpc('register_for_event', [1])).status, 403);
    assert.equal((await rpc('set_event_registration_period', [1, later, future, true])).status, 400);
    let result = await rpc('set_event_registration_period', [1, future, later, true]);
    assert.equal(result.event.status, 'confirmed');
    assert.ok(result.event.safety_approved_at, 'registration edits preserve safety approval');
    await actor(attendee);
    assert.match((await rpc('register_for_event', [1])).error, /not yet open/);
    assert.equal((await rpc('attendee_registration_events')).events[0].registration_status, 'not_open');
    await assert.rejects(db.query('update public.events set waiting_list_enabled=false where event_id=1'), /assigned Event Organiser/);
    await actor(organiser);
    result = await rpc('set_event_registration_period', [1, past, future, true]);
    assert.equal(result.event.status, 'confirmed');
    await actor(attendee);
    assert.equal((await rpc('register_for_event', [1])).registration.status, 'registered');
    assert.equal((await rpc('register_for_event', [1])).registration.status, 'registered');
    const saved = (await db.query('select * from public.event_registration')).rows[0];
    assert.equal(saved.full_name, 'Alex Tan');
    assert.equal(saved.contact_email, 'alex@example.com');
    assert.equal(saved.contact_phone, '+65 8123 4567');
    assert.equal((await db.query('select * from public.registration_email_outbox')).rows.length, 1);
    await db.exec('update public.registration_email_outbox set sent_at=now()');
    assert.equal((await rpc('register_for_event', [1])).notification, 'sent');
    await actor(nextAttendee);
    assert.equal((await rpc('register_for_event', [1])).registration.status, 'waiting_list');
    const queued = (await db.query('select * from public.registration_email_outbox order by id')).rows;
    assert.match(queued[0].body, /registration is confirmed/);
    assert.match(queued[1].body, /does not confirm a place/);
    const info = (await rpc('attendee_registration_events')).events[0];
    assert.equal(info.my_registration, 'waiting_list');
    assert.equal(info.registration_status, 'open');
    assert.equal(info.event_organiser_id, undefined);
    await db.exec(`delete from public.event_registration where attendee_id='${nextAttendee}'`);
    await actor(organiser);
    await rpc('set_event_registration_period', [1, past, future, false]);
    await actor(nextAttendee);
    assert.match((await rpc('register_for_event', [1])).error, /full/);
    await actor(organiser);
    const earlier = new Date(Date.now() - 172800000).toISOString();
    await rpc('set_event_registration_period', [1, earlier, past, false]);
    await actor(nextAttendee);
    assert.match((await rpc('register_for_event', [1])).error, /closed/);
    assert.equal((await rpc('attendee_registration_events')).events[0].registration_status, 'closed');
    await actor(organiser);
    assert.equal((await rpc('set_event_registration_period', [1, past, future, false])).status, 409);
    await actor('');
    assert.equal((await rpc('attendee_registration_events')).status, 401);
    assert.equal((await rpc('register_for_event', [1])).status, 401);
    // Authenticated clients cannot bypass the controlled registration function.
    await db.exec('set role authenticated');
    await actor(attendee);
    const ownRows = (await db.query('select * from public.event_registration')).rows;
    assert.equal(ownRows.length, 1);
    assert.equal(ownRows[0].attendee_id, attendee);
    await assert.rejects(db.exec(`insert into public.event_registration(event_id,attendee_id,status) values (1,'${nextAttendee}','registered')`), /permission denied/);
    await assert.rejects(db.exec('select * from public.registration_email_outbox'), /permission denied/);
    await db.exec('reset role');
  } finally { await db.close(); }
});
