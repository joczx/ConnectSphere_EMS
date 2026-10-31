// Runs the forward migration and the real production safety-submission RPC in
// embedded PostgreSQL. Install the ignored QA dependency documented in
// docs/event-status-management.md before running this file.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PGlite } from '../node_modules/.event-status-qa/node_modules/@electric-sql/pglite/dist/index.js';

const coordinator = '00000000-0000-0000-0000-000000000001';
const organiser = '00000000-0000-0000-0000-000000000002';
const safetyOfficer = '00000000-0000-0000-0000-000000000003';
const otherSafetyOfficer = '00000000-0000-0000-0000-000000000005';
const venue = '00000000-0000-0000-0000-000000000004';

function functionDefinition(sql, signature) {
  const start = sql.indexOf(signature);
  assert.notEqual(start, -1, `Missing production function: ${signature}`);
  const end = sql.indexOf('\n$$;', start);
  assert.notEqual(end, -1, `Unterminated production function: ${signature}`);
  return sql.slice(start, end + 4);
}

test('053 removes registration readiness from the real safety lifecycle', async t => {
  const db = new PGlite();
  try {
    await db.exec(`
      create role anon; create role authenticated; create schema auth;
      create function auth.uid() returns uuid language sql stable as $$
        select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
      $$;
      create type public.event_status as enum ('planning','pending_safety_checks','confirmed','completed','cancelled');
      create table public.users (user_id uuid primary key, name text);
      create table public.events (
        event_id serial primary key, event_name text,
        status public.event_status not null default 'planning',
        event_organiser_id uuid, event_coordinator_id uuid, safety_officer_id uuid,
        start_datetime timestamptz, end_datetime timestamptz, capacity_needed integer,
        equipment_requirements jsonb, registration_needs text,
        registration_ready boolean not null default false,
        registration_opens_at timestamptz, registration_closes_at timestamptz,
        waiting_list_enabled boolean not null default false,
        safety_rework_required boolean not null default false,
        safety_rework_requested_at timestamptz,
        safety_rework_arrangements text[] not null default array[]::text[],
        safety_approved_at timestamptz, updated_at timestamptz not null default now()
      );
      create table public.venues (
        venue_id uuid primary key, deleted_at timestamptz, suitable boolean not null default true
      );
      create table public.venue_booking_requests (
        booking_id serial primary key, event_id integer, venue_id uuid, status text,
        starts_at timestamptz, ends_at timestamptz, attendance integer,
        reviewed_at timestamptz default now()
      );
      create table public.equipment (equipment_id serial primary key, equipment_type text);
      create table public.equipment_request (
        equipment_request_id serial primary key, event_id integer, quantity integer
      );
      create table public.equipment_reservations (
        reservation_id serial primary key, event_id integer, equipment_id integer,
        equipment_request_id integer, quantity integer, starts_at timestamptz,
        ends_at timestamptz, created_at timestamptz default now()
      );
      create table public.operational_safety_decision (
        safety_decision_id bigint generated always as identity primary key,
        event_id integer not null, safety_officer_id uuid not null,
        outcome text not null, remarks text, affected_arrangements text[] not null,
        created_at timestamptz not null default clock_timestamp()
      );
      create function public.venue_shortfalls_for_event(public.venues, public.events)
        returns text[] language sql as $$
          select case when $1.suitable then '{}'::text[] else array['Unsuitable'] end;
        $$;
      create function public.has_safety_officer_role() returns boolean language sql stable as $$
        select auth.uid() in ('${safetyOfficer}'::uuid, '${otherSafetyOfficer}'::uuid);
      $$;
      create function public.notify_user(uuid,text,text,text,text) returns void language sql as $$ select; $$;
      create function public.set_event_registration_ready(integer,boolean)
        returns jsonb language sql as $$ select '{}'::jsonb; $$;
      create function public.guard_event_lifecycle() returns trigger language plpgsql as $$
        begin return new; end;
      $$;
      create trigger guard_event_lifecycle before insert or update on public.events
        for each row execute function public.guard_event_lifecycle();
      insert into public.users values
        ('${coordinator}','Coordinator'), ('${organiser}','Organiser'),
        ('${safetyOfficer}','Safety Officer'), ('${otherSafetyOfficer}','Other Safety Officer');
      insert into public.venues(venue_id) values ('${venue}');
      insert into public.equipment(equipment_type) values ('Microphone');
    `);

    // Use the repository's production submission RPC, not a test reimplementation.
    const submitMigration = await readFile(new URL('../../supabase/048_submit_for_safety_checks.sql', import.meta.url), 'utf8');
    await db.exec(functionDefinition(submitMigration,
      'create or replace function public.submit_event_for_safety_checks(p_event_id integer)'));

    // A deployed event that had already passed Safety but was held by the old gate.
    await db.exec(`
      insert into public.events(event_id,event_name,status,event_coordinator_id,safety_officer_id,
        start_datetime,end_datetime,capacity_needed,equipment_requirements,registration_needs,
        registration_ready,safety_approved_at)
      values(99,'Already approved','pending_safety_checks','${coordinator}','${safetyOfficer}',
        now()+interval '2 days',now()+interval '3 days',10,'[]','Registration required',false,now());
      insert into public.venue_booking_requests(event_id,venue_id,status,starts_at,ends_at,attendance)
      select event_id,'${venue}','approved',start_datetime,end_datetime,capacity_needed
      from public.events where event_id=99;
    `);

    await db.exec(await readFile(new URL('../../supabase/053_remove_registration_readiness.sql', import.meta.url), 'utf8'));

    const actor = id => db.query('select set_config($1,$2,false)', ['request.jwt.claim.sub', id]);
    const createEvent = async (equipment = [], registration = 'Managed by an external provider') => (
      await db.query(`insert into public.events(event_name,event_organiser_id,event_coordinator_id,safety_officer_id,
        start_datetime,end_datetime,capacity_needed,equipment_requirements,registration_needs,
        registration_opens_at,registration_closes_at)
        values('Conference',$1,$2,$3,now()+interval '2 days',now()+interval '3 days',100,$4::jsonb,$5,
          now()+interval '1 hour',now()+interval '1 day') returning event_id`,
      [organiser, coordinator, safetyOfficer, JSON.stringify(equipment), registration])
    ).rows[0].event_id;
    const book = id => db.query(`insert into public.venue_booking_requests
      (event_id,venue_id,status,starts_at,ends_at,attendance)
      select event_id,$2,'approved',start_datetime,end_datetime,capacity_needed
      from public.events where event_id=$1`, [id, venue]);
    const reserve = (id, quantity) => db.query(`insert into public.equipment_reservations
      (event_id,equipment_id,quantity,starts_at,ends_at)
      select event_id,1,$2,start_datetime,end_datetime from public.events where event_id=$1`, [id, quantity]);

    await t.test('valid submission and assigned Safety Officer approval confirm directly', async () => {
      const id = await createEvent([{ equipment_type: 'Microphone', quantity: 2 }]);
      await book(id); await reserve(id, 2); await actor(coordinator);
      const submitted = (await db.query('select public.submit_event_for_safety_checks($1) result', [id])).rows[0].result;
      assert.equal(submitted.event.status, 'pending_safety_checks');

      await actor(otherSafetyOfficer);
      const refused = (await db.query(
        "select public.record_safety_decision($1,'approved',null,'{}') result", [id]
      )).rows[0].result;
      assert.equal(refused.status, 404, 'another Safety Officer cannot decide the event');

      await actor(safetyOfficer);
      const approved = (await db.query(
        "select public.record_safety_decision($1,'approved',null,'{}') result", [id]
      )).rows[0].result;
      assert.equal(approved.event.status, 'confirmed');
      assert.equal(approved.message, 'Safety arrangements approved. The event is confirmed.');
    });

    await t.test('registration details neither block nor undo confirmation', async () => {
      const id = await createEvent(); await book(id); await actor(coordinator);
      assert.equal((await db.query('select public.submit_event_for_safety_checks($1) result', [id])).rows[0].result.event.status,
        'pending_safety_checks');
      await actor(safetyOfficer);
      assert.equal((await db.query(
        "select public.record_safety_decision($1,'approved',null,'{}') result", [id]
      )).rows[0].result.event.status, 'confirmed');
      await db.query(`update public.events set registration_needs='Changed requirements',
        registration_opens_at=now(),registration_closes_at=now()+interval '12 hours',
        waiting_list_enabled=true where event_id=$1`, [id]);
      assert.equal((await db.query('select status from public.events where event_id=$1', [id])).rows[0].status, 'confirmed');
    });

    await t.test('venue and equipment blockers remain active', async () => {
      const noVenue = await createEvent(); await actor(coordinator);
      const venueBlocked = (await db.query('select public.submit_event_for_safety_checks($1) result', [noVenue])).rows[0].result;
      assert.equal(venueBlocked.status, 409);
      assert.match(venueBlocked.blockers.join(' '), /approved venue booking/i);

      const noEquipment = await createEvent([{ equipment_type: 'Microphone', quantity: 3 }]);
      await book(noEquipment);
      const equipmentBlocked = (await db.query(
        'select public.submit_event_for_safety_checks($1) result', [noEquipment]
      )).rows[0].result;
      assert.equal(equipmentBlocked.status, 409);
      assert.match(equipmentBlocked.blockers.join(' '), /Reserve all required Microphone/);
    });

    await t.test('obsolete schema is removed and previously approved rows are promoted', async () => {
      assert.equal((await db.query('select status from public.events where event_id=99')).rows[0].status, 'confirmed');
      const columns = await db.query(`select 1 from information_schema.columns
        where table_schema='public' and table_name='events' and column_name='registration_ready'`);
      assert.equal(columns.rows.length, 0);
      assert.equal((await db.query(
        "select to_regprocedure('public.set_event_registration_ready(integer,boolean)') name"
      )).rows[0].name, null);
    });
  } finally { await db.close(); }
});
