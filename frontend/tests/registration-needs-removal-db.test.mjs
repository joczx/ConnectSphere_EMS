import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PGlite } from '../node_modules/.event-status-qa/node_modules/@electric-sql/pglite/dist/index.js';

test('removing registration needs preserves approved request creation and registration settings', async () => {
  const db = new PGlite();
  try {
    await db.exec(`
      create schema auth;
      create function auth.uid() returns uuid language sql stable as $$ select null::uuid; $$;
      create type public.event_status as enum ('planning','pending_safety_checks','confirmed','completed','cancelled');
      create type public.facility as enum ('wifi');
      create table public.events (
        event_id serial primary key, event_request_id integer unique, event_name text, purpose text, description text,
        start_datetime timestamptz, end_datetime timestamptz, capacity_needed integer, room_layout text,
        required_facilities public.facility[], need_wheelchair_accessibility boolean, need_blind_accessibility boolean,
        equipment_requirements jsonb, registration_needs text, status public.event_status default 'planning',
        event_organiser_id uuid, event_coordinator_id uuid, registration_opens_at timestamptz, registration_closes_at timestamptz,
        waiting_list_enabled boolean default false, safety_rework_required boolean default false,
        safety_rework_requested_at timestamptz, safety_rework_arrangements text[], safety_approved_at timestamptz,
        updated_at timestamptz default now()
      );
      create table public.event_request (
        event_request_id integer primary key, event_name text, purpose text, description text,
        start_datetime timestamptz, end_datetime timestamptz, capacity_needed integer, room_layout text,
        required_facilities public.facility[], need_wheelchair_accessibility boolean, need_blind_accessibility boolean,
        equipment_requirements jsonb, registration_needs text, status text, event_organiser_id uuid, event_coordinator_id uuid
      );
      create function public.event_confirmation_blockers(public.events) returns text[] language sql as $$ select '{}'::text[]; $$;
      create function public.event_safety_check_blockers(public.events) returns text[] language sql as $$ select '{}'::text[]; $$;
      create table public.operational_safety_decision(event_id integer, safety_officer_id uuid, outcome text, created_at timestamptz);
      insert into public.events(event_id,event_name,registration_needs,status,safety_approved_at)
        values (100,'Existing event','Obsolete arrangements','confirmed',now());
      insert into public.event_request(event_request_id,event_name,description,status,equipment_requirements)
        values (1,'New event','Event description','submitted','[]');
    `);
    const migration = await readFile(new URL('../../supabase/055_remove_registration_needs.sql', import.meta.url), 'utf8');
    await db.exec(migration);
    await db.exec(migration);
    assert.equal((await db.query(`select 1 from information_schema.columns where table_schema='public'
      and table_name in ('event_request','events') and column_name='registration_needs'`)).rows.length, 0);
    await db.exec(`
      create trigger guard_event_lifecycle before insert or update on public.events
        for each row execute function public.guard_event_lifecycle();
      create trigger create_event_after_request_approval after update of status on public.event_request
        for each row when (new.status='planning' and old.status is distinct from 'planning')
        execute function public.create_event_from_approved_request();
      update public.event_request set status='planning' where event_request_id=1;
    `);
    const created = (await db.query('select * from public.events where event_request_id=1')).rows[0];
    assert.equal(created.event_name, 'New event');
    assert.equal(created.description, 'Event description');
    assert.equal(created.status, 'planning');
    assert.deepEqual(created.equipment_requirements, []);
    assert.equal(created.registration_needs, undefined);
    await db.exec(`update public.events set registration_opens_at=now(), registration_closes_at=now()+interval '1 day',
      waiting_list_enabled=true where event_id=100`);
    const existing = (await db.query('select * from public.events where event_id=100')).rows[0];
    assert.equal(existing.status, 'confirmed');
    assert.ok(existing.safety_approved_at);
    assert.equal(existing.waiting_list_enabled, true);
  } finally { await db.close(); }
});
