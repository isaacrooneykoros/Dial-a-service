# Milestone 2 report: Catalogue and pricing

- **Date:** 2026-10-04
- **Plan:** `docs/plans/M2.md` (T01–T10), approved 2026-10-03 with every recommendation (D-53 to D-60)
- **Summary:** what was built is in `docs/CHANGELOG.md` under "Milestone 2".

## Acceptance (design doc M2 row)

> "Pricing tests cover per kg, per item, minimums, modifiers, discounts, VAT, rounding and snapshots."

| Covered | Where | Evidence |
| --- | --- | --- |
| Per kg, per item, flat, mixed orders | `apps/catalog/tests/test_pricing.py` | `TestLines` |
| Minimum charges | same | Under, at and over the minimum; modifiers applied to the minimum |
| Modifiers | same | Percentages add up per line (D-54); flat amounts once per order; chosen services only (D-55); ones that apply to nothing are reported |
| Discounts | same | Percent and amount, at, under and over the cap; 0% until set; never below zero (D-56) |
| VAT | same | Not registered, included ("of which", from the rounded total), added on top; after the discount; the delivery fee taxable (D-53) |
| Rounding | same | Lines to the cent, the total half-up to the shilling at .49 and .50, the rounding kept |
| Snapshots | same, `test_services.py` | Each line names its price version; versions never change once started |

- **Tests:** pricing.py has 100% line and branch coverage, the catalogue services 94%, the selectors 98%. Every new endpoint has tests for its happy path, validation, roles, cross-business access and idempotent replay.
- **Dev database:** checked against your Neon dev database after migrating and seeding. Each business's config shows only its own price list, and a staff quote for 6.4 kg wash and fold plus 2 duvets with Express 50% gave KSh 2,502 (1,152 + 1,350), as calculated by hand.

## Changes from the plan

- **The concurrent price-change test isn't the two-connection test the plan described.** The test harness switches the database role and test database on the main thread's connection only, so a second thread could have reached the dev database instead.
  - **What's tested instead:** the database refuses overlapping versions (T01), the service row lock serialises changes (T04), and a refused overlap becomes a clear "price conflict" error.
- **`seed_dev` moved from `accounts` to `catalog`**, because it now sets sample prices and only an app at or above the catalogue may call it. It will move up again when later milestones add sample data from higher apps.
- **The template list arrives through a `business.created` outbox event**, because `create_business` (in `accounts`) may not call the catalogue directly.
- **The business config is composed from registered sections** (`tenancy/config_sections.py`), for the same reason.
- **The config isn't cached,** so there was no cache to clear when prices change. The plan's "changing a price clears the cached config" doesn't apply.
- **T07 and T08 share one commit,** because they share the same three API files.

## Decided during M2

- **D-53 to D-60:** the owner's answers to the plan's questions.
- **D-61 (open, safe default in place):** VAT-registered prices include VAT by default. To confirm before the M5 settings screen.

## Bugs found by the tests and fixed

- A refused rename (a name already taken) left the rejected name on the in-memory object, so the next save failed too. Refused updates now reload the object.
- The price endpoint's default minimum charge was passed through as text, so every price set without a minimum was refused. The default is now an exact decimal.
- A field test was named like an endpoint test and was picked up by the endpoint harness rule. It has been renamed.

## For you

- **Push** and check CI. The full backend suite runs there on a fresh database. Locally, Neon was too slow tonight to run all of it in one go, so it ran in parts.
- **Try it:** start the API and frontend as in the README, then:
  - open `http://mamasafi.localhost:5173` and `http://cleanpro.localhost:5173`; each business's price list is in its config, though no screen shows it yet;
  - you can call the quote and console catalogue endpoints, but nothing in the browser uses them until M3 (S-14) and M5 (A-30, A-31).

## Next

Milestone 3, the counter core: customers, walk-in and phone orders, receiving, weighing with photos (staff photos, D-45), ready, release with a collection code, the queue, search and practice mode. Its plan comes next, for your approval.
