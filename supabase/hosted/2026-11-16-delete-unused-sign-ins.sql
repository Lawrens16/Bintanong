-- Hosted project only (owner, 16 Nov 2026; personal fork). Applied once with the Supabase MCP, not a migration:
-- the storage tests apply every file in supabase/migrations to a fresh database that has no auth schema and
-- cannot host pg_cron. Re-running is safe (the job is replaced by name).
--
-- Sign-in records are temporary. A Google sign-in creates a record in auth.users with the student's name, school
-- email and profile photo link. This job deletes a record once it has not been used for 7 days: no sign-in and no
-- session refreshed in that time. Daily question counts never use this record (they key on an anonymous account
-- number in server memory for 24 hours), so deleting it cannot reset anyone's limit.
-- Deleting a user removes its identities and sessions too (Supabase's own foreign keys); no app table refers to it.

create extension if not exists pg_cron with schema pg_catalog;
grant usage on schema cron to postgres;
grant all privileges on all tables in schema cron to postgres;

select cron.schedule(
  'delete-unused-sign-ins',
  '17 19 * * *',  -- daily at 19:17 UTC (03:17 Philippine time)
  $job$
  delete from auth.users u
  where coalesce(u.last_sign_in_at, u.created_at) < now() - interval '7 days'
    and not exists (
      select 1 from auth.sessions s
      where s.user_id = u.id
        and coalesce(s.refreshed_at, s.updated_at, s.created_at) > now() - interval '7 days');
  $job$
);
