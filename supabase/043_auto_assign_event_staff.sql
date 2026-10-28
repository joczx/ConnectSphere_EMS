-- ConnectSphere EMS: Assign event staff automatically on approval
-- Run this file in the Supabase SQL Editor after 042.
--
-- When the assigned Event Coordinator approves an event request, the request
-- moves to 'planning' and create_event_after_request_approval inserts the
-- events row. This migration fills that new row's Venue Staff, Technical
-- Support Staff and Safety Officer with a randomly chosen user holding each
-- role.
--
-- WHY A TRIGGER ON events, NOT ON THE REVIEW
-- The approval creates the event inside the database, so assigning in the
-- same insert means an approved event is never seen without its staff, and
-- no client can approve a request while skipping the assignment. Only events
-- created from a request (event_request_id is set) are assigned.
--
-- WHAT IT DOES NOT DO
--   * Existing events are left as they are; nothing is backfilled.
--   * A role with no users leaves that field empty rather than failing the
--     approval, so an approval never breaks because a role is unstaffed.
--   * A value already set on the new row is kept.
--
-- TO REVERT
--     drop trigger if exists auto_assign_event_staff on public.events;
--     drop function if exists public.auto_assign_event_staff();
--     drop function if exists public.random_user_with_role(text[]);
--     alter table public.events drop column if exists safety_officer_id;

begin;

-- 1. The Safety Officer assigned to the event, alongside the existing
--    technical_support_id and venue_staff_id.
alter table public.events
    add column if not exists safety_officer_id uuid references public.users(user_id);

comment on column public.events.safety_officer_id is
    'The Safety Officer assigned to the event, chosen at random on approval.';

-- 2. One random user holding any of the given roles, or null when none does.
--    Role names are compared the same way as has_booking_role():
--    lower case, trimmed, spaces as underscores.
create or replace function public.random_user_with_role(p_roles text[])
returns uuid
language sql volatile security definer set search_path = public as $$
    select ur.user_id
    from public.user_roles ur
    join public.roles r using (role_id)
    where replace(lower(btrim(r.role_name)), ' ', '_') = any(p_roles)
    order by random()
    limit 1;
$$;

revoke all on function public.random_user_with_role(text[]) from public, anon, authenticated;

-- 3. Fill in whoever is still missing on an event created from a request.
create or replace function public.auto_assign_event_staff()
returns trigger
language plpgsql security definer set search_path = public as $$
begin
    if new.event_request_id is null then
        return new;
    end if;
    new.venue_staff_id := coalesce(
        new.venue_staff_id,
        public.random_user_with_role(array['venue_staff']));
    new.technical_support_id := coalesce(
        new.technical_support_id,
        public.random_user_with_role(array['technical_support_staff', 'technical_support']));
    new.safety_officer_id := coalesce(
        new.safety_officer_id,
        public.random_user_with_role(array['safety_officer']));
    return new;
end;
$$;

revoke all on function public.auto_assign_event_staff() from public, anon, authenticated;

drop trigger if exists auto_assign_event_staff on public.events;
create trigger auto_assign_event_staff
    before insert on public.events
    for each row execute function public.auto_assign_event_staff();

notify pgrst, 'reload schema';

commit;
