// Run with: node --test frontend/tests/event-status-db.mjs
// Temporary QA dependency: npm install --prefix frontend/node_modules/.event-status-qa
// @electric-sql/pglite --no-save --package-lock=false
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PGlite } from '../node_modules/.event-status-qa/node_modules/@electric-sql/pglite/dist/index.js';

const coordinator = '00000000-0000-0000-0000-000000000001';
const organiser = '00000000-0000-0000-0000-000000000002';
const outsider = '00000000-0000-0000-0000-000000000003';
const venue = '00000000-0000-0000-0000-000000000004';

test('PostgreSQL lifecycle migrations enforce and automatically advance event stages', async t => {
  const db = new PGlite();
  try {
    // Minimal deployed-table fixture: rules under test are the actual migration,
    // not a JavaScript copy. Unrelated venue suitability is stubbed explicitly.
    await db.exec(`
      create role anon; create role authenticated;
      create schema auth;
      create function auth.uid() returns uuid language sql stable as $$
        select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
      $$;
      create type public.event_status as enum ('draft','submitted','planning','rejected','confirmed','completed','cancelled');
      create table public.event_request (
        event_request_id serial primary key, event_name text, purpose text,
        capacity_needed integer, start_datetime timestamptz, end_datetime timestamptz,
        status public.event_status default 'draft', event_organiser_id uuid,
        event_coordinator_id uuid, updated_at timestamptz default now()
      );
      create table public.events (
        event_id serial primary key, event_request_id integer unique,
        event_name text, purpose text, capacity_needed integer,
        start_datetime timestamptz, end_datetime timestamptz,
        status public.event_status default 'planning',
        event_organiser_id uuid, event_coordinator_id uuid,
        technical_support_id uuid, venue_staff_id uuid,
        equipment_requirements jsonb, registration_needs text,
        updated_at timestamptz default now()
      );
      create table public.event_request_review (
        event_request_id integer, reviewer_id uuid, outcome text, created_at timestamptz default now()
      );
      create table public.venues (venue_id uuid primary key, deleted_at timestamptz, suitable boolean default true);
      create table public.venue_booking_requests (
        booking_id serial primary key, event_id integer, venue_id uuid,
        status text, starts_at timestamptz, ends_at timestamptz, attendance integer
      );
      create table public.equipment (equipment_id serial primary key, equipment_type text);
      create table public.equipment_request (equipment_request_id serial primary key, event_id integer, quantity integer);
      create table public.equipment_reservations (
        reservation_id serial primary key, event_id text, equipment_id integer,
        quantity integer, starts_at timestamptz, ends_at timestamptz, equipment_request_id integer
      );
      create table public.event_activity (
        activity_id serial primary key, event_id integer, changed_by uuid,
        change_type text check (change_type in ('edit','critical_edit')), changes jsonb
      );
      create function public.venue_shortfalls_for_event(public.venues, public.events)
        returns text[] language sql as $$ select case when $1.suitable then '{}'::text[] else array['Unsuitable'] end; $$;
      create function public.create_event_from_approved_request() returns trigger language plpgsql as $$
      begin
        insert into public.events (event_request_id, event_name, purpose, capacity_needed,
          start_datetime, end_datetime, event_organiser_id, event_coordinator_id)
        values (new.event_request_id, new.event_name, new.purpose, new.capacity_needed,
          new.start_datetime, new.end_datetime, new.event_organiser_id, new.event_coordinator_id)
        on conflict (event_request_id) do nothing;
        return new;
      end; $$;
    `);

    await db.exec(await readFile(new URL('../../supabase/030_event_status_automation.sql', import.meta.url), 'utf8'));
    await db.query('select set_config($1, $2, false)', ['request.jwt.claim.sub', coordinator]);
    await db.query('insert into venues(venue_id) values ($1)', [venue]);
    await db.exec("insert into equipment(equipment_type) values ('Microphone'), ('microphone')");

    const status = async id => (await db.query('select status from events where event_id=$1', [id])).rows[0].status;
    const createEvent = async (equipment = [], registration = null, past = false) => (
      await db.query(`insert into events(event_name, capacity_needed, event_coordinator_id, event_organiser_id,
        start_datetime, end_datetime, equipment_requirements, registration_needs)
        values ('Test', 10, $1, $2, now() + $5::interval, now() + $6::interval, $3::jsonb, $4) returning event_id`,
      [coordinator, organiser, JSON.stringify(equipment), registration,
        past ? '-2 hours' : '1 day', past ? '-1 hour' : '2 days'])
    ).rows[0].event_id;
    const book = id => db.query(`insert into venue_booking_requests(event_id, venue_id, status, starts_at, ends_at, attendance)
      select event_id, $2, 'approved', start_datetime, end_datetime, capacity_needed from events where event_id=$1`, [id, venue]);
    const reserve = (id, qty, model = 1, requestId = null) => db.query(`insert into equipment_reservations
      (event_id, equipment_id, quantity, starts_at, ends_at, equipment_request_id)
      select event_id::text, $2, $3, start_datetime, end_datetime, $4 from events where event_id=$1`, [id, model, qty, requestId]);

    await t.test('only the seven requested statuses exist', async () => {
      const values = (await db.query("select unnest(enum_range(null::event_status))::text as status")).rows.map(r => r.status);
      assert.deepEqual(values.sort(), ['draft','submitted','planning','confirmed','completed','cancelled','rejected'].sort());
    });
    await t.test('draft submission and approval require valid conditions and assigned reviewer', async () => {
      const id = (await db.query(`insert into event_request(event_coordinator_id,event_organiser_id) values ($1,$2) returning event_request_id`, [coordinator, organiser])).rows[0].event_request_id;
      await assert.rejects(db.query("update event_request set status='submitted' where event_request_id=$1", [id]), /complete_before_submit/);
      await db.query(`update event_request set event_name='Test', purpose='Test',capacity_needed=10,
        start_datetime=now()+interval '1 day',end_datetime=now()+interval '2 days',status='submitted' where event_request_id=$1`, [id]);
      await assert.rejects(db.query("update event_request set status='planning' where event_request_id=$1", [id]), /matching coordinator review/);
      await db.query("insert into event_request_review(event_request_id, reviewer_id, outcome) values ($1,$2,'approved')", [id, coordinator]);
      await db.query('select set_config($1,$2,false)', ['request.jwt.claim.sub', organiser]);
      await assert.rejects(db.query("update event_request set status='planning' where event_request_id=$1", [id]), /assigned coordinator/);
      await db.query('select set_config($1,$2,false)', ['request.jwt.claim.sub', coordinator]);
      await db.query("update event_request set status='planning' where event_request_id=$1", [id]);
      assert.equal((await db.query('select status from event_request where event_request_id=$1', [id])).rows[0].status, 'planning');
      assert.equal((await db.query('select status from events where event_request_id=$1', [id])).rows[0].status, 'planning');
      await assert.rejects(db.query("update event_request set status='submitted' where event_request_id=$1", [id]), /Invalid request/);
    });
    await t.test('venue, full equipment quantity and coordinator registration acknowledgement are all required', async () => {
      const id = await createEvent([{ equipment_type: 'microphone', quantity: 3 }], 'Attendee sign-up');
      await assert.rejects(db.query("update events set status='confirmed' where event_id=$1", [id]), /approved venue/);
      await book(id); assert.equal(await status(id), 'planning');
      await reserve(id, 1); assert.equal(await status(id), 'planning');
      await reserve(id, 2, 2); assert.equal(await status(id), 'planning');
      await db.query('select set_config($1,$2,false)', ['request.jwt.claim.sub', organiser]);
      assert.equal((await db.query('select set_event_registration_ready($1,true) as result', [id])).rows[0].result.status, 403);
      await assert.rejects(db.query('update events set registration_ready=true where event_id=$1', [id]), /assigned coordinator/);
      await db.query('select set_config($1,$2,false)', ['request.jwt.claim.sub', coordinator]);
      assert.equal((await db.query('select set_event_registration_ready($1,true) as result', [id])).rows[0].result.event.status, 'confirmed');
      assert.equal(await status(id), 'confirmed');
      await assert.rejects(db.query("update events set status='completed' where event_id=$1", [id]), /end time/);
      await db.query('delete from equipment_reservations where event_id=$1 and equipment_id=2', [String(id)]);
      assert.equal(await status(id), 'planning');
      await reserve(id, 2, 2); assert.equal(await status(id), 'confirmed');
      const changes = (await db.query("select changes->'status'->>'to' as status from event_activity where event_id=$1 order by activity_id", [id])).rows.map(r => r.status);
      assert.deepEqual(changes, ['confirmed', 'planning', 'confirmed']);
    });
    await t.test('unknown equipment requirements, malformed requirements and stale bookings block confirmation', async () => {
      const id = await createEvent(null);
      await book(id); assert.equal(await status(id), 'planning');
      await db.query("update events set equipment_requirements='[{\"equipment_type\":\"microphone\"}]' where event_id=$1", [id]);
      assert.equal(await status(id), 'planning');
      await db.query("update venue_booking_requests set ends_at=ends_at-interval '1 hour' where event_id=$1", [id]);
      await db.query("update events set equipment_requirements='[]' where event_id=$1", [id]);
      assert.equal(await status(id), 'planning');
    });
    await t.test('outstanding additional requests and partial reservations cannot be counted as fulfilled', async () => {
      const id = await createEvent([]);
      const requestId = (await db.query('insert into equipment_request(event_id,quantity) values ($1,2) returning equipment_request_id', [id])).rows[0].equipment_request_id;
      await book(id); assert.equal(await status(id), 'planning');
      await reserve(id, 1, 1, requestId); assert.equal(await status(id), 'planning');
      await db.query('update equipment_reservations set quantity=2 where equipment_request_id=$1', [requestId]);
      assert.equal(await status(id), 'confirmed');
    });
    await t.test('completion occurs only after the end and only for authorised visible events', async () => {
      const id = await createEvent([], null, true);
      await book(id); assert.equal(await status(id), 'confirmed');
      await db.query('select set_config($1,$2,false)', ['request.jwt.claim.sub', outsider]);
      await db.exec('select refresh_visible_event_statuses()');
      assert.equal(await status(id), 'confirmed');
      await db.query('select set_config($1,$2,false)', ['request.jwt.claim.sub', organiser]);
      await db.exec('select refresh_visible_event_statuses()'); assert.equal(await status(id), 'completed');
      await assert.rejects(db.query("update events set status='planning' where event_id=$1", [id]), /cannot be changed/);
      await db.query('select set_config($1,$2,false)', ['request.jwt.claim.sub', coordinator]);
    });
    await t.test('cancellation is authorised, terminal, and permits incomplete drafts', async () => {
      const id = await createEvent([]);
      await db.query('select set_config($1,$2,false)', ['request.jwt.claim.sub', outsider]);
      assert.equal((await db.query('select cancel_planned_event($1) as result', [id])).rows[0].result.status, 404);
      await db.query('select set_config($1,$2,false)', ['request.jwt.claim.sub', organiser]);
      assert.equal((await db.query('select cancel_planned_event($1) as result', [id])).rows[0].result.event.status, 'cancelled');
      await book(id); assert.equal(await status(id), 'cancelled');
      await assert.rejects(db.query("update events set status='planning' where event_id=$1", [id]), /cannot be changed/);
      const requestId = (await db.query('insert into event_request(event_organiser_id) values ($1) returning event_request_id', [organiser])).rows[0].event_request_id;
      assert.equal((await db.query('select cancel_event_request($1) as result', [requestId])).rows[0].result.event_request.status, 'cancelled');
      await db.query('select set_config($1,$2,false)', ['request.jwt.claim.sub', coordinator]);
    });
    await t.test('venue changes invalidate confirmation without reopening terminal events', async () => {
      const id = await createEvent([]); await book(id); assert.equal(await status(id), 'confirmed');
      await db.query('update venues set suitable=false where venue_id=$1', [venue]);
      assert.equal(await status(id), 'planning');
      await db.query('update venues set suitable=true where venue_id=$1', [venue]);
      assert.equal(await status(id), 'confirmed');
    });
    await t.test('rejection can be resubmitted but skips and repeated decisions are refused', async () => {
      const id = (await db.query(`insert into event_request(event_name,purpose,capacity_needed,status,
        start_datetime,end_datetime,event_organiser_id,event_coordinator_id)
        values ('Test','Test',10,'submitted',now()+interval '1 day',now()+interval '2 days',$1,$2)
        returning event_request_id`, [organiser, coordinator])).rows[0].event_request_id;
      await db.query("insert into event_request_review(event_request_id,reviewer_id,outcome) values ($1,$2,'rejected')", [id, coordinator]);
      await db.query("update event_request set status='rejected',updated_at=clock_timestamp() where event_request_id=$1", [id]);
      await assert.rejects(db.query("update event_request set status='planning' where event_request_id=$1", [id]), /Invalid request/);
      await db.query("update event_request set status='submitted',updated_at=clock_timestamp() where event_request_id=$1", [id]);
      await assert.rejects(db.query("update event_request set status='rejected' where event_request_id=$1", [id]), /matching coordinator review/);
      const eventId = await createEvent([]);
      await assert.rejects(db.query("update events set status='completed' where event_id=$1", [eventId]), /Invalid event/);
      await db.query("update events set registration_ready=true where event_id=$1", [eventId]);
      await db.query("update events set registration_needs='Changed requirements' where event_id=$1", [eventId]);
      assert.equal((await db.query('select registration_ready from events where event_id=$1', [eventId])).rows[0].registration_ready, false);
    });
    await t.test('direct equipment reservations require both Technical Support role and event assignment', async () => {
      await db.exec(`
        create table public.roles (role_id serial primary key, role_name text);
        create table public.user_roles (user_id uuid, role_id integer);
        alter table public.equipment add column equipment_model text default 'Test';
        alter table public.equipment add column total_quantity integer default 10;
        alter table public.equipment_reservations add column created_by uuid;
        create function public.equipment_peak(integer,timestamptz,timestamptz)
          returns bigint language sql as $$ select 0::bigint; $$;
        insert into roles(role_name) values ('Technical Support Staff');
      `);
      await db.exec(await readFile(new URL('../../supabase/022_reserve_available_equipment.sql', import.meta.url), 'utf8'));
      await db.exec(await readFile(new URL('../../supabase/032_technical_support_reservations.sql', import.meta.url), 'utf8'));
      const id = await createEvent([]);
      await db.query('update events set technical_support_id=$2 where event_id=$1', [id, organiser]);
      await db.query('select set_config($1,$2,false)', ['request.jwt.claim.sub', organiser]);
      const attempt = () => db.query('select reserve_equipment($1,1,2) as result', [String(id)]);
      assert.equal((await attempt()).rows[0].result.status, 403, 'assignment alone must not grant permission');
      assert.equal((await db.exec('select reservable_equipment_events() as result'))[0].rows[0].result.status, 403);
      await db.query('insert into user_roles(user_id,role_id) values ($1,1)', [organiser]);
      await db.query('update events set technical_support_id=$2 where event_id=$1', [id, coordinator]);
      assert.equal((await attempt()).rows[0].result.status, 403, 'role alone must not grant permission');
      await db.query('update events set technical_support_id=$2 where event_id=$1', [id, organiser]);
      const saved = (await attempt()).rows[0].result;
      assert.equal(saved.reservation.event_id, String(id));
      assert.equal(saved.reservation.quantity, 2);
      const visible = (await db.query('select reservable_equipment_events() as result')).rows[0].result;
      assert.deepEqual(visible.map(e => e.event_id), [String(id)]);
      assert.equal((await db.query("select has_function_privilege('authenticated', 'public.reserve_equipment_assigned(text,integer,integer)', 'EXECUTE') as allowed")).rows[0].allowed, false);
    });
  } finally { await db.close(); }
});
