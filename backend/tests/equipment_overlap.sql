-- Run as postgres in a test Supabase database after migration 005.
-- Rolls back fixtures. These assertions exercise the actual SQL peak calculation.
begin;
do $$
declare item uuid := gen_random_uuid(); actor uuid := gen_random_uuid();
begin
    insert into auth.users(id) values (actor);
    insert into public.equipment(equipment_id, name, total_quantity) values (item, 'Overlap test ' || item, 10);
    insert into public.equipment_reservations(event_id, equipment_id, quantity, starts_at, ends_at, created_by) values
        ('test-a', item, 4, '2030-01-01 09:00Z', '2030-01-01 10:00Z', actor),
        ('test-b', item, 6, '2030-01-01 10:00Z', '2030-01-01 11:00Z', actor);
    assert public.equipment_peak(item, '2030-01-01 09:00Z', '2030-01-01 11:00Z') = 6, 'Back-to-back reservations must not be summed';
    assert public.equipment_peak(item, '2030-01-01 11:00Z', '2030-01-01 12:00Z') = 0, 'Adjacent event must have full stock';
    assert public.equipment_peak(item, '2030-01-02 09:00Z', '2030-01-02 10:00Z') = 0, 'Non-overlapping day must have full stock';
    assert public.equipment_peak(item, '2030-01-01 09:15Z', '2030-01-01 09:45Z') = 4, 'Containing reservation must count';
    insert into public.equipment_reservations(event_id, equipment_id, quantity, starts_at, ends_at, created_by)
    values ('test-c', item, 3, '2030-01-01 09:30Z', '2030-01-01 10:30Z', actor);
    assert public.equipment_peak(item, '2030-01-01 09:00Z', '2030-01-01 11:00Z') = 9, 'Concurrent quantities must add';
end;
$$;
rollback;
