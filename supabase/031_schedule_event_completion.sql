-- Apply after 030. Supabase supports pg_cron; enable it in Database > Extensions
-- if this deployment does not allow CREATE EXTENSION from the SQL Editor.
create extension if not exists pg_cron;
select cron.schedule('connectsphere-event-completion', '* * * * *',
    $$update public.events set status = 'completed'
      where status = 'confirmed' and end_datetime <= now();$$);
