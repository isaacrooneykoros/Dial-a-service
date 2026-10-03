# ADR-0005: Continuous integration and dependency audit

- **Status:** Accepted (owner, 2026-10-03: pip-audit approved; the owner creates the GitHub repository)
- **Date:** 2026-10-03
- **Sources:** `CLAUDE.md` §4 (approved dependencies), §6.1 (tests as `dial_app`), §6.5 (committed `openapi.yaml`), §8 (coverage); M1 plan T11; owner decision D-21 (CI uses a Postgres 16 service container)

## Context

Every change must pass the same checks a developer runs locally, against a real Postgres with the three roles so row-level security is exercised. The plan also asks for a dependency audit. The Python audit tool, pip-audit, is not on the approved list in `CLAUDE.md` §4.

## Decision

### 1. One workflow, three jobs (`.github/workflows/ci.yml`)

It runs on every push to `main` and every pull request.

- **Backend:**
  - a `postgres:16` service container;
  - `scripts/db/setup_roles.py --create-database` creates `dial_owner`, `dial_app` (NOBYPASSRLS) and `dial_platform` (BYPASSRLS), with throwaway passwords from `DIAL_*_PASSWORD`, and verifies them;
  - migrations as `dial_owner` (`scripts/migrate.sh`) and a check for missing migrations;
  - ruff, ruff format and mypy;
  - `check_openapi` (the committed schema must match the code);
  - pytest as `dial_app` under coverage.
- **Coverage gates (`CLAUDE.md` §8):**
  - at least 80% overall;
  - at least 90% on `apps/*/services`, `apps/catalog/pricing.py` and `apps/orders/state_machine.py`.
- **Frontend:**
  - `npm ci`;
  - `api:gen` must leave `src/api/schema.d.ts` unchanged;
  - typecheck, lint, Prettier, Vitest, build;
  - the per-app first-load budget (200 KB gzipped).
- **Dependency audit:**
  - `pip-audit --strict` over the pinned backend requirements (`dev.txt` and `prod.txt`);
  - `npm audit --audit-level=high` over the frontend lockfile.

The CI database passwords and Django secret key are written in the workflow on purpose. The database exists only inside one job and can't be reached from outside, so these values protect nothing. Real secrets never go in the workflow (`CLAUDE.md` §6.7).

### 2. pip-audit as a CI-only tool

- `pip-audit` 2.10.1, from the Python Packaging Authority, checks pinned packages against the PyPI and OSV vulnerability databases.
- It and its dependencies are pinned in `backend/requirements/audit.txt` and installed **only in the audit job**. They are not part of `dev.txt`, so developers' environments and the app are unchanged.
- To upgrade, create a clean virtualenv, `pip install pip-audit==<version>`, and `pip freeze --exclude pip` into `audit.txt`.

### 3. Action versions

`actions/checkout`, `actions/setup-python` and `actions/setup-node` are pinned to major v7, current at the time of writing.

## Consequences

- A change that weakens tenant isolation, leaves a migration out, changes the API without its schema, or drops coverage fails CI before review.
- A newly published vulnerability in a pinned package can turn CI red without any code change. That is intended: upgrade the package (or record why not) before merging.
- CI depends on GitHub Actions. The repository is private, and GitHub's free minutes for private repositories are limited; a typical run takes a few minutes.

## Alternatives rejected

- **Safety (pyup):** its vulnerability database needs an account for full data.
- **Dependabot alone:** it opens upgrade PRs but doesn't fail a build on known vulnerabilities. It can be added later alongside pip-audit.
- **Running the backend tests against Neon from CI:** slower, would need real credentials as secrets, and isn't independent of the developer's database.
