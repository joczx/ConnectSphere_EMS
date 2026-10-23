"""Static checks on the auto-assignment migration; no database needed."""
from pathlib import Path


SQL = (Path(__file__).parents[2] / 'supabase/043_auto_assign_event_staff.sql').read_text()


def test_assignment_runs_as_the_approved_event_is_created():
    assert 'before insert on public.events' in SQL
    # Only events created by approving a request, not any events row.
    assert 'if new.event_request_id is null then' in SQL


def test_each_staff_role_is_assigned_without_overwriting_a_chosen_one():
    for column, roles in (
        ('venue_staff_id', "array['venue_staff']"),
        ('technical_support_id', "array['technical_support_staff', 'technical_support']"),
        ('safety_officer_id', "array['safety_officer']"),
    ):
        assert f'new.{column} := coalesce(\n        new.{column},\n        public.random_user_with_role({roles}));' in SQL


def test_safety_officer_column_is_added_once_and_references_users():
    assert 'add column if not exists safety_officer_id uuid references public.users(user_id)' in SQL


def test_choice_is_random_and_compares_role_names_like_has_booking_role():
    assert 'order by random()' in SQL
    assert "replace(lower(btrim(r.role_name)), ' ', '_') = any(p_roles)" in SQL
    # volatile, so each row gets its own draw rather than a cached one.
    assert 'language sql volatile security definer' in SQL


def test_helpers_are_not_callable_from_the_api_and_the_trigger_can_be_rerun():
    assert 'revoke all on function public.random_user_with_role(text[]) from public, anon, authenticated;' in SQL
    assert 'revoke all on function public.auto_assign_event_staff() from public, anon, authenticated;' in SQL
    assert 'drop trigger if exists auto_assign_event_staff on public.events;' in SQL



BOOKINGS_SQL = (Path(__file__).parents[2] / 'supabase/045_event_venue_bookings_for_assigned_staff.sql').read_text()


def test_event_bookings_are_read_only_for_everyone_the_event_names():
    for column in ('event_organiser_id', 'event_coordinator_id', 'technical_support_id', 'venue_staff_id', 'safety_officer_id'):
        assert f'auth.uid() is distinct from planned.{column}' in BOOKINGS_SQL
    assert 'where b.event_id = p_event_id' in BOOKINGS_SQL
    for word in ('insert into', 'update public.', 'delete from'):
        assert word not in BOOKINGS_SQL
    assert 'revoke all on function public.event_venue_bookings(integer) from public, anon;' in BOOKINGS_SQL
