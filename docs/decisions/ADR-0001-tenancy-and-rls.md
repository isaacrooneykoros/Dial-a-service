# ADR-0001: Tenancy and row-level security

- **Status:** Accepted (owner, 2026-10-01)
- **Date:** 2026-10-01
- **Sources:** design doc "Tenancy and isolation", `CLAUDE.md` §6.1 and §6.6, `docs/UNDERSTANDING.md` §4 items 4, 5, 17, 19–24

## Context

Many laundries share one Postgres database. One business must never see another's data, even when there's a bug in one layer. The design asks for three independent layers: application code, Postgres row-level security (RLS), and tests in CI. The development database is a Neon dev branch; CI uses a Postgres 16 service container.

## Decision

### 1. Resolving the business from the host

- `apps.tenancy.middleware.TenantResolutionMiddleware` reads `request.get_host()`, strips the port, lowercases it, and looks it up in `BusinessDomain.host`. The result (business ID, slug, status) is cached for 60 seconds under `tenancy:host:{host}`. Negative results are cached for 60 seconds too, so random hosts can't hammer the database.
- An unknown host returns **404 with the error envelope** before any view, authentication or session code runs.
- **Exempt paths:** `/api/v1/health` only (Render's health check doesn't use a business host). The exemption list is one setting, `TENANCY_EXEMPT_PATHS`, and a test asserts it contains nothing else.
- **Platform host:** `PLATFORM_ADMIN_HOST` (e.g. `admin.dialaservice.co.ke`) resolves to "no business". It is served only by the platform-admin service (see §6); the API service returns 404 for it.
- A business with status `suspended` or `cancelled` still resolves (so its owner can see a message). Status enforcement is M6.
- `X-Business` headers for mobile builds are out of scope (design doc says "later").

### 2. Carrying the context

- `apps/core/tenant_context.py` holds a `ContextVar[UUID | None]` named `current_business_id`, plus:
  - `get_current_business_id()`: returns the ID or raises `TenantContextMissing`;
  - `tenant_context(business_id)`: a context manager that sets the contextvar, opens `transaction.atomic()`, runs `SELECT set_config('app.business_id', %s, true)`, and restores everything on exit. Entering a *different* business while one is active raises `TenantContextConflict`. Entering the same one again is a no-op.
- `apps.tenancy.middleware.TenantTransactionMiddleware` wraps each business request in `tenant_context(request.business_id)`. So every business request runs in one transaction with a transaction-local setting, which is safe behind Neon's pooler. Session-level `SET` is never used; a test greps the codebase for it.
- `core` refers to the business only by the string `"tenancy.Business"` and holds no import from `apps.tenancy`. This settles the core/tenancy contradiction (UNDERSTANDING §4 item 4) without moving `TenantModel` out of core.

### 3. `TenantModel` and managers

```python
class TenantModel(BaseModel):          # BaseModel: UUID pk, created_at, updated_at
    business = models.ForeignKey("tenancy.Business", on_delete=models.PROTECT,
                                 db_index=True, editable=False, related_name="+")
    objects = TenantManager()          # raises TenantContextMissing without context; filters by business
    unscoped = models.Manager()        # platform code only, each use marked  # platform-scope: <reason>

    class Meta:
        abstract = True
```

- `TenantManager.get_queryset()` filters `business_id=get_current_business_id()`. This is layer 1: it fails loudly when there's no context, and it narrows results even before RLS does.
- `TenantModel.save()` fills `business_id` from the context when it's empty, and raises `TenantMismatch` if it's set to anything else. This is an integrity guard, not business logic, so it doesn't break §6.6.
- Serializers never expose `business` as writable (it's `editable=False`), and a test checks every serializer for this.
- Composite indexes and unique constraints start with `business`.
- Related-object access (`order.customer`) uses Django's base manager, which is not filtered; RLS covers that path.
- `tests/test_code_rules.py` fails if any line uses `.unscoped` without a `# platform-scope: <reason>` comment on the same line (ruff can't express this rule; as built in T04a).

**Nullable-tenant models.** Two models have rows that belong to no business: `accounts.User` (platform staff) and `core.AuditLog` (platform actions, P-12). They don't subclass `TenantModel`. They get a nullable `business` FK, the same RLS policy, and an entry in the registry's `NULLABLE_TENANT_MODELS` list. Under RLS, rows with a NULL business are invisible to `dial_app` (NULL never equals the setting) and visible only to `dial_platform`. `User` gets two partial unique constraints: `(business, phone) WHERE business IS NOT NULL` and `(phone) WHERE business IS NULL`.

### 4. The RLS migration operations

`apps/core/db.py` provides two reusable migration operations; no policy is ever hand-written:

- `EnableTenantRLS("modelname")`:
  ```sql
  ALTER TABLE t ENABLE ROW LEVEL SECURITY;
  ALTER TABLE t FORCE ROW LEVEL SECURITY;
  CREATE POLICY tenant_isolation ON t
    USING (business_id = NULLIF(current_setting('app.business_id', true), '')::uuid)
    WITH CHECK (business_id = NULLIF(current_setting('app.business_id', true), '')::uuid);
  ```
  It reverses cleanly (drop the policy, disable RLS). When no business is set, the policy matches nothing, so the query sees zero rows instead of all of them.

  **Why `NULLIF` (owner-approved 2026-10-01):** once a connection has used a transaction-local `app.business_id`, Postgres reports the unset value as `''` rather than NULL for the rest of that session. A plain `::uuid` cast would then raise on reused (pooled) connections but match nothing on fresh ones. `NULLIF(..., '')` makes it consistent: with no business, zero rows, always. Layer 1 still fails loudly before any such query is sent.
- `MakeAppendOnly("modelname")`: `REVOKE UPDATE, DELETE ON t FROM dial_app, dial_platform`. Used for `AuditLog` and `ConsentRecord` in M1, and later for `OrderStatusEvent`, `LedgerEntry` and `SmsTransaction`. This backs "never edit or delete" with the database, not just code.

### 5. Database roles

| Role | How it's created | Attributes | Used by |
| --- | --- | --- | --- |
| `dial_owner` | **Neon:** in the Neon Console (so it can create databases and roles). **CI/local Postgres:** by `create_roles.sql` as superuser | Owns the schema and all tables; `CREATEDB` (for test databases) | `scripts/migrate.ps1`, test-database setup |
| `dial_app` | **Always by SQL** (`create_roles.sql`, run as `dial_owner`) | `LOGIN NOBYPASSRLS NOSUPERUSER`, **not** a member of `neon_superuser` | API service and Celery worker |
| `dial_platform` | By SQL, run as `dial_owner` | `LOGIN BYPASSRLS` | Platform-admin service and cross-tenant platform jobs (M6) |

- **Why `dial_app` must be created by SQL on Neon:** Neon makes every Console-created role a member of `neon_superuser`, which has `BYPASSRLS`. A member could `SET ROLE neon_superuser` and step around every policy. SQL-created roles get no such membership ([Neon docs: roles](https://neon.com/docs/manage/roles)). T02 includes a test that fails if `dial_app` has `rolbypassrls`, or can become any role that has it.
- **Verified in T02a (2026-10-01, Neon project `dial-a-service`, branch `dev`, Postgres 16):** the Console-created `dial_owner` created `dial_platform WITH BYPASSRLS` by SQL, so no fallback was needed. `scripts/db/setup_roles.py --verify-only` confirmed:
  - `dial_app` has no superuser, BYPASSRLS, CREATEROLE or CREATEDB;
  - `dial_app` is not a member of any role that has them;
  - `dial_app` can't create objects in `public` and owns no tables.

  A live probe as `dial_app` through the pooled host could read tables and was refused `CREATE TABLE`.
- **Grants** (`create_roles.sql`, idempotent): `USAGE` on schema `public`; `ALTER DEFAULT PRIVILEGES FOR ROLE dial_owner` granting `SELECT, INSERT, UPDATE, DELETE` on tables and `USAGE, SELECT` on sequences to `dial_app` and `dial_platform`. Neither role can create or alter tables.
- **Connection URLs:** `DATABASE_URL` is `dial_app` through Neon's **pooled** host (`-pooler`). `DATABASE_MIGRATION_URL` is `dial_owner` through the **direct** host. The platform service's `DATABASE_URL` is `dial_platform`.
- **psycopg 3 behind the pooler:** `OPTIONS={"prepare_threshold": None}`, `DISABLE_SERVER_SIDE_CURSORS=True`, `CONN_HEALTH_CHECKS=True`.

### 6. Background tasks and the platform-admin service

- **Tasks** take `business_id` as their first argument. A decorator, `@tenant_task`, runs the body inside `tenant_context(business_id)`. A test fails if any task in `apps/*/tasks.py` lacks the decorator or a `# platform-scope:` marker.
- **Outbox dispatch without bypassing RLS:** when an `OutboxEvent` is written, `transaction.on_commit` enqueues `dispatch_outbox(business_id, event_id)`. A periodic sweeper (every minute, Celery beat) reads the global `Business` table and, per business, dispatches leftover events inside `tenant_context`. The worker stays on `dial_app`.
- **No Redis in development:** if `REDIS_URL` is empty (local only; production settings refuse it), Celery runs tasks eagerly *after commit* and the cache is in-memory. The outbox is still written in the same transaction, so code paths don't change. You can add a free Upstash Redis URL any time to run a real worker.
- **Platform-admin service:** same codebase, `DJANGO_SERVICE=platform_admin`, connects as `dial_platform`, serves Django admin only, and only on `PLATFORM_ADMIN_HOST`. The API service never mounts admin. In M1, admin registers only global models (Business, BusinessDomain, AppVersion) plus read-only views. Everything else is M6.

### 7. How tests prove isolation

- **Test roles:** a `django_db_setup` override in `backend/conftest.py` creates and migrates the test database as `dial_owner` (so tables are owned and RLS is forced as in production), then points the default connection at the same database as `dial_app`. A smoke test asserts `current_user = 'dial_app'` and that it can't bypass RLS. SQLite is refused by settings. In the test database only, `dial_app` is also granted `TRUNCATE`, which Django needs to empty tables after transactional tests; real databases never grant it.
- **Contract test** (`tests/test_tenancy_contract.py`): for every installed model, exactly one of these must hold:
  1. it's in `GLOBAL_MODELS` in `apps/tenancy/registry.py` (Business, BusinessDomain, AppVersion, and Django's own contenttypes, auth Permission/Group and migrations), each with a reason;
  2. it's a `TenantModel` whose table has RLS enabled and forced, and a `tenant_isolation` policy in `pg_policies`;
  3. it's in `NULLABLE_TENANT_MODELS` with a nullable `business` FK and the same policy.

  M2M auto-created through tables are banned, so every link table is an explicit tenant model.
- **DB-level test:** creates rows for businesses A and B with raw SQL. Under A's context it runs `SELECT` on every tenant table and asserts that zero of B's rows come back. With no context, it asserts zero rows at all. It also asserts that an `INSERT` of a B row under A's context fails.
- **Endpoint harness** (`apps/core/testing/tenancy.py`): fixtures `business_a`, `business_b`, `api_client_for(business, user)` (sets the Host header), and `assert_cross_business_404(make_object, url_for)`. Every endpoint test module must call it. A meta-test fails if a module under `apps/*/tests/test_api_*.py` doesn't.
- **Token binding:** access tokens carry `business_id`. Authentication rejects a token on any other business's host, and a harness test proves it (details in ADR-0002).

### 8. App dependency order: one change to `CLAUDE.md` §6.6 (needs approval)

The data model puts `Device` and `Invitation` (accounts) on a branch, while `BranchMember` (branches) points to a user. With the current order (`accounts ← branches`), that's a cycle. **Proposal:** `core ← tenancy ← branches ← accounts ← customers / catalog ← orders ← …`

- `branches` refers to users only through `settings.AUTH_USER_MODEL`, Django's standard swappable reference, and never imports `apps.accounts`.
- `accounts` calls `branches.services` and `branches.selectors`.

If approved, `CLAUDE.md` §6.6 is updated in T01 to match.

## Consequences

- Each API request holds one transaction for its whole life. Streaming responses are not allowed in business requests; large exports go through the worker (as the design doc already says).
- `select_for_update` and the order state machine (M3) work naturally inside the request transaction.
- Tests are slower against Neon from Nairobi than against a local database. CI uses a local Postgres service, so only your local runs pay this.
- Platform staff can't sign in on business hosts, and business users can't sign in on the admin host. This falls out of the design.

## Alternatives rejected

- **Schema per tenant** (django-tenants): heavy migrations with thousands of businesses, and a dependency outside the approved list.
- **App-layer filtering only:** one missed filter leaks data, and the design requires RLS.
- **Session-level `SET app.business_id`:** unsafe with pooled connections.
