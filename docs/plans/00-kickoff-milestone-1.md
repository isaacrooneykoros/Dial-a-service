# Kickoff prompt: Milestone 1 (Foundation)

Paste everything below the line into the first Claude Code session, started in the repository root.

---

You are the founding senior engineer of **Dial A Service**, a multi-tenant laundry business platform that laundries in Kenya rent monthly. I'm the founder. We're starting from an empty repository with a finished design. Your job in this session is to understand the design deeply, plan Milestone 1, and then build it to production quality, one reviewed task at a time.

## Step 0: Read everything first

Read `CLAUDE.md` completely, then every file in `docs/design/` end to end: the design doc, all screen specs and `diagrams.md`. `CLAUDE.md` is binding for how you work; the design doc is binding for what we build. Don't write any code in this step.

## Phase A: Show me you understand (no code)

Create `docs/UNDERSTANDING.md` containing:

1. The product in five sentences, as you'd explain it to a laundry owner.
2. The invariants from `CLAUDE.md` §6 in your own words, with one sentence each on what would go wrong without it.
3. Milestone 1's scope, and an explicit list of what is **not** in Milestone 1.
4. Anything in the docs that is ambiguous, contradictory or risky, with the file and section.
5. Up to 10 questions for me, most important first. Only ask what you genuinely can't decide from the docs.

Also create `docs/decisions/OPEN.md` listing the open decisions from the design doc.

**Then stop and wait for my answers.**

## Phase B: Plan Milestone 1 (no code)

After I reply, write:

- `docs/plans/M1.md`: the tasks below, refined into an ordered list. Each task should be half a day or less of work and include: goal, files to create or change, tests to write, acceptance criteria, and risks. Split a task if it's bigger than that.
- `docs/decisions/ADR-0001-tenancy-and-rls.md`: tenant resolution, context propagation, `TenantModel` and managers, the RLS migration operation, the three database roles, how Celery tasks and the platform-admin service get their context, and how tests prove isolation.
- `docs/decisions/ADR-0002-auth-and-sessions.md`: per-business users, phone normalization, OTP design, JWT with an in-memory access token and an httpOnly refresh cookie, invitations, registered devices and PIN switching, throttling.
- `docs/decisions/ADR-0003-frontend-architecture.md`: one Vite app with route areas, config bootstrap, generated API client, i18n, design tokens.

**Then stop and wait for my approval.**

## Phase C: Build Milestone 1

Execute the approved plan one task at a time using the loop in `CLAUDE.md` §3. After each task: all tests, lint and type checks pass, commit on the task branch, and give me a short report. **Also stop for my review after T04, T06 and T10**, and any time you're blocked or a rule in `CLAUDE.md` says ask.

### Milestone 1 tasks (starting point for the plan)

**T01. Repository and tooling**

- Monorepo layout from `CLAUDE.md` §5.
- `.gitignore`, and `.gitattributes` for line endings (Windows).
- Backend: `pyproject.toml` (ruff, mypy), `pytest.ini`, requirements split into base, dev and prod, settings split into base, local, test and production, driven by django-environ.
- A complete `.env.example` with comments.
- `README.md` with setup for Windows (PowerShell).
- The twelve apps created empty.

**T02. Database and roles**

- `scripts/db/create_roles.sql` for `dial_owner`, `dial_app` (NOBYPASSRLS) and `dial_platform` (BYPASSRLS), with the grants.
- `scripts/migrate.ps1` and `migrate.sh` that run migrations as the owner role.
- Settings that pick up `DATABASE_URL` and the migration URL.
- Documentation for both a Neon dev branch and a local Postgres 16 (a Docker compose file is fine).

**T03. Core**

- Abstract base model with a UUID primary key and created/updated timestamps.
- Request-ID middleware.
- Structured JSON logging with phone-number masking.
- DRF exception handler producing the error envelope.
- Cursor pagination defaults.
- `GET /api/v1/health`, checking the database and Redis.
- drf-spectacular set up, with `openapi.yaml` generated and committed.

**T04. Tenancy — the most important task**

- Models: `Business` and `BusinessDomain` (global), plus a minimal `BusinessBranding` (name, colours, logo URL) and `BusinessSetting`.
- Host-resolution middleware with a cache; a tenant-context contextvar.
- The transaction middleware that sets `app.business_id` with `set_config(..., true)`.
- `TenantModel` with its guarded manager and an explicit unscoped manager.
- The `EnableTenantRLS` migration operation, and a `tenant_context()` helper for tasks and scripts.
- The global-model registry and `tests/test_tenancy_contract.py`.
- The DB-level isolation test: raw SQL under business A never returns business B's rows.
- An endpoint-level cross-business test harness that later endpoints can reuse.

**T05. Accounts and authentication**

- Custom `User`: business (null only for platform staff), phone, names, role, language, verified flag, status; unique (business, phone). Made **before the first migration of any app that references users**.
- Kenyan phone normalization in one module, with tests covering 07…, 01…, 7…, 1…, +254… and 254… inputs.
- `PhoneOTP` (hashed codes, 10-minute expiry, 5 attempts, 3 sends per hour per phone).
- `Invitation` (hashed token, 7-day expiry) and `ConsentRecord`.
- Endpoints for X-10 to X-14: register, verify-phone and resend, login, refresh (httpOnly cookie, rotation, blacklist), logout, password reset request and confirm, password change, invitation accept.
- Throttles on login and codes. Login errors never reveal whether the phone exists.
- SMS goes through the notification outbox (T07).

**T06. Registered devices and PIN switching (X-15)**

- `Device` model tied to a branch. For M1, a minimal `Branch` model is allowed if the plan says why; otherwise register the device to the business and add the branch link in M3.
- Staff PINs, hashed.
- `POST /staff/devices` (manager or owner only), `POST /auth/pin-switch`.
- Lock after 5 wrong PINs; idle lock handled on the client.
- Owner endpoint to list and sign out sessions.

**T07. Audit log, outbox, notifications and idempotency**

- `AuditLog` with a helper to record actions.
- `OutboxEvent`, and a Celery dispatcher task that runs under the tenant context.
- `Notification` and `NotificationTemplate` (SMS only in M1), a pluggable SMS backend interface, and a console backend for dev.
- The sign-in code template and the invitation template from the notification catalogue.
- `IdempotencyKey` middleware with the rules in `CLAUDE.md` §6.5.
- `GET /business/config` returning only branding and basic settings (enough for X-01).
- `GET /app/version`.

**T08. Uploads**

- `POST /uploads` returns a short-lived presigned upload URL for private R2 storage, with keys prefixed by the business ID, plus a photo record ID.
- A local development alternative (filesystem storage or MinIO; the ADR decides).
- Type and size limits.

**T09. Frontend foundation**

- Vite + React + TypeScript (strict), with route areas `/console`, `/staff`, `/rider`, `/` and `/o/:token`, each a placeholder page except auth.
- X-01 splash with config bootstrap and branding via CSS variables.
- Design tokens from the Screens tab as CSS variables, with Tailwind configured to use them.
- i18n with `en` and `sw` files; keys by screen ID.
- A generated, typed API client and TanStack Query setup.
- Auth screens X-10 to X-15, with the access token in memory and a silent refresh.
- The shared states (loading, empty, error, offline, session expired, update required) as reusable components.
- `lib/format.ts` for money, weight, dates and phone numbers.
- The Vite proxy from `/api` to Django.
- Vitest tests for the format helpers and the auth flow.

**T10. Seed and developer experience**

- `python manage.py seed_dev`: businesses `mamasafi` and `cleanpro` with `*.localhost` domains, an owner, a manager and a staff member each (with PINs), printing the logins.
- A one-page "run it locally" section in the README that I can follow on Windows.

**T11. Continuous integration**

A GitHub Actions workflow with:

- backend: Postgres 16 service, create roles, migrate as owner, pytest as `dial_app`, ruff, mypy;
- OpenAPI schema generation and a diff check;
- frontend: `npm ci`, typecheck, lint, test, build.

**T12. Staging configuration (write only, don't deploy)**

- `render.yaml` with three services: `api` (dial_app), `worker` and `platform-admin` (dial_platform, Django admin only on the admin host).
- `docs/ops/deploy.md` with the manual steps for me: Neon branches and roles, Render environment variables, the Cloudflare wildcard DNS and routing (`/api/*` to Render, everything else to Pages), and R2 bucket setup.

### Milestone 1 acceptance

Milestone 1 is done only when every one of these is true:

- On my Windows machine, following the README, `mamasafi.localhost:5173` and `cleanpro.localhost:5173` each show their own branding; an owner can log in, reset a password, invite a staff member, and that staff member can accept the invitation and switch in by PIN on a registered device.
- The tenancy contract test, the DB-level isolation test and the cross-business endpoint tests all pass, and CI is green.
- No SMS is sent inline; codes appear through the console SMS backend via the outbox.
- `openapi.yaml`, `.env.example`, `README.md`, the ADRs and `docs/CHANGELOG.md` are up to date.
- Nothing from Milestone 2 onwards has been built: no catalogue, orders or payments.

Start with Step 0 now.
