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

### Changed

- `CLAUDE.md` §6.6: app dependency order now puts `branches` before `accounts` (ADR-0001 §8).
