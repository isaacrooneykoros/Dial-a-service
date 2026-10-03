# Dial A Service — Claude Code project guide

Read this file completely at the start of every session. It is the contract for how code is written in this repository.

## 1. What we are building

Dial A Service is a multi-tenant SaaS that laundry businesses in Kenya rent monthly to run their counter, pickups, deliveries, payments and reports.

- Each business gets its own subdomain (`{slug}.dialaservice.co.ke`), branding, branches, staff, riders, customers, price list and M-Pesa Till or Paybill.
- The platform never holds order money. Customers pay the business directly (M-Pesa prompt, recorded M-Pesa code, Paybill match, or cash). The platform earns subscriptions and SMS top-ups.
- Build order: the counter product (Starter plan: staff app, console, public order pages, payments) first; delivery (Growth plan: booking app, riders) later.
- The owner is a solo founder. Explain decisions in plain language and give exact commands (PowerShell on Windows).

## 2. Sources of truth — read before any work

| File | What it is |
| --- | --- |
| `docs/design/00-design-doc.md` | Architecture, tenancy, roles, order flows, payments, pricing, data model, API, security, milestones. **Authoritative.** |
| `docs/design/10-screens-shared.md` | Screen inventory, design system, shared states, content rules, notification catalogue |
| `docs/design/11-staff-app.md` | Staff app screens (S-, X-15) |
| `docs/design/12-business-console.md` | Business console screens (A-, B-) |
| `docs/design/13-customer-app.md` | Customer app and public order pages (C-) |
| `docs/design/14-rider-app.md` | Rider app screens (R-) |
| `docs/design/15-platform-and-website.md` | Website (W-) and platform admin (P-) |
| `docs/design/diagrams.md` | Architecture, order state machine and payment flow as Mermaid |
| `docs/decisions/ADR-*.md` | Decisions made during the build |
| `docs/decisions/OPEN.md` | Decisions still pending (never invent answers) |

**Precedence:** latest ADR > design doc > screen specs > your judgement.

If the docs are silent or contradict each other on anything touching data, money, security, permissions or a screen's behaviour: **stop and ask**. Never invent a business rule, price, limit, legal text or message wording. When something pending is needed to proceed, put it in settings with a safe default, mark it `# TODO(decision): <topic>`, and add it to `docs/decisions/OPEN.md`.

Screen IDs (X-10, S-40, A-01, C-60…) are permanent. Use them in component names, i18n keys, test names and commit messages.

## 3. How we work

**Loop for every task:** Inspect relevant code → state the plan (files, tests) → implement the smallest sound change → run tests, lint, type check → review your own diff against §6 → fix → commit → report.

**Report after each task (short):** what changed and why, files touched, tests added and their result, edge cases considered, known limitations.

**Stop and wait for the owner:**

- after writing a milestone plan;
- before adding any dependency not in §4;
- before a migration that changes or deletes existing data;
- before weakening or changing any invariant in §6;
- before anything involving deployment, production, DNS or real secrets;
- whenever a rule in §2 says ask.

**Never** say a task is done without passing tests. If tests fail, find the cause and fix it; never report a failure without a diagnosis.

## 4. Stack (approved dependencies)

When scaffolding, check the current stable release of each package and pin exact versions in lockfiles. Do not assume version numbers from memory.

**Backend:** Python 3.12, Django 5.2 LTS, Django REST Framework, djangorestframework-simplejwt, drf-spectacular, psycopg 3, django-environ, Celery 5 + redis, django-storages + boto3 (Cloudflare R2), cryptography (field encryption), phonenumbers, sentry-sdk, gunicorn, whitenoise (admin static only).

**Backend dev:** pytest, pytest-django, factory-boy, time-machine, coverage, ruff, mypy + django-stubs.

**Frontend:** Node 22 LTS, React + TypeScript (strict), Vite, React Router, TanStack Query, react-hook-form + zod, i18next + react-i18next, openapi-typescript + openapi-fetch, Tailwind CSS (driven by the design-system CSS variables), lucide-react.

**Frontend dev:** Vitest, Testing Library, ESLint, Prettier.

Anything else needs an ADR explaining why, and the owner's approval first.

## 5. Repository layout

```text
dial-a-service/
  CLAUDE.md
  backend/
    config/settings/  base.py  local.py  test.py  production.py
    config/  urls.py  wsgi.py  celery.py
    apps/  core  tenancy  billing  accounts  customers  catalog
           branches  riders  orders  payments  notifications  support
    scripts/  migrate.ps1  migrate.sh  db/create_roles.sql
    requirements/  base.txt  dev.txt  prod.txt
    openapi.yaml            # committed; CI fails on unexpected diff
    manage.py  pyproject.toml  pytest.ini  .env.example
  frontend/
    src/apps/  console  staff  rider  customer  public
    src/  components  api  i18n/en  i18n/sw  lib  styles
    package.json  vite.config.ts  tsconfig.json  .env.example
  website/                  # later milestone
  docs/  design/  decisions/  plans/  ops/  CHANGELOG.md
  .github/workflows/ci.yml
  render.yaml
```

Inside each Django app: `models.py`, `services.py` (or `services/`), `selectors.py`, `api/` (serializers, views, urls), `admin.py`, `tests/`.

## 6. Non-negotiable invariants

### 6.1 Tenant isolation (the most important property of the platform)

- **Resolution:** middleware resolves the business from the `Host` header through `BusinessDomain` (cached for 60 s). An unknown host gets 404 before any view runs. The platform-admin host has no business.
- **Models:** every business-owned model subclasses `apps.core.models.TenantModel`, which has a non-null, indexed `business` FK. `business` comes first in composite indexes and unique constraints, e.g. `UniqueConstraint(fields=["business", "phone"])`.
- **Managers:** `TenantModel.objects` raises `TenantContextMissing` when no business is in context. The unscoped manager is used only in platform code paths, each marked `# platform-scope: <reason>`.
- **Input:** `business` is never read from request data. Services set it from the context.
- **Row-level security:** every tenant table has `ENABLE` and `FORCE ROW LEVEL SECURITY` and a policy `USING (business_id = NULLIF(current_setting('app.business_id', true), '')::uuid) WITH CHECK (same)`. (`NULLIF` because Postgres reports a once-set setting as `''`, not NULL; with no business every query sees zero rows. ADR-0001 §4.) Policies are created by a reusable migration operation (`apps.core.db.EnableTenantRLS`), never hand-written per table.
- **Per request:** a middleware wraps the request in `transaction.atomic()` and runs `SELECT set_config('app.business_id', %s, true)`. The setting is transaction-local, so it is safe behind Neon's pooled connections. Never use session-level `SET`.
- **Background tasks:** tasks take `business_id` as an argument and run inside `with tenant_context(business_id):`, which does the same thing.
- **Database roles** (created by `scripts/db/create_roles.sql`):

| Role | Used by | RLS |
| --- | --- | --- |
| `dial_owner` | Migrations only (`scripts/migrate.ps1`) | Owns tables |
| `dial_app` | API web service and worker | `NOBYPASSRLS`: subject to policies |
| `dial_platform` | Platform-admin service and cross-tenant jobs (billing) only | `BYPASSRLS` |

- **Tests:**
  - `tests/test_tenancy_contract.py` walks every model. Each one must be either in the global allow-list (`apps/tenancy/registry.py`) or a `TenantModel` with a policy present in `pg_policies`.
  - Every endpoint test module includes a cross-business test: a user of business A gets 404 on business B's object.
  - A database-level test runs raw SQL under business A's context and asserts that zero of business B's rows come back.
  - Tests connect as `dial_app`, so RLS is really exercised. SQLite is not supported.

### 6.2 Money

- Amounts are `DecimalField(max_digits=12, decimal_places=2)` plus a `currency` code (`"KES"`). Never float, anywhere, including the frontend: amounts travel as strings.
- All price maths lives in `apps/catalog/pricing.py`. Totals are rounded half-up to whole shillings there and only there.
- The ledger is append-only: a `LedgerTransaction` with balanced `LedgerEntry` rows (debits equal credits, checked in the service and in tests). Balances are always computed, never stored.
- Only `apps/payments/services` changes payment state. An order is marked paid only by: a Daraja callback, an STK status query, a matched C2B payment, or a staff-recorded M-Pesa code or cash payment carrying the staff member and device.
- M-Pesa codes are unique per business and format-validated.
- Daraja secrets are encrypted with `FIELD_ENCRYPTION_KEY` and never serialized to any API response or log.

### 6.3 Order state machine

- There is exactly one module, `apps/orders/state_machine.py`, holding the transition table from the design doc. States: `booked`, `picked_up`, `received`, `processing`, `ready`, `out_for_delivery`, `completed`, `cancelled`.
- Every change goes through `transition(order, to, *, actor, reason=None)`. It locks the row with `select_for_update`, validates the move, writes an `OrderStatusEvent` and an `OutboxEvent`, and raises `OrderTransitionError` for anything else, which the API returns as HTTP 409.
- Release rule: `out_for_delivery` and `completed` require payment status `paid`, or a trusted customer within their limit.

### 6.4 Side effects

- SMS, email and webhooks are never sent inline. Write a `Notification` or `OutboxEvent` in the same transaction; the worker dispatches it with retries.
- Development uses a console SMS backend that prints messages.

### 6.5 API

- `/api/v1` with DRF. State changes use explicit action endpoints (`POST /staff/orders/{ref}/weigh`).
- Error envelope everywhere: `{"code", "message", "fields", "request_id"}`. Messages are safe to show to users.
- Cursor pagination, 20 per page by default.
- `Idempotency-Key` is required on mutating POSTs from the apps. Middleware stores it per business, user and key for 24 hours. A repeat returns the stored response; the same key with a different body returns 409.
- Permissions: role classes plus object scoping in `get_queryset`. Never rely on frontend checks.
- The drf-spectacular schema is committed as `backend/openapi.yaml`; CI fails on an unexpected diff. The frontend client is generated from it (`npm run api:gen`).

### 6.6 Code structure

- Business logic lives in typed service functions (`services.py`) and read queries in `selectors.py`.
- Views are thin. Serializers validate shape only.
- No business logic in `Model.save()` or signals.
- App dependencies point one way: `core ← tenancy ← branches ← accounts ← customers / catalog ← orders ← payments / riders ← notifications / support / billing` (ADR-0001 §8). `branches` refers to users only through `settings.AUTH_USER_MODEL` and never imports `apps.accounts`. `core` refers to the business only as the string `"tenancy.Business"`.
- No import cycles. One app calls another only through that app's services or selectors.

### 6.7 Security and privacy

- Secrets come only from environment variables through django-environ. `.env` is never committed. `.env.example` lists every variable with a dummy value and a comment.
- OTPs, PINs, invitation tokens and public-link tokens are stored only as hashes. Public order tokens have at least 128 bits of randomness.
- DRF throttles are keyed by business plus IP or user. Login, codes, PIN entry and payments have tighter limits.
- Logs are structured JSON. Phone numbers are masked. Passwords, codes, tokens, PINs and M-Pesa secrets never appear.
- Every mutating action in the console, staff app and platform admin writes an `AuditLog` row.

### 6.8 Frontend

- One Vite app with route areas `/console`, `/staff`, `/rider`, `/` (customer) and `/o/:token` (public pages).
- On start (X-01), fetch the business config and apply branding through CSS variables.
- No hard-coded user-facing strings. i18n keys are namespaced by screen ID (`"S-40.button.save_and_pay"`), with `en` and `sw` files.
- Money, weight, dates and phone numbers are formatted only through `src/lib/format.ts`.
- Every screen implements the shared states (loading, empty, error, offline) from `docs/design/10-screens-shared.md`.
- The access token is kept in memory only; the refresh token is an httpOnly cookie handled by `/api/v1/auth/refresh`. The API is same-origin; in dev, Vite proxies `/api` to Django.
- Screen components are named by ID, e.g. `src/apps/staff/screens/S40NewOrder.tsx`.

## 7. Local development (Windows)

- **Business hosts:** Chrome and Edge resolve `*.localhost` to 127.0.0.1, so use `http://mamasafi.localhost:5173` and `http://cleanpro.localhost:5173`. `ALLOWED_HOSTS` includes `.localhost`.
- **Database:** Postgres 16, either a Neon dev branch or a local Postgres (Docker Desktop). Run `scripts/db/create_roles.sql` once.
- **Seed data:** `python manage.py seed_dev` creates two businesses (`mamasafi`, `cleanpro`), each with a domain, its own branding, a branch, and an owner, a manager and a staff member with passwords and PINs, and prints their logins. It is safe to run again and refuses production settings. `python manage.py create_business` adds a real business by hand (the owner's password is prompted, never passed as an argument).
- **Celery on Windows:** `celery -A config worker --pool=solo -l info` (the default pool doesn't run on Windows).

Backend (PowerShell, from `backend/`). These commands are created in Milestone 1; keep this section accurate:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements\dev.txt
Copy-Item .env.example .env        # then fill in the values
.\scripts\migrate.ps1              # runs migrations as dial_owner
python manage.py seed_dev
python manage.py runserver
pytest
ruff check . ; ruff format --check . ; mypy .
```

Frontend (from `frontend/`):

```powershell
npm ci
npm run api:gen
npm run dev
npm run typecheck ; npm run lint ; npm run test
```

## 8. Testing standards

- pytest against Postgres as `dial_app`, with factories per app.
- **Every endpoint:** happy path, validation errors, permission per role, cross-business 404, and an idempotent replay for POSTs.
- **State machine and money:** table-driven tests for every allowed and disallowed transition; a ledger balance assertion after every money operation.
- **Coverage:** at least 90% on services, pricing and the state machine; at least 80% overall.
- **Frontend:** Vitest for `lib/` and hooks, plus component tests for critical screens (X-10, S-40, S-42, S-43).

## 9. Git

- Conventional commits (`feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`), one logical change per commit, and the screen ID or milestone task in the message when relevant (`feat(accounts): X-12 OTP verification`).
- Branch per milestone task: `m1/t04-tenancy-rls`.
- Never commit `.env`, secrets, uploaded files or build output.
- Update `docs/CHANGELOG.md` at the end of each milestone.

## 10. Definition of done (every task)

A task is done only when you can answer all of these:

- What changed, and why?
- Which files changed?
- Does it work, and how was it tested? (commands and results)
- Which edge cases were considered?
- Does existing behaviour still work? (full test suite green)
- Were the docs, `.env.example` and `openapi.yaml` updated?
- What are the known limitations or follow-ups?

## 11. Never

- Never build features from a later milestone than the current one.
- Never read `business` from the client, or query tenant data without a business context.
- Never use floats for money, or compute prices outside `pricing.py`.
- Never mark anything paid because the frontend said so.
- Never send SMS or email inline in a request.
- Never edit or delete ledger entries, audit log rows or status events.
- Never hard-code secrets, prices, plan limits or user-facing text.
- Never disable, skip or weaken a failing test to make CI pass.
- Never run deployments, touch DNS, or use real M-Pesa credentials; sandbox only.
- Never rewrite working code for style alone.
