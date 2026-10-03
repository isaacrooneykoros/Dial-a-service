# Open decisions

Decisions that are still pending. Never invent an answer to anything on this list. When code needs one of these to proceed, it uses a safe default in settings, marked `# TODO(decision): <topic>`, and the entry below says so.

When a decision is made, move it to "Decided" with the date and who decided, and write an ADR if it changes the design.

## From the design doc ("Open decisions")

| # | Decision | Needed by | Status |
| --- | --- | --- | --- |
| D-01 | Approve the design doc and the screen tabs as the basis for Milestone 1 | M1 (blocking) | Open |
| D-02 | Plan prices for Starter, Growth and Business, and whether there's an annual discount | M6 | Open |
| D-03 | SMS bundle sizes per plan and the top-up price | M6 | Open |
| D-04 | Paid setup help: offered or not, and its price | M6 | Open |
| D-05 | Trial length (14 days proposed) | M6 | Open |
| D-06 | Grace period before read-only (7 days proposed) | M6 | Open |
| D-07 | Brand: product name for businesses, colours, logo, and the domain (`dialaservice.co.ke` assumed) | M1 for defaults, final before M7 | Open; M1 uses the proposed tokens and domain |
| D-08 | SMS gateway and shared sender ID: provider and registration | M4 | Open; M1 uses the console backend only |
| D-09 | Platform Daraja Paybill for subscriptions (register now, go-live takes time) | M6 | Open |
| D-10 | Rental agreement and privacy terms, drafted by a lawyer (data processor role, ODPC registration) | M6/M7 | Open |
| D-11 | First pilot laundries: 3–5 businesses willing to try Starter | M8 | Open |
| D-12 | Rider pay tracking: confirm the optional per-job pay feature is wanted for Growth | M9 | Open |

## Locked decisions still marked "Proposed" in the design doc

| # | Decision | Proposed choice | Needed by |
| --- | --- | --- | --- |
| D-13 | Order money goes directly to each business; the platform only collects subscription fees | As proposed | M4 |
| D-14 | Payment timing as a business setting: at drop-off, after weighing (default), or at collection | As proposed | M3 |
| D-15 | Order channels: walk-in, phone/WhatsApp entered by staff, online booking as a plan feature | As proposed | M3 |
| D-16 | Admin: React business console for owners; Django admin for the platform team | As proposed | M5/M6 |
| D-17 | Release rule exception: owner can mark named customers as trusted to pay on collection | As proposed | M3 |

## Raised in Phase A (see `docs/UNDERSTANDING.md` §4 and §5)

| # | Decision | Needed by | Status |
| --- | --- | --- | --- |
| D-28 | Plan limits (staff, branches, riders) are not enforced until plans exist | M6 | Open; M1 enforces none, marked `TODO(decision): plan-limits` |
| D-29 | Trusted customer limit: A-21 confirms a maximum amount owed; field name and default still to set on `Customer` | M3 | Partly answered by A-21 |
| D-30 | Customer-facing status labels and flows use old marketplace states (Requested, Assigned, Accepted) in `10-screens-shared.md`, C-21, C-28 and R-18; the state machine has `booked`, and `received` has no label | M3 | Open |
| D-31 | Screen for failed SMS: notification rules say "logged on A-43", which is the Riders screen | M4 | Open |
| D-32 | Payment status: prompt for the remaining amount after a part payment (`part_paid → pending` is not in the diagram) | M4 | Open |
| D-33 | `Business` "SMS balance" field vs "balance is the sum of `SmsTransaction`" | M6 | Open; M1 stores no balance |
| D-34 | Where the three per-person staff rights (accept cash, give discounts, correct prices) are stored | M3 | Open |
| D-35 | Authenticator-app 2FA for platform admin needs a dependency outside the approved list | M6 | Open |
| D-38 | Staff app API prefix: `/shop/` (S-13 to S-20) vs `/staff/` (everywhere else); plan is `/staff/` | M3 | Open |
| D-39 | Missing transitions: `out_for_delivery → ready` after a failed delivery (R-18); payment reversal `paid → unpaid/part_paid` (A-50, R-15) | M4/M9 | Open |
| D-40 | C-03 says waitlist counts are on A-41; they're on A-33 | M9 | Open (likely a typo) |
| D-41 | Cash-up uniqueness: per person per branch per day (S-50) vs per staff per day (`CashUp` table) | M4 | Open |
| D-42 | Rider pay rules: none / fixed per job / share of delivery fee (A-43) vs none / per job (`RiderProfile`) | M9 | Open |
| D-43 | Delivery fee charged at booking or not (C-13 "Pending decision") | M9 | Open |
| D-44 | Cancellation and redelivery fees (C-28, R-18 "open cancellation decision") | M9 | Open |
| D-45 | Staff profile photos for X-15 (no field or upload screen); M1 shows initials | M3 | Open |
| D-46 | QR code on S-44 likely needs a frontend dependency outside `CLAUDE.md` §4 | M3 | Open |
| D-50 | `BranchMember.role`: the data model lists a role per branch membership, but nothing says how it differs from the person's own role (`User.role`). M1 leaves it out; adding it later is additive | M5 | Open |
| D-51 | X-12 automatic code fill on Android (WebOTP) only works if the code SMS ends with a line like `@mamasafi.dialaservice.co.ke #123456`. The catalogue text is used word for word, so that line isn't added. X-12 is ready for it and offers the code through the keyboard (`autocomplete=one-time-code`) meanwhile | M1 (T09e) | Open |

## Decided

| # | Decision | Date | By |
| --- | --- | --- | --- |
| D-18 | Screen sub-tab specs supplied; saved as `docs/design/11` to `15` | 2026-10-01 | Owner |
| D-25 | Staff PIN is personal (one per user), per X-15, S-30 and A-41; to be confirmed in ADR-0002 | 2026-10-01 | Screen specs |
| D-19 | M1 builds S-02 and X-15 in full, a PIN step after X-14, and a minimal console invite form | 2026-10-01 | Owner |
| D-20 | `POST /auth/register` and `verify-phone` are not built in M1 (customer sign-up, M9) | 2026-10-01 | Owner |
| D-21 | Development database is a Neon dev branch; CI uses a Postgres 16 service container | 2026-10-01 | Owner |
| D-22 | Delete the PyCharm scaffold and 3.11 venv; install Python 3.12 with winget | 2026-10-01 | Claude (delegated by owner) |
| D-23 | No wording review file; Claude writes missing English wording in the house style; `sw` files stay empty with English fallback until translations are wanted | 2026-10-01 | Owner |
| D-24 | Add `core.Upload` (table 55) | 2026-10-01 | Owner |
| D-26 | Owners inviting owners waits for M5 (with SMS confirmation); riders for M9 | 2026-10-01 | Owner |
| D-27 | No GitHub repo yet; `git init` locally now, create the remote with the owner in T11 | 2026-10-01 | Owner |
| D-36 | Minimal `Branch` and `BranchMember` in M1 | 2026-10-01 | Owner |
| D-37 | A manager or owner unlocks a locked device by signing in on it; A-42 Unlock in M5 | 2026-10-01 | Owner |
| D-47 | App dependency order changed to `core ← tenancy ← branches ← accounts ← …` to break the Device/Invitation ↔ BranchMember cycle (changes `CLAUDE.md` §6.6) | 2026-10-01 | Owner (approved with ADRs and M1 plan) |
| D-48 | Starting throttle rates (ADR-0002 §9) and upload limits (JPEG/PNG/WebP, 5 MB; M1 plan T08) | 2026-10-01 | Owner (approved with ADRs and M1 plan) |
| D-49 | Added auth endpoints not in the design doc list: `password-reset/verify`, invitation `send-code`/`verify`, `/me/pin`, `/devices/current` | 2026-10-01 | Owner (approved with ADRs and M1 plan) |
