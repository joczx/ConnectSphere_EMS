from pathlib import Path


SQL = (Path(__file__).parents[2] / 'supabase/030_event_status_automation.sql').read_text()


def test_status_migration_repairs_integer_event_id_guard_before_updating_events():
    repair = SQL.index('create or replace function public.guard_equipment_event()')
    existing_rows = SQL.index('update public.events set updated_at = clock_timestamp()')
    assert repair < existing_rows
    assert 'where event_id = old.event_id' in SQL


def test_status_automation_uses_integer_event_ids_without_text_casts():
    assert 'where r.event_id = p_event.event_id' in SQL
    assert 'declare previous_id integer; next_id integer;' in SQL
    assert 'event_id::text' not in SQL


def test_every_created_trigger_can_be_replaced_on_rerun():
    trigger_names = [
        line.split()[2]
        for line in SQL.splitlines()
        if line.startswith('create trigger ')
    ]
    for name in trigger_names:
        assert f'drop trigger if exists {name} on public.' in SQL
