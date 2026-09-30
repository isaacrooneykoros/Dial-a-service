# Understanding: Dial A Service before Milestone 1

Written in Phase A, 2026-10-01, after reading `CLAUDE.md`, `docs/design/00-design-doc.md`, `docs/design/10-screens-shared.md`, `docs/design/diagrams.md` and the Milestone 1 kickoff. No code has been written yet.

## 1. The product in five sentences (for a laundry owner)

1. Dial A Service is the system you rent monthly to run your laundry: every order gets a reference, a bag count, a photo of the scale and a status, instead of a paper book.
2. Your staff use it on a phone or counter tablet to take walk-in and phone orders, weigh and price them, and hand them back only when they're paid, while you watch the day from the business console at home.
3. Your customers pay you directly, into your own M-Pesa Till or Paybill or in cash, and the system records it; we never touch your money and take no cut per order.
4. Customers get an SMS with the weight, the price and a link to see the photo and pay, so they need no app; when you're ready, you can switch on online booking and your own riders for pickup and delivery.
5. It runs under your own name and colours at your own web address (for example `mamasafi.dialaservice.co.ke`), and your data is yours: nobody from another laundry can ever see it, and you can export it any time.

## 2. The invariants (`CLAUDE.md` §6) in my own words

### 6.1 Tenant isolation

| Rule | What goes wrong without it |
| --- | --- |
| The business is decided by the request's host, looked up in `BusinessDomain`; unknown hosts get 404 before any view. | A request could run with no business, or a guessed host could reach an API that then falls back to "all businesses". |
| Every business-owned model inherits `TenantModel` with a required, indexed `business` FK, first in composite indexes and unique constraints. | Rows could be created without an owner, and per-business uniqueness (phone, reference) would be global, leaking "this phone exists elsewhere". |
| The default manager raises `TenantContextMissing` without a business in context; the unscoped manager is only for marked platform code. | A forgotten filter silently returns every laundry's data instead of failing loudly. |
| `business` is never taken from request data; services set it from context. | A user could write rows into another business by editing a JSON field. |
| Every tenant table has forced RLS with a policy on `current_setting('app.business_id', true)`, created only by `EnableTenantRLS`. | A bug in layer 1 (a raw query, a wrong manager) would leak data with nothing underneath to stop it; hand-written policies would drift. |
| Each request runs in one transaction that calls `set_config('app.business_id', …, true)`; never session-level `SET`. | Behind Neon's pooled connections a session setting would stick to the connection and the next request (another business) would inherit it. |
| Background tasks take `business_id` and run inside `tenant_context()`. | A task would run with no context (fails) or the wrong one (leaks or corrupts another business's data). |
| Three DB roles: `dial_owner` (migrations), `dial_app` (NOBYPASSRLS), `dial_platform` (BYPASSRLS, platform only). | If the app connected as the owner or a BYPASSRLS role, layer 2 would not exist at all. |
| Contract test over every model, cross-business 404 test per endpoint module, raw-SQL isolation test, tests run as `dial_app` on Postgres. | Isolation would rest on reviewers remembering; one new model without a policy would ship unnoticed. |

### 6.2 Money

| Rule | What goes wrong without it |
| --- | --- |
| `Decimal(12,2)` plus currency; never float, including the frontend (amounts are strings). | Rounding drift: totals that are off by a cent, receipts that don't match M-Pesa, reports that don't add up. |
| All price maths in `apps/catalog/pricing.py`; half-up rounding to whole shillings only there. | Two places computing a price would disagree; M-Pesa rejects non-whole amounts. |
| Append-only ledger of balanced transactions; balances computed, never stored. | A stored balance drifts from its history and nobody can explain the difference at cash-up. |
| Only `apps/payments/services` changes payment state, and only from a callback, status query, matched C2B payment or a staff-recorded code/cash tied to staff and device. | Laundry released against a fake "paid" from a browser, or a payment nobody is accountable for. |
| M-Pesa codes unique per business and format-checked. | The same (possibly fake) code used to "pay" several orders. |
| Daraja secrets encrypted with `FIELD_ENCRYPTION_KEY`, never serialized or logged. | A leaked API response or log line would let someone move a business's money. |

### 6.3 Order state machine

| Rule | What goes wrong without it |
| --- | --- |
| One module holds the transition table; every change goes through `transition()` with a row lock, an `OrderStatusEvent`, an `OutboxEvent`, and 409 on anything invalid. | Two staff tapping at once could double-transition an order, statuses could jump illegally, and there'd be no history for disputes. |
| `out_for_delivery` and `completed` need `paid` (or a trusted customer). | Laundry leaves unpaid, which is the problem the product exists to stop. |

### 6.4 Side effects

| Rule | What goes wrong without it |
| --- | --- |
| SMS, email and webhooks are written to an outbox in the same transaction and sent by the worker with retries; dev uses a console SMS backend. | A slow gateway blocks the counter, a rolled-back transaction still sends "Paid", or a failed send loses the message. |

### 6.5 API

| Rule | What goes wrong without it |
| --- | --- |
| `/api/v1`, explicit action endpoints for state changes. | A generic "set status" bypasses guards. |
| One error envelope with a user-safe message and `request_id`. | Apps can't show consistent errors and support can't trace a report to a log line. |
| Cursor pagination, 20 per page. | Offset pagination skips or repeats orders as new ones arrive, and large pages are slow on 3G. |
| `Idempotency-Key` on mutating app POSTs, stored per business/user/key for 24 h; same key with a different body is 409. | A retry on a flaky connection creates two orders or records a payment twice. |
| Permissions by role class plus object scoping in `get_queryset`. | Hiding a button in the UI would be the only protection. |
| Committed `openapi.yaml`, CI diff check, generated frontend client. | Backend and frontend drift apart silently and older app versions break. |

### 6.6 Code structure

| Rule | What goes wrong without it |
| --- | --- |
| Logic in typed services, reads in selectors, thin views, shape-only serializers, nothing in `save()` or signals. | Rules get scattered and bypassed (bulk updates skip `save()`, signals fire in surprising orders). |
| One-way app dependencies, no cycles, cross-app calls only via services/selectors. | The monolith becomes a tangle where a change in payments breaks accounts. |

### 6.7 Security and privacy

| Rule | What goes wrong without it |
| --- | --- |
| Secrets only from env via django-environ; `.env` never committed; `.env.example` complete. | Keys end up in git history, or a new machine can't start because a variable is undocumented. |
| OTPs, PINs, invitation and public-link tokens stored only as hashes; public tokens ≥128 bits. | A database leak hands out working codes and order links; short tokens can be guessed. |
| Throttles keyed by business plus IP/user, tighter on login, codes, PINs, payments. | Brute-forcing a 4-digit PIN or 6-digit code, SMS-cost abuse, one busy business starving others. |
| Structured JSON logs, phone numbers masked, no secrets. | Logs become a personal-data and credential leak. |
| Every mutating console, staff and platform action writes an `AuditLog` row. | No answer to "who changed this price / gave this discount / released this order". |

### 6.8 Frontend

| Rule | What goes wrong without it |
| --- | --- |
| One Vite app with route areas; branding from `/business/config` via CSS variables at start. | Separate builds per business or per app, which can't scale to many laundries. |
| No hard-coded strings; i18n keys by screen ID, `en` and `sw`. | Swahili can't be added without touching every screen. |
| Money, weight, dates and phones formatted only in `lib/format.ts`. | "KSh 1,250" in one place and "1250.00" in another. |
| Every screen implements the shared states. | Blank screens and spinners on slow 3G, lost input on errors. |
| Access token in memory, refresh token in an httpOnly cookie, same-origin API. | A script injection could steal a long-lived token from `localStorage`. |
| Screen components named by ID. | Specs, tests and code can't be matched up. |

## 3. Milestone 1 scope

**In M1 (Foundation)**, per the design doc milestone table and the kickoff tasks T01–T12:

- Monorepo, tooling, settings split, requirements split, `.env.example`, README for Windows.
- Postgres roles (`dial_owner`, `dial_app`, `dial_platform`), migration scripts, local Postgres or Neon.
- Core: base model, request IDs, JSON logging with phone masking, error envelope, cursor pagination, health endpoint, OpenAPI schema.
- Tenancy with all three isolation layers: `Business`, `BusinessDomain`, minimal `BusinessBranding` and `BusinessSetting`, host middleware, transaction + `set_config` middleware, `TenantModel`, `EnableTenantRLS`, `tenant_context()`, the contract test, the raw-SQL isolation test and a reusable cross-business test harness.
- Accounts: custom `User`, phone normalization, `PhoneOTP`, `Invitation`, `ConsentRecord`, auth endpoints for X-10 to X-14, throttles.
- Registered devices and PIN switching (X-15), owner list/sign-out of sessions.
- `AuditLog`, `OutboxEvent` + Celery dispatcher, `Notification`/`NotificationTemplate` (SMS only) with a console backend, the sign-in code and invitation templates, idempotency middleware, `GET /business/config`, `GET /app/version`.
- Uploads: presigned URLs to private R2, a local alternative, type/size limits.
- Frontend foundation: route areas, X-01 to X-04, X-10 to X-15, design tokens, i18n, generated client, shared state components, `lib/format.ts`, Vitest tests.
- `seed_dev` for `mamasafi` and `cleanpro`.
- GitHub Actions CI.
- Staging config written (`render.yaml`, `docs/ops/deploy.md`), not deployed.

**Not in M1** (explicitly):

- Catalogue, prices, modifiers, VAT, `pricing.py`, quote endpoint (M2).
- Customers, orders, the order state machine, order lines, photos attached to orders, condition notes, public order links, collection codes, practice mode (M3).
- Any payment: cash, recorded M-Pesa codes, Daraja/STK, C2B, ledger, cash-up, refunds, `BusinessPaymentConfig` and `FIELD_ENCRYPTION_KEY` usage, public order and pay pages C-60 to C-62 (M4).
- Console screens A-01 to A-67 and B-02/B-03, including the Team (A-41) and Devices (A-42) screens, reports, exports, content, audit log viewer (M5).
- Website W-01 to W-04, business self sign-up, setup checklist B-01, plans, plan limits, trial, subscription, invoices, SMS balance and top-ups, read-only/suspension enforcement, platform admin screens P-01 to P-12, admin 2FA (M6).
- Security checklist sign-off, backups, load test, production Daraja (M7).
- Customer app, rider app, riders, areas, slots, delivery jobs, dispatch (M9).
- Email (Resend), real SMS gateway, WhatsApp, branded Android builds, custom domains, eTIMS, printers.
- Any deployment, DNS change or real secret.

## 4. Ambiguities, contradictions and risks

### Missing inputs

1. ~~**Screen sub-tabs are missing.**~~ **Resolved 2026-10-01:** the owner pasted all five sub-tabs; they are now `docs/design/11-staff-app.md` to `15-platform-and-website.md`. The pasted design doc and shared Screens tab match the Word versions already converted. Findings from the sub-tabs are in §4a below.
2. **No Swahili text anywhere.** The docs give English wording only, but `sw` files are required and the rules forbid inventing wording. *(Question 6)*
3. **Many M1 strings have no given wording**: field validation messages, the X-01 "Can't connect" screen body, X-03 text, the password checklist, the invitation-expired and already-registered texts, PIN screen texts, error envelope messages. *(Question 6)*

### Contradictions

4. **`TenantModel` location vs dependency direction.** §6.1 puts `TenantModel` (with an FK to `Business`) in `apps.core`, and core also holds `OutboxEvent`, `IdempotencyKey`, `AuditLog`, which carry `business`; but §6.6 says `core ← tenancy`, i.e. core must not depend on tenancy. *Proposal:* core refers to the business model only by the string `"tenancy.Business"` (no Python import), and the contextvar and `tenant_context()` live in core. I'll record this in ADR-0001 unless you object.
5. **Nullable business on "tenant" tables.** `User.business` is empty for platform staff, and platform-level actions (P-12 audit log, platform billing outbox events) have no business, yet §6.1 says `TenantModel.business` is non-null. Also `UniqueConstraint(business, phone)` does not stop duplicates where `business` is NULL. *Proposal:* `User` and `AuditLog` get a nullable `business` with RLS (NULL rows are invisible to `dial_app`, visible to `dial_platform`), a partial unique constraint on `phone` for platform staff, and an explicit entry in the contract test's "nullable-tenant" list. Written up in ADR-0001/0002.
6. **Where staff PINs live.** The data model puts "staff PIN hashes" on `Device`, but the PIN is described as "a personal 4-digit PIN" that works on any registered device. **Largely settled by the sub-tabs:** X-15 lists "the staff … for this branch", S-30 has "Change PIN" and A-41 has "Reset PIN" per person, so the PIN belongs to the person. I'll store one PIN hash per user; the device records only registration, status and its own wrong-PIN lock. This reading goes into ADR-0002 for your approval.
7. **Stored SMS balance.** `Business` lists an "SMS balance" field, while `SmsTransaction` says "Balance is the sum; never edited" and `CLAUDE.md` says balances are never stored. I'll leave the field out of `Business` in M1 (SMS billing is M6).
8. **Trusted customer "within their limit".** `CLAUDE.md` §6.3 mentions a limit; the design doc and `Customer` table have only a yes/no trusted flag. Not M1 (M3/M4), recorded in `OPEN.md`.
9. **Customer status labels are from the old marketplace design.** `10-screens-shared.md` "Status labels" lists Requested, Assigned, Accepted ("Finding a shop", "Shop confirming"), which don't exist in the state machine, and has no labels for `booked` or `received`. Not M1; recorded in `OPEN.md`.
10. **"Logged on A-43".** The notification rules say failed SMS are logged on A-43, which is the Riders screen. Probably a renumbered screen. Not M1; recorded in `OPEN.md`.
11. **Payment status diagram gap.** `diagrams.md` has no `part_paid → pending` edge, so a customer who part-paid can't be sent a prompt for the rest. M4; recorded in `OPEN.md`.

### Gaps in scope that affect M1 acceptance

12. **The acceptance test needs screens scheduled for later.** "An owner can invite a staff member" needs A-41 (M5); "switch in by PIN on a registered device" needs S-02 Register this device (M3) and somewhere to set a PIN. The design doc's onboarding says invited staff get "an SMS to set a password and a PIN", but the X-14 flow (X-12 → X-13 → home) has no PIN step. *(Question 1)*
13. **`POST /auth/register` has no M1 user.** C-04 confirms it is customer sign-up (Growth, M9); owner sign-up is `POST /platform/signup` on W-03 (M6). The kickoff lists `register` in T05. *(Question 2)*
14. **Invitation creation isn't in T05's endpoint list** (only accept). A-41 settles who may invite: an invite has name, phone, role, branches and rights; managers can't manage owners; only an owner adds owners, with an SMS code. *(Question 7)*
15. **No table for uploads.** T08 returns "a photo record ID", but the 54-table model has only `OrderPhoto` (M3) and `RiderDocument` (M9). The sub-tabs confirm photos are uploaded before the record that uses them exists (S-14 sends "lines and photo IDs"; S-15, S-20, R-13, R-31 and C-30 all attach photos). *(Question 6)*
16. **Idempotency for anonymous POSTs.** Keys are stored "per business, user and key", but login, codes and password reset have no user. *Proposal:* required for authenticated app POSTs; optional on the anonymous auth endpoints, where the throttles already protect them. Goes in ADR-0002.
17. **Health check vs host resolution.** Render's health check won't use a business host, so `/api/v1/health` must be exempt from the unknown-host 404. I'll do that; noting it because it's an exception to §6.1.
18. **Plan limits.** Staff invitations would normally check the plan's staff limit (3 on Starter), but plans are M6. M1 won't enforce limits; recorded as `TODO(decision)`.

### Technical risks (handled in ADRs, listed so you know)

19. **JWT must be bound to the business.** A token issued on `mamasafi` must be rejected on `cleanpro`. The access and refresh tokens will carry `business_id`, checked against the host on every request.
20. **simplejwt's blacklist tables aren't tenant-scoped.** They'd be readable across businesses by `dial_app`. *Proposal:* our own tenant-scoped `UserSession`/refresh-token table (it also powers "list and sign out sessions"), using simplejwt only for signing and verifying. ADR-0002.
21. **Tests vs roles.** pytest-django creates and migrates the test database as the connecting user; if that's `dial_app`, it owns the tables. The test setup must migrate as `dial_owner` and run tests as `dial_app`. ADR-0001.
22. **Neon pooling with psycopg 3.** Transaction-mode pooling needs server-side cursors off and prepared statements disabled. ADR-0001.
23. **Vite proxy must keep the Host header** (`mamasafi.localhost`), or every API call in dev resolves to no business.
24. **Third-party models** (auth permissions, content types, admin log, Celery results if any) must be on the global allow-list in the contract test.
25. **Fonts.** Plus Jakarta Sans and Inter must be self-hosted; I'll commit the WOFF2 files (OFL licence) rather than add an npm font package, which would need approval.
26. **Admin 2FA** needs a dependency outside §4 (e.g. `django-otp`). M1 only writes the staging config for the admin service; 2FA is flagged for M6/M7.
27. **Local environment.** Python 3.12 is not installed on this machine (only 3.11), Docker is installed but not running, `psql` is not installed, and the folder is not yet a git repository. *(Questions 3, 4 and 10)*

## 4a. Findings from the screen sub-tabs (added 2026-10-01)

### What they settle for M1

- **X-15 Switch user:** shows the staff photos and names for this branch; tap a name, enter a 4-digit PIN; only on registered devices; 5-minute idle lock; 5 wrong PINs lock the device until a manager unlocks it; every later action is recorded against the person who switched in (`11-staff-app.md`).
- **S-02 Register this device:** manager or owner only; device name and branch; registering signs the manager out and leaves the device on the PIN screen (`11-staff-app.md`).
- **Sessions and devices (A-42):** the owner sees every signed-in session per person (device, browser, last active) and can sign it out; removing a device ends every PIN session on it at once; A-41 "Deactivate" signs a person out of every device. This supports a tenant-scoped session table of our own (§4 item 20).
- **Roles:** tenant roles are Owner, Manager, Accountant, Staff, Rider (plus customers); platform roles are Super admin, Support, Finance (P-11). The `User.role` field in M1 covers all of them.
- **Business web address rules (W-03):** a–z, 0–9 and hyphens; reserved words `www, admin, api, app, console, staff, rider` are refused. M1's `Business.slug` validation and `seed_dev` will follow this.
- **Branches are needed in M1.** Devices belong to a branch (S-02), X-15 lists staff "for this branch", invitations carry branches (A-41), and S-01 uses `GET /me/branches`. T06 allows a minimal `Branch` if the plan says why; this is why. *(Question 8)*

### New contradictions and gaps (none block M1 unless marked)

28. **Two API prefixes in the staff app.** S-13 to S-20 use `/shop/orders/...`; S-40 to S-44, the design doc and `CLAUDE.md` use `/staff/...`. I'll use `/staff/` everywhere (M3). The tab itself is titled "Shop app screens".
29. **Marketplace-era statuses appear in more places** (extends D-30): C-21's next-step table and C-28 use Requested, Assigned, Accepted, and R-18 says a failed pickup "returns the order to Accepted". The state machine has `booked` instead. M3/M9.
30. **Transitions the state machine doesn't have.** R-18: a failed delivery sends the order from `out_for_delivery` back to `ready`. A-50 and R-15: reversing a payment moves payment status from `paid` back to `unpaid`/`part_paid`. Neither is in `diagrams.md`. M4/M9.
31. **Trusted customers have a limit after all.** A-21 sets "Trusted with a maximum amount they may owe", matching `CLAUDE.md` §6.3, but the `Customer` table has no such field. The field will be added in M3 (resolves D-29 except for the field name and default).
32. **Wrong screen references.** C-03 says waitlist counts are on A-41 (Team); A-33 is where they appear. The notification rules' "logged on A-43" remains unexplained (D-31).
33. **Cash-up uniqueness.** S-50 says one per person per branch per day; the `CashUp` table says one per staff per day. M4.
34. **Rider pay rules.** A-43 has none, fixed amount per job, or a share of the delivery fee; the `RiderProfile` table has none or per job. M9.
35. **Two pending decisions named only in the screens:** whether the delivery fee is charged at booking (C-13), and the cancellation/redelivery fee decision (C-28, R-18). Added to `OPEN.md`.
36. **How a manager unlocks a device after 5 wrong PINs** isn't specified: A-42 has only Remove, and X-15 doesn't say. *(Question 9)*
37. **Staff photos on X-15.** No photo field exists on `User` and no screen uploads one. M1 will show initials; photos can come later.
38. **S-44 needs a QR code**, which likely means a frontend dependency outside `CLAUDE.md` §4. M3; I'll raise it then.
39. **X-14 role labels** are "Rider / Shop staff / Shop owner"; Manager and Accountant have no label yet. Covered by Question 5.

## 5. Questions for you, most important first

*Revised 2026-10-01 after the screen sub-tabs arrived. The old Q1 (missing specs) and Q8 (personal PIN) are answered by the specs.*

1. **Minimal screens for the M1 acceptance test.** The acceptance test needs invite, register-device and set-PIN. My recommendation:
   - build **S-02 Register this device** and **X-15 Switch user** fully in M1 (both are small, fully specified, and their APIs are M1 work);
   - add a **"Choose your 4-digit PIN" step after X-13 in the X-14 flow** for owner, manager and staff roles, as the design doc's onboarding describes ("an SMS to set a password and a PIN");
   - build a **minimal invite form** in `/console` (name, phone, role, branches, rights) now; the full A-41 Team screen follows in M5.

   Yes, or API-only?
2. **Drop `POST /auth/register` from M1?** C-04 shows it is customer sign-up (M9), and owners sign up through `POST /platform/signup` (M6). Owners in M1 come from `seed_dev` and a `create_business` management command.
3. **Development database:** Postgres 16 in Docker on this machine (my recommendation; you'd need to start Docker Desktop), or a Neon dev branch?
4. **Existing PyCharm project:** may I delete `dial_a_service/`, `templates/`, the root `manage.py` and the Python 3.11 `.venv` in T01? Will you install Python 3.12 (`winget install Python.Python.3.12`), or may I run it?
5. **Wording and Swahili:** may I draft the missing English wording (X-15 labels, PIN step, validation messages, "Can't connect", role labels for manager and accountant, and so on) in one file for your review, and fill the `sw` files with English marked `TODO(translation)` until a translation arrives?
6. **Uploads table:** may I add `core.Upload` (business, storage key, content type, size, status, uploaded by)? `/uploads` returns its ID, and `OrderPhoto`, condition notes, tickets and rider documents reference it later. That makes 55 tables.
7. **Invitations in M1:** owners and managers invite managers, accountants and staff; managers can't invite owners (A-41). Should owner-invites-owner, which needs an SMS code, be **in M1** (it reuses the M1 code machinery) or **wait for M5**? My recommendation is M5. Riders wait for M9.
8. **Minimal branches in M1:** `Branch` (name, status) and `BranchMember` (branch, user, role), pulled forward from M3/M5 because devices, X-15 and invitations all need a branch. The full branch fields (hours, capacity, Till) come in M5. OK?
9. **Unlocking a device after 5 wrong PINs:** my recommendation is that a manager or owner signs in on the locked device with phone and password, which unlocks it; an Unlock button on A-42 follows in M5. OK?
10. **GitHub:** is there a repository for CI yet? If not, I'll `git init` locally, and you create the remote when ready. I won't push without asking.
