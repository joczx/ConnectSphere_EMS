# Coordinator Lead dashboard

The authenticated `/reassign-event-coordinators` page groups submitted requests
and operational events into Submitted, Planning, Pending Safety Checks, and
Confirmed columns. Draft, rejected, completed, and cancelled records are not
returned. Leads can reassign either a submitted request or an operational event;
the assigned coordinator receives a notification.

The dashboard and reassignment operations use role-checked Supabase functions.
They do not widen event or request row-level security policies. Coordinators
continue to read and update events only through their existing assigned-event
policies. A Lead may reassign a confirmed event; ordinary event edits remain
subject to the existing confirmed-event restrictions.

Apply [030_coordinator_lead_dashboard.sql](../supabase/030_coordinator_lead_dashboard.sql)
after migration 029, then reload the Supabase API schema cache if the new RPCs
are not immediately visible. The migration adds `pending_safety_checks` to the
shared event status enum; existing rows are not moved into that status
automatically.
