# Changelog

All notable changes, grouped by milestone. Updated at the end of each milestone.

## Milestone 1: Foundation (in progress)

### Added

- Design documents, screen specs and diagrams in `docs/design/`.
- Phase A understanding (`docs/UNDERSTANDING.md`) and open decisions (`docs/decisions/OPEN.md`).
- Milestone 1 plan and ADR-0001 (tenancy and RLS), ADR-0002 (auth and sessions), ADR-0003 (frontend architecture), all approved 2026-10-01.
- Repository skeleton: `.gitignore`, `.gitattributes`, `README.md`.
- Backend skeleton (T01b): Python 3.12, Django 5.2.17 LTS, settings split into base, local, test and production (driven by django-environ, refusing SQLite and unsafe production values), pinned requirements, ruff, mypy and pytest configuration, `.env.example`, and the twelve empty apps.
- Database roles (T02a): `dial_owner`, `dial_app` (NOBYPASSRLS) and `dial_platform` (BYPASSRLS) with per-database grants, a setup and verification script, migration scripts that run only as the owner, and `docs/ops/neon-dev.md`. Verified on the Neon `dev` branch.
- Test database harness (T02b): pytest creates and migrates the test database as `dial_owner`, applies the grants, then runs every test as `dial_app` over Neon's direct host. Tests prove the test role can't bypass RLS or create tables.
- Core (T03a): `BaseModel` (random UUID key, UTC timestamps); request IDs on every request, response (`X-Request-ID`) and log line; JSON logging that masks Kenyan phone numbers and redacts passwords, PINs, codes, tokens and secrets at any depth.
- API conventions (T03b): the error envelope `{code, message, fields, request_id}` for every error (DRF, Django 404/500), with user-safe messages and `retry_after` on 429; every error response rolls back the request transaction; cursor pagination (20 per page); `GET /api/v1/health` (database and Redis); the OpenAPI schema at `/api/schema/`, committed as `backend/openapi.yaml` and checked by `manage.py check_openapi`; `Accept-Language` support.
- Tenant context and layer 1 isolation (T04a): `tenant_context()` (contextvar plus transaction-local `app.business_id`, cleared even inside outer transactions), `TenantModel` with a manager that refuses to run without a business and a save/bulk-create guard, `unscoped` manager checked by a code-rule test; global `Business` and `BusinessDomain` with W-03 address rules and database constraints; a test-only tenant app.
- Row-level security and the tenancy contract (T04b): `EnableTenantRLS` (enable and force RLS plus the `tenant_isolation` policy, using `NULLIF` so an unset business always means zero rows) and `MakeAppendOnly` (revoke UPDATE and DELETE) migration operations; `BusinessBranding` (WCAG AA check on the primary colour) and `BusinessSetting` (typed registry, no M1 keys) with RLS; the global-model registry and `tests/test_tenancy_contract.py`; the test harness now sets default privileges before migrating, and the grant script no longer re-grants on existing tables.

### Changed

- `CLAUDE.md` §6.6: app dependency order now puts `branches` before `accounts` (ADR-0001 §8).
- `CLAUDE.md` §6.1 and ADR-0001 §4: the RLS policy compares with `NULLIF(current_setting('app.business_id', true), '')::uuid` (owner-approved).
