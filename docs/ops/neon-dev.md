# Development database on Neon

How to set up the Neon Postgres database used for local development (owner decision D-21). Background: ADR-0001 §5.

Neon's screens change from time to time; if a button has a slightly different name, look for the closest match.

## One-time setup

1. **Create the project.** Sign up at <https://console.neon.tech> and create a project:
   - name `dial-a-service`;
   - Postgres version **16**;
   - region **AWS Europe Central 1 (Frankfurt)**.
2. **Create the owner role and database** on the `main` branch, under **Roles & Databases** (or **Roles** and **Databases**):
   - add a role named **`dial_owner`**;
   - add a database named **`dialaservice`** with owner **`dial_owner`**.
3. **Create your development branch.** Under **Branches**, create a branch named **`dev`** from `main`. It gets a copy of the role and database.
4. **Copy the direct connection string.** Click **Connect** and choose:
   - branch **`dev`**;
   - database **`dialaservice`**;
   - role **`dial_owner`**;
   - **connection pooling OFF** (this gives the *direct* host, without `-pooler` in the name).

   Copy the connection string.
5. **Put it in your `.env`.** Open `backend\.env` and set `DATABASE_MIGRATION_URL=` to it. It looks like this:

   ```text
   DATABASE_MIGRATION_URL=postgresql://dial_owner:xxxx@ep-something-123456.eu-central-1.aws.neon.tech/dialaservice?sslmode=require
   ```

   Never paste it anywhere else, including chat.
6. **Create the app roles.** From `backend\`, with the virtualenv active:

   ```powershell
   python -m scripts.db.setup_roles
   ```

   This creates **`dial_app`** and **`dial_platform`** with SQL and applies the grants. It then checks that `dial_app` can't bypass row-level security, and writes `DATABASE_URL` (dial_app, pooled host) and `PLATFORM_DATABASE_URL` into `backend\.env`. Passwords are generated and never shown. Every line of its output should say `[OK  ]`.

   > **Don't create `dial_app` or `dial_platform` in the Neon Console.** Console roles are automatically members of `neon_superuser`, which can bypass row-level security. The script's checks would catch it and fail.

7. **Run the migrations** (as `dial_owner`):

   ```powershell
   .\scripts\migrate.ps1
   ```

## Checking the roles later

```powershell
python -m scripts.db.setup_roles --verify-only
```

## Resetting the dev database

In the Neon Console, **Branches** → `dev` → **Reset from parent**. It returns to a copy of `main`, where the roles exist but have no app passwords. Then run steps 6 and 7 again.

## Tests

`pytest` creates a separate `test_dialaservice` database on the same branch as `dial_owner`, migrates it, and runs the tests as `dial_app`. Tests from Kenya to Frankfurt are slower than CI; use `pytest --reuse-db` to skip rebuilding the test database between runs.

## Optional: local Postgres instead of Neon

If you ever want to work offline, `docker-compose.yml` in the repository root starts Postgres 16 locally:

```powershell
docker compose up -d db
python -m scripts.db.setup_roles --admin-url postgres://postgres:postgres@localhost:5432/postgres --create-database dialaservice
```

Then set `DATABASE_MIGRATION_URL=postgres://dial_owner:<DIAL_OWNER_PASSWORD>@localhost:5432/dialaservice` (set `DIAL_OWNER_PASSWORD` in your shell before running the script).
