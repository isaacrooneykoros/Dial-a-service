# Milestone 1 report: Foundation

- **Date:** 2026-10-03
- **Plan:** `docs/plans/M1.md` (T01–T13), approved 2026-10-01
- **Summary:** what was built is in `docs/CHANGELOG.md` under "Milestone 1".

## Acceptance checklist (from the kickoff)

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Following the README on the owner's Windows machine: `mamasafi.localhost:5173` and `cleanpro.localhost:5173` show their own branding; an owner logs in, resets a password, invites a staff member, who accepts and switches in by PIN on a registered device | **Done by Claude; the owner's own try-out not yet confirmed** | T10 run against the Neon dev database, through the Vite dev server on each business's address: 25 of 25 checks passed (branding per business, log-in, password reset with the code from the log, invite, accept, PIN, S-02 registration, PIN switch, wrong-PIN countdown, no cross-business access). The browser screens are covered by component tests. |
| 2 | Tenancy contract test, database-level isolation test and cross-business endpoint tests pass; CI green | **Done** | About 600 backend tests (all green locally, in parts on Neon) and about 190 frontend tests. CI on GitHub reported green by the owner. The last three commits (D-51, T12, the T13 docs) still need pushing and their CI run. |
| 3 | No SMS is sent inline; codes appear through the console SMS backend via the outbox | **Done** | `send_sms` writes a `Notification` and an outbox event in the caller's transaction, and the worker sends after commit (T07b). A code rule test keeps the SMS backends behind the outbox. In development, codes print in the `runserver` window. Production now refuses the console backend. |
| 4 | `openapi.yaml`, `.env.example`, `README.md`, the ADRs and `docs/CHANGELOG.md` are up to date | **Done** | `check_openapi` passes. `.env.example` lists `RENDER_EXTERNAL_HOSTNAME` and the SMS backend rules. The README has the Windows run guide. ADR-0001 to ADR-0005 are Accepted. |
| 5 | Nothing from Milestone 2 onwards has been built (no catalogue, orders or payments) | **Done** | `apps/catalog`, `apps/orders` and `apps/payments` contain no models. Staff photos (D-45) were agreed for M3 and not built early. |

The design doc's M1 row also lists **staging on Render + Neon + Cloudflare**. Its configuration is written (T12: `render.yaml`, `docs/ops/deploy.md`, the "Migrate staging" workflow) but **not deployed**. Deploying, DNS and secrets are owner actions, and **D-52** (how `/api/*` reaches Render with the business's address) must be decided first.

## Decisions made during M1

- **Recorded in `OPEN.md` → Decided:** D-18 to D-27, D-36, D-37, D-45, D-47 to D-49 and D-51.
- **During the build:**
  - the migrations run separately from Render;
  - the platform-admin service is defined but serves nothing until M6;
  - pip-audit in CI (ADR-0005).

## Open items carried forward

| Item | When |
| --- | --- |
| D-52: API routing on Cloudflare with the business host | Before the first staging deploy |
| D-08: SMS gateway and sender ID | M4 |
| D-35: platform-admin 2FA | M6 |
| D-34: where staff rights live long-term | M3 |
| D-45: staff photos (decided; build and where photos are taken) | M3 |
| Node 22.23.2 upgrade on the owner's PC (needs the admin prompt) | Any time |
| WSL, for Docker and a fast local test database (optional) | Any time |
| The staff app's first-load size is 179 of 200 KB; `zod/mini` is the first lever | Watch in M2–M3 |

## What went well, what to watch

- **Went well:** isolation is enforced three ways and proven by tests, including a deliberate break of RLS that the tests caught. Most bugs were found by tests before they reached you: the navigation race on device lock, the bundle undercount, and the CI database URL.
- **Watch:**
  - **Neon is slow for the full backend suite locally:** 30–40 minutes on bad days. CI on GitHub runs it on its own fresh database and is much faster.
  - **Shell quoting:** escaping in file edits caused several small breakages along the way. Each was caught at once by the linters and tests.
