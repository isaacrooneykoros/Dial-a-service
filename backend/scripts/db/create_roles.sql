-- Database roles for Dial A Service (ADR-0001 section 5).
--
-- Run through scripts/db/setup_roles.py, never by hand: the script sets the
-- passwords as transaction settings (dial.*_password) so they never appear in
-- this file, in shell history or in logs.
--
-- Idempotent: safe to run again. Each block is run separately so one failure
-- (for example Neon refusing BYPASSRLS) doesn't hide the others.
--
--   dial_owner     owns the schema; migrations and test-database setup only.
--                  On Neon it is created in the Console; elsewhere by this file.
--   dial_app       API and worker. NOBYPASSRLS: every query is subject to the
--                  tenant policies. Always created here by SQL, so on Neon it is
--                  NOT a member of neon_superuser (which has BYPASSRLS).
--   dial_platform  platform-admin service and cross-tenant platform jobs only.

-- @block owner
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dial_owner') THEN
    EXECUTE format(
      'CREATE ROLE dial_owner LOGIN CREATEDB NOSUPERUSER NOBYPASSRLS PASSWORD %L',
      current_setting('dial.owner_password')
    );
  END IF;
END
$$;

-- @block app
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dial_app') THEN
    EXECUTE format(
      'CREATE ROLE dial_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
      current_setting('dial.app_password')
    );
  ELSE
    EXECUTE format(
      'ALTER ROLE dial_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
      current_setting('dial.app_password')
    );
  END IF;
END
$$;

-- @block platform
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dial_platform') THEN
    EXECUTE format(
      'CREATE ROLE dial_platform LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS PASSWORD %L',
      current_setting('dial.platform_password')
    );
  ELSE
    EXECUTE format(
      'ALTER ROLE dial_platform LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS PASSWORD %L',
      current_setting('dial.platform_password')
    );
  END IF;
END
$$;
