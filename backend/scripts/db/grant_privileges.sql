-- Privileges inside one database (ADR-0001 section 5).
--
-- Default privileges are stored per database, so this runs in every database
-- the app uses: the dev/staging/production database (setup_roles.py) and each
-- test database (conftest.py). Run as dial_owner or a superuser. Idempotent.
--
-- dial_app and dial_platform can read and write rows but can never create,
-- alter or drop anything. Append-only tables later REVOKE UPDATE, DELETE
-- through the MakeAppendOnly migration operation.

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO dial_app, dial_platform;

ALTER DEFAULT PRIVILEGES FOR ROLE dial_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dial_app, dial_platform;
ALTER DEFAULT PRIVILEGES FOR ROLE dial_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO dial_app, dial_platform;

-- Tables that already exist (re-runs after migrations).
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO dial_app, dial_platform;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO dial_app, dial_platform;
