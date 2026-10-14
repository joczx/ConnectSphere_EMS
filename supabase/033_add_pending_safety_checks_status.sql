-- Apply this migration on its own, before 034_operational_safety_reviews.sql.
-- PostgreSQL requires a committed enum value before a later migration can use
-- it in functions, triggers, or constraints.
alter type public.event_status add value if not exists 'pending_safety_checks';
