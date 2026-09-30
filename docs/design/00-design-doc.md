> Converted from the Word export (Design doc.docx) on 2026-10-01. Diagrams are in `diagrams.md`; the pricing formula is kept as LaTeX.

## Dial A Service — Laundry Business Platform: Design Overview

Dial A Service is a laundry business system that businesses rent monthly. A laundry signs up, enters its prices, staff and existing M-Pesa Till or Paybill, and runs its counter, pickups, deliveries and payments from the same day. Dial A Service never looks for end customers and never touches order money: each business brings its own customers, and they pay straight into the business's own M-Pesa or in cash.

| A laundry's problem today | What the system does |
| --- | --- |
| Paper books, lost tickets, mixed-up bags | Every order gets a reference, a bag count at each handover, photos and a status |
| Arguments about weight and damage | Photo of the scale and notes on existing damage, sent to the customer before payment |
| Customers collecting without paying, or owing | Laundry is released only when paid; M-Pesa prompt to the customer's phone; automatic reminders |
| Counting cash and M-Pesa at closing | End-of-day cash-up per staff member, with expected against counted |
| No online booking or delivery | Booking page, customer app and rider app, switched on when the business wants them |
| Owner can't see the business from home | Live dashboard and reports in the business console |

Who uses it: the owner and managers (business console), counter and washing staff (staff app), the business's riders (rider app), the business's customers (SMS links, booking page, customer app), and your team (platform admin).

Locked decisions

| Decision | Choice | Source |
| --- | --- | --- |
| Product | Laundry business system rented monthly, white-labelled per business | Owner, 1 Oct 2026 |
| Marketplace | Dropped: no platform-owned customers and no commission. The multi-tenant design keeps it possible later | Owner, 1 Oct 2026 |
| Order money | Goes directly to each business (its M-Pesa Till or Paybill, or cash). The platform only collects subscription fees | Proposed, 1 Oct 2026 |
| Backend | Django + Django REST Framework, modular monolith | Brief |
| Frontend | React + TypeScript (Vite), one codebase building the staff, rider and customer apps and the business console | Owner, 30 Sep 2026 |
| Sign-in | Phone number + password, per business; SMS code only to verify the number and reset the password | Owner, 30 Sep 2026 |
| Weight evidence | Photo of the scale reading on every weighed order | Owner, 30 Sep 2026 |
| Release rule | Laundry leaves only when paid (on by default); the owner can let named trusted customers pay on collection | Owner, 30 Sep 2026; exception proposed |
| Delivery | Optional per business; riders are the business's own people using the rider app | Owner, 30 Sep 2026 |
| Payment timing | Business setting: at drop-off, after weighing (default), or at collection | Proposed, 1 Oct 2026 |
| Order channels | Walk-in at the counter (core), phone or WhatsApp orders entered by staff, online booking (plan feature) | Proposed, 1 Oct 2026 |
| Admin | Business console as a React app for business owners; Django admin for your platform team | Proposed, 1 Oct 2026 |

In the MVP: self-serve sign-up with a free trial; the business console (setup, prices, staff, riders, customers, orders, payments, reports, subscription); the staff app (counter orders, queue, weighing, ready, collection, cash-up); public order and payment pages opened from SMS, so customers need no app; online booking, customer app and rider app for plans that include delivery; platform admin.

Not in the MVP: branded Android apps per business, custom domains (subdomains only), corporate customers billed monthly, loyalty and promotions, automatic rider dispatch, WhatsApp messages, other service categories (the catalogue already supports them), receipt and tag printers.

All 137 screens are specified on the Screens tab and its sub-tabs: Staff app, Business console, Customer app, Rider app, and Platform and website.

### Business model

The platform earns a monthly subscription per business plus SMS top-ups, and nothing per order, so a business never feels taxed for growing. Plan prices are open decisions; the structure below is what the system enforces.

|  | Starter | Growth | Business |
| --- | --- | --- | --- |
| For | One counter shop | Shops that collect and deliver | Chains and larger laundries |
| Branches | 1 | Up to 3 | Unlimited |
| Staff accounts | 3 | 10 | Unlimited |
| Counter orders, weighing with photos, bag tags | Yes | Yes | Yes |
| M-Pesa (recorded codes or STK prompt) and cash | Yes | Yes | Yes |
| Public order and payment pages by SMS link | Yes | Yes | Yes |
| End-of-day cash-up and reports | Yes | Yes | Yes, plus branch comparison |
| SMS included per month | Small bundle | Larger bundle | Largest bundle |
| Online booking page and customer app | No | Yes | Yes |
| Riders, pickup and delivery | No | Yes | Yes |
| Custom domain, branded Android app | No | No | After the MVP |
| Monthly price | To set | To set | To set |

Rules the system enforces

- Trial: 14 days of Growth, free, with no payment details needed. Before it ends the owner picks a plan and pays by M-Pesa prompt.
- Billing: monthly in advance, paid by M-Pesa to the platform's own Paybill. Invoices are generated and texted automatically.
- Late payment: 7 days' grace with daily reminders, then read-only mode. In read-only mode staff can still finish, release and collect payment for existing orders, so the business's customers are never stranded, but no new orders can be created. After 60 days unpaid the account is suspended.
- Cancellation: data can be exported for 90 days, then it is deleted, with notice before deletion.
- Plan limits: checked when staff, branches or riders are added; exceeding one shows an upgrade prompt instead of an error.
- SMS: each business has an SMS balance. The plan's bundle is added monthly, and top-ups are bought by M-Pesa. When the balance runs out, sign-in codes still go out (a small negative balance is allowed), other messages pause, and the owner is warned in the console and by one SMS. All businesses share the platform's sender ID by default; their own sender ID is a paid add-on, because registration with the mobile networks takes weeks.
- Setup help: an optional paid onboarding session (prices entered, staff trained) for owners who don't want to do it themselves.

Growth for you depends on signing laundries, not on finding end customers: far fewer, larger customers, reached by visiting shops, through laundry and dry-cleaning associations, and through referrals (a free month for both sides when a business refers another).

### The ecosystem

Every business gets its own web address, such as mamasafi.dialaservice.co.ke, and every surface for that business lives under it. The address alone tells the system which business a request belongs to.

| Surface | Used by | For | Delivered as | Plans |
| --- | --- | --- | --- | --- |
| Business console | Owner, managers, accountant | Setup, prices, staff, riders, customers, orders, payments, reports, subscription | Web app at /console, desktop or tablet | All |
| Staff app | Counter and washing staff, branch managers | Counter orders, queue, weighing, ready, collection, cash-up | Web app at /staff, phone or counter tablet | All |
| Public order and pay pages | Any customer with an SMS link | See the order, weight and photos; pay; receipt; no account needed | Pages at /o/{token} | All |
| Customer booking app | The business's customers | Book pickups, track, pay, history | Installable web app at / | Growth and up |
| Rider app | The business's riders | Pickups and deliveries | Web app at /rider; Android build later | Growth and up |
| Platform admin | Your team | Businesses, plans, billing, support, platform health | Django admin on a separate host | — |
| Website and sign-up | Laundry owners | What it does, prices, start a free trial | dialaservice.co.ke | — |

system architecture · 8 parts

One Django service with one background worker serves every business. A modular monolith gives one deploy, one database transaction around every money movement, and clear app boundaries. It scales by adding web instances; the database is the eventual limit, handled first with a read replica for reports. Sentry collects errors from both the web service and the worker.

### Tenancy and isolation

Many businesses share one database from the first day, so keeping each business's data invisible to every other business is the most important property of the whole platform. It is enforced in three independent layers, so a bug in any one layer alone cannot leak data.

- Every request belongs to one business. Middleware looks up the request's host in BusinessDomain and stores the business in the request context. An unknown host gets a 404 before any view runs. Later mobile builds send a fixed X-Business key instead. The platform admin host has no business.
- Layer 1: application code. Every business-owned model inherits a TenantModel base with a required, indexed business column. Its default manager refuses to run without a business in context, so an unscoped query fails loudly instead of returning everyone's data. Serializers never accept business from the client; it is always set from the context.
- Layer 2: Postgres row-level security, from day one. Every tenant table has a policy allowing rows only where business_id matches a per-transaction setting (SET LOCAL app.business_id). The application connects as a database role that cannot bypass the policy; migrations use a separate owner role. Background tasks carry the business ID and set it before touching data.
- Layer 3: tests in CI. A check fails the build if any model outside an approved global list lacks the business column or its security policy. Every endpoint has a test proving a user of business A gets 404 on business B's records.
- Unique values are per business: phone numbers, order references, customer codes.
- Files are per business. Storage keys start with the business ID, and signed URLs are issued only after checking the business.
- Caches, rate limits and queues are keyed by business, so one busy business can't slow down or starve the others. Heavy exports and reports run in the worker.
- Accounts are per business. A person who uses two laundries has two separate accounts, exactly as with two unrelated shops.

Who owns the data. Each business is the data controller for its customers, staff and orders; Dial A Service processes that data on its behalf. The rental agreement says so. Owners can export everything (CSV) at any time, and data is deleted 90 days after cancellation, after a notice.

### Roles, permissions and sign-in

Permissions are fixed per role so they are easy to reason about. The owner adjusts only three sensitive rights per staff member.

| Role | Uses | Can | Cannot |
| --- | --- | --- | --- |
| Platform super admin | Platform admin | Everything across businesses; read-only "view as business", always audited | See any business's M-Pesa secrets (never shown to anyone) |
| Platform support | Platform admin | View a business's setup and orders read-only; resend invitations; reset an owner's password after verification | Change money, plans or data |
| Platform finance | Platform admin | Subscription invoices, payments, SMS top-ups, subscription refunds | See business orders or customers |
| Owner | Console, staff app | Everything in their business, including billing, M-Pesa setup, staff and data export | — |
| Manager | Console, staff app | Everything except billing, M-Pesa setup, deleting data and managing owners; can be limited to chosen branches | Billing, payment setup |
| Accountant | Console | Payments, refunds, cash-ups, reports, exports | Edit orders, prices or staff |
| Staff | Staff app | Counter orders, receiving, weighing, statuses, collection, taking M-Pesa payments. Three rights the owner switches per person: accept cash, give discounts, correct prices | Reports, settings, other branches |
| Rider | Rider app | Their own jobs | Anything else |
| Customer | Public pages, customer app | Their own orders, addresses, payments | — |

Sign-in

- Everyone signs in with phone number and password on the business's own address, which decides the business. A 6-digit SMS code verifies the number and resets passwords; staff and riders join through an SMS invitation.
- The API is served on the same address (/api/v1), so the refresh token sits in an httpOnly, Secure, same-site cookie and the access token (15 minutes) only in memory. The refresh token lasts 7 days and rotates on every use.
- Shared counter devices. A manager registers a counter tablet to a branch once. After that, staff switch users on it with a personal 4-digit PIN instead of a full sign-in, so every order and payment is recorded against the right person. The tablet locks after 5 idle minutes; 5 wrong PINs lock it until a manager unlocks it. PINs work only on registered devices and are stored hashed.
- Owners confirm sensitive changes (M-Pesa settings, adding an owner, data export) with an SMS code. Platform admin requires an authenticator app.
- The owner sees every signed-in device in the console and can sign any of them out.

### Order flows

Most laundry orders are walk-ins, so the counter is the centre of the design: a walk-in order is created, weighed and priced in one screen, and online bookings join the same flow once the bags reach the branch.

| Channel | Created by | Starts at | Plans |
| --- | --- | --- | --- |
| Walk-in at the counter | Staff (S-40) | Received | All |
| Phone or WhatsApp, customer brings the bags | Staff (S-40) | Received when the bags arrive | All |
| Phone or WhatsApp, pickup wanted | Staff (S-40 with pickup) | Booked | Growth and up |
| Online booking | Customer (C-11 to C-13) | Booked | Growth and up |

Each order is either collected at the counter or delivered (Growth and up). When the customer pays is a business setting: at drop-off, after weighing (default), or at collection. Whatever the setting, laundry is released only when paid, unless the owner has marked that customer as trusted to pay on collection.

order state machine · 7 states + cancelled, 2 ways in, 2 ways out

| State | Meaning | Entered by | Guard |
| --- | --- | --- | --- |
| Booked | Pickup booked | Customer or staff | Area covered, window free |
| Picked up | Rider has the bags | Rider | Bag count and photo recorded |
| Received | Bags at the branch | Staff (walk-ins start here) | Bag count confirmed |
| Processing | Weighed, priced, being washed | Staff | Every weighed line has a scale photo |
| Ready | Clean and packed | Staff | Outgoing bag count set |
| Out for delivery | With the delivery rider | Rider | Paid (or trusted customer) |
| Completed | Delivered or collected | Rider with the customer's delivery code, or staff at the counter with the collection code | Paid (or trusted customer) |
| Cancelled | Stopped | Customer before pickup; staff before weighing; manager at any point before completion | Reason required; refund raised if paid |

Collection at the counter. Every order gets a 4-digit collection code, sent in the receipt SMS. Staff release the laundry after the customer gives the code, or after finding the order by phone number and confirming the name. The release screen shows a large red "Not paid" and blocks release until payment is taken.

Uncollected laundry. Customers get reminders at 3, 7 and 14 days after Ready (a setting). After 30 days the order appears on the owner's "uncollected" report, for the business to follow its own policy.

Payment status runs alongside: Unpaid → Pending (M-Pesa prompt sent) → Part paid or Paid; then Refunded or Part refunded. Every status change locks the order row, checks these rules, and writes an OrderStatusEvent in the same transaction; anything else is refused with HTTP 409.

### Payments

There are two kinds of money, and they never mix. Order money belongs to each business and goes straight into its own M-Pesa or cash drawer; the platform only records it. Platform money is subscriptions and SMS top-ups, paid by businesses into your Paybill. Because the platform never holds a business's customers' money, it avoids the licensing question a marketplace would face.

#### Order money: three ways to pay

| Method | How it works | Confirmed by |
| --- | --- | --- |
| M-Pesa prompt | Staff or the public pay page sends an STK prompt to the customer's phone | Safaricom's callback to the platform, using the business's own Daraja keys |
| M-Pesa paid directly | Customer pays to the business's Till or Paybill; staff record the M-Pesa code, or a Paybill payment with the order reference as account number is matched automatically | Staff entry checked against the business's M-Pesa messages; automatic for a connected Paybill |
| Cash | Staff with the cash right record the amount | The staff member's end-of-day cash-up |

#### M-Pesa connection levels

A business can start on day one with only its existing Till or Paybill number and connect the automatic features when ready.

| Level | The business needs | What works |
| --- | --- | --- |
| Basic | Its existing Till or Paybill number | Customers pay to it; staff record the M-Pesa code; pages and SMS show "Pay to Till {number}" |
| Connected | Daraja API keys for that Till or Paybill (Safaricom go-live, guided on B-03) | M-Pesa prompts to the customer's phone, automatic confirmation, reminders with a pay link |
| Connected Paybill | The above, on a Paybill | Also automatic matching of manual payments by order reference |

At Basic level, a recorded M-Pesa code must match the Safaricom format and be unused in this business. Staff must see the payment on the business's own M-Pesa messages before recording it, because fake payment SMS are a known fraud. Owners can later upload their M-Pesa statement to reconcile recorded codes automatically.

M-Pesa prompt flow for a connected business · 4 parties

Connected payments follow the same safety rules as before: the amount always comes from the stored order total; callbacks are matched by CheckoutRequestID and ignored if already final; M-Pesa receipt numbers are unique per business; an attempt with no callback is checked with an STK status query; a failure returns the order to Unpaid so the customer can try again. Each business's callback URL carries its own token, and its Daraja secrets are stored encrypted.

#### The business's ledger

Every business has its own balanced ledger, so its reports always add up.

| Event | Debit | Credit |
| --- | --- | --- |
| Order priced | Customer receivables | Sales |
| Discount given | Discounts | Customer receivables |
| M-Pesa payment | M-Pesa received | Customer receivables |
| Cash payment | Cash drawer (that staff member) | Customer receivables |
| Refund | Refunds | M-Pesa received or cash drawer |
| Rider pay earned (if paid per job) | Rider costs | Rider payable (that rider) |
| Rider paid | Rider payable | M-Pesa received or cash drawer |

Cash-up. At closing each staff member's expected cash (the sum of their cash drawer entries that day) is shown against the amount they count. The difference is recorded with a note and approved by a manager.

Refunds are made by the business itself (M-Pesa reversal, sending money, or cash) and recorded in the system with the reference. Automated M-Pesa refunds come later.

#### Platform money

Subscription invoices and SMS top-ups are paid by M-Pesa prompt to the owner's phone, using your own Daraja Paybill, or manually to it with the invoice number as account. The callback marks the invoice paid and updates the plan or SMS balance at once.

### Pricing engine

Each business sets its own price list; the server computes every price in one module, and the apps only display what it returns.

\text{line} = \begin{cases} \max(\text{minimum},\ \text{kg} \times \text{rate}) \times (1 + \text{modifiers}) & \text{per kg} \\ \text{quantity} \times \text{price} \times (1 + \text{modifiers}) & \text{per item} \\ \text{price} & \text{flat} \end{cases} \qquad \text{total} = \operatorname{round}\Big(\textstyle\sum \text{lines} + \text{delivery fee} - \text{discount}\Big)

- Starting price list. A new business gets a template of common services (wash and fold, wash and iron, ironing only, duvets, blankets, suits, curtains, shoes) with the prices left blank for the owner to fill in, plus a CSV import for an existing list.
- Pricing models: per kg with a minimum charge, per item, or flat. One order can mix them.
- Modifiers: express service (a percentage or a flat amount) and chargeable preferences such as hypoallergenic detergent. Each is a setting per business.
- Discounts: only staff with the discount right, as a percentage or an amount, with a required reason, capped by a business-wide maximum. Every discount is audited and printed on the receipt.
- Delivery fee: per area, set by the business (Growth and up).
- Whole shillings: totals are rounded half-up to the shilling because M-Pesa accepts only whole amounts; the unrounded parts are kept.
- VAT: a business setting says whether prices include VAT and at what rate; receipts show the VAT line. Sending invoices to KRA's eTIMS is an integration for after the MVP.
- Estimate vs final: online bookings get an estimate range; the final price is set at weighing. Walk-ins are priced on the spot.
- Snapshots and versions: prices are versioned with an effective date, and every order keeps the exact prices it was charged, so later changes never alter past orders.

### Data model

54 tables in 12 Django apps. Every table except those marked Global carries a required business column protected by row-level security. Money is Decimal(12,2) plus a currency code; timestamps are UTC; primary keys exposed through the API are UUIDs.

| App | Table | Key fields | Rules |
| --- | --- | --- | --- |
| tenancy | Business | name, slug, status (trial, active, read-only, suspended, cancelled), country, currency, timezone, language, SMS balance | Global; slug unique |
| tenancy | BusinessDomain | business, host, is_primary | Global; host unique |
| tenancy | BusinessBranding | app name, logo, primary and accent colours, support phone, WhatsApp, legal links, SMS sender ID | One per business; colours pass the contrast check |
| tenancy | BusinessPaymentConfig | level (basic, connected), type (Till, Paybill), number, encrypted Daraja keys and passkey, environment, callback token, status | Secrets encrypted with a key from an environment variable; never returned by the API |
| tenancy | BusinessSetting | key, typed value (payment timing, cash allowed, reminders, limits, feature flags) | One row per key |
| tenancy | BusinessContent | type (FAQ, terms, privacy, care policy), language, version, body, published_at | Published versions never change |
| billing | Plan | name, monthly price, limits (branches, staff, riders), features, SMS bundle | Global |
| billing | Subscription | business, plan, status, current period, trial end, grace end | One active per business |
| billing | Invoice | business, number, period, amount, status, due date | Number unique; paid invoices never change |
| billing | BillingPayment | invoice, method, M-Pesa receipt, amount, paid_at | Receipt unique |
| billing | SmsTransaction | business, change (+/−), reason (bundle, top-up, usage, adjustment), reference | Balance is the sum; never edited |
| accounts | User | business (empty for platform staff), phone, password hash, names, role, language, is_phone_verified, status | Unique (business, phone) |
| accounts | Invitation | phone, role, branch, token hash, expires_at, accepted_at | 7-day expiry |
| accounts | PhoneOTP | phone, purpose, code hash, expires_at, attempts, used_at | Hashed codes |
| accounts | ConsentRecord | user or customer, document, version, accepted_at, IP | Append-only |
| accounts | Device | branch, name, registered_by, last_seen, status; staff PIN hashes | PIN switching only on registered devices |
| customers | Customer | phone, name, trusted to pay on collection, notes, marketing consent, linked user (if they created an account) | Unique (business, phone); walk-ins need no password |
| customers | Address | customer, label, area, estate, building, house number, landmark, directions, optional coordinates, is_default | One default per customer |
| catalog | ServiceCategory | name (EN/SW), is_active |  |
| catalog | Service | category, code, name (EN/SW), pricing model (per kg, per item, flat), unit, is_active | Code unique per business |
| catalog | ServicePrice | service, branch (optional override), unit price, minimum charge, effective_from, effective_to | No overlapping versions |
| catalog | PriceModifier | name, kind (express, preference), percent or amount, applies to |  |
| catalog | ServiceArea | name, town, delivery fee, branch serving it, is_active | Growth and up |
| catalog | SlotTemplate | area, weekday, start, end, capacity | No overlaps |
| catalog | WaitlistEntry | area text, phone, consent | One per phone and area |
| branches | Branch | name, location, phone, hours, daily capacity (kg), status | Plan limit on count |
| branches | BranchMember | branch, user, role | Unique per branch and user |
| riders | RiderProfile | user, vehicle, plate, areas, status, is_online, pay rule (none, per job) | Plan limit on count |
| riders | RiderDocument | rider, type, file, expiry, status, reviewed_by | Private storage |
| riders | DeliveryJob | order, rider, kind (pickup, delivery), status, deadlines, bag counts, photos, times, fail reason | One open job per order and kind |
| orders | Order | reference, branch, customer, channel, fulfilment (collect, deliver), status, payment_status, windows, address copies, preferences, instructions, subtotal, discount, delivery fee, VAT, total, collection code hash, delivery code hash, created_by | Reference unique per business; indexed on (business, branch, status) and (business, customer, created_at) |
| orders | OrderLine | order, service, source (declared, final), quantity, unit, unit price, modifiers, minimum applied, line total | Final lines required before pricing |
| orders | OrderPhoto | order, kind (scale, bags, handover, condition, issue), file, line, taken_by | Private storage, signed URLs |
| orders | ConditionNote | order, item, issue, photo, note, created_by | Editable until Ready |
| orders | OrderStatusEvent | order, from, to, actor, reason, created_at | Append-only |
| orders | OrderLink | order, token hash, purpose (view, pay), expires_at | Public page access; unguessable 128-bit token |
| orders | Review | order, rating, tags, comment | One per order |
| payments | Payment | order, method (M-Pesa prompt, M-Pesa recorded, Paybill matched, cash), amount, M-Pesa code, recorded_by, status | M-Pesa code unique per business |
| payments | PaymentAttempt | order, amount, phone, request IDs, status, result, receipt, raw callback | One pending per order |
| payments | C2BPayment | receipt, amount, payer name, phone, account text, matched order, status | Receipt unique per business |
| payments | CashUp | branch, staff, date, expected, counted, difference, note, approved_by | One per staff per day |
| payments | Refund | order, amount, method, reference, reason, recorded_by | Can't exceed amount paid |
| payments | RiderPayout | rider, period, amount, method, reference, created_by | Can't exceed rider payable |
| payments | LedgerAccount | code, owner (staff drawer, rider or none) | Unique per business |
| payments | LedgerTransaction | source, reference, created_at | Entries balance |
| payments | LedgerEntry | transaction, account, order, amount, debit or credit | Never updated or deleted |
| notifications | NotificationTemplate | event, channel, language, body | SMS bodies within 160 characters |
| notifications | Notification | recipient, event, channel, payload, status, attempts, cost, error | Outbox; charged to the SMS balance |
| support | SupportTicket | scope (customer to business, business to platform), order, opened_by, type, status, assignee, outcome |  |
| support | TicketMessage | ticket, author, body, photos, is_internal |  |
| core | OutboxEvent | type, payload, created_at, processed_at | Same transaction as its change |
| core | IdempotencyKey | user, key, endpoint, stored response | Kept 24 hours |
| core | AuditLog | actor, action, object, before/after, IP | Append-only |
| core | AppVersion | app, platform, minimum, latest | Global |

### API contract

One REST API at /api/v1 on each business's own address, documented with OpenAPI (drf-spectacular) at /api/schema/.

Conventions for every endpoint

- The business comes from the host, never from the request body.
- State changes are explicit action endpoints (POST .../weigh), never a generic "set status".
- Every app POST carries an Idempotency-Key; a repeat returns the first response.
- Accept-Language picks English or Swahili for messages.
- Lists use cursor pagination, 20 per page by default.
- Errors always look like {"code", "message", "fields", "request_id"}, and the message is safe to show to users.
- Orders are addressed by reference (MSF-7K3P9Q), other objects by UUID.
- Throttles are per business and per user; login, codes and payments have their own tighter limits.

| Group | Paths | Used by | Endpoints |
| --- | --- | --- | --- |
| Config | /business/config, /business/content, /app/version | Everyone | Branding, services, prices, areas, settings the apps need; FAQs and legal pages; app versions |
| Auth | /auth/... | Everyone | register, verify-phone, verify-phone/resend, login, refresh, logout, password-reset/request, password-reset/confirm, password/change, invitations/accept, pin-switch |
| Me | /me/... | Signed in | profile, phone change and confirm, delete, notification preferences, my branches |
| Public order links | /o/{token} | Anyone with the SMS link | view order, send M-Pesa prompt, payment status, receipt |
| Customer | /addresses, /quotes, /slots, /orders, /waitlist | Customers (Growth and up) | book, list, detail, cancel, pay, payment status, review, report a problem, share delivery code |
| Staff | /staff/... | Staff and managers | orders by stage and search; create walk-in or phone order; find or create customer; receive, weigh, reprice, condition notes, ready, release at counter, hand over, cancel, report; record cash or M-Pesa code, send prompt; today's cash-up; register device |
| Rider | /rider/... | Riders | jobs, accept, decline, start, arrived, collect, arrived-at-shop, complete, fail, availability, earnings, payouts, documents |
| Console | /console/... | Owner, manager, accountant | dashboard; orders and actions; customers (import, trusted flag, export); catalogue and prices (import); modifiers; areas and slots; branches; staff, invitations, devices; riders and dispatch board; payments and unmatched Paybill payments; refunds; cash-up approvals; rider payouts; reports and exports; settings; branding; M-Pesa setup and test; content; subscription, invoices, SMS top-up; audit log; full data export |
| Uploads | /uploads | Signed in | short-lived upload URL for a photo, returns a photo ID |
| Support | /support/tickets | Customers, businesses | tickets and messages |
| Notifications | /notifications | Signed in | list, unread count, read, read all |
| M-Pesa in (business) | /payments/mpesa/stk/{token}, /payments/mpesa/c2b/validation/{token}, /payments/mpesa/c2b/confirmation/{token} | Safaricom | prompt results and Paybill payments for that business |
| M-Pesa in (platform) | /billing/mpesa/stk/{token} on the platform host | Safaricom | subscription and SMS top-up payments |

Platform staff work in Django admin and need no public API.

### Onboarding: live in one day

A laundry can go from sign-up to its first real order in one working day, using only what it already has: an Android phone or tablet with a browser, mobile data, its existing M-Pesa Till or Paybill, whatever scale it owns, and pen-written bag tags. Nothing to install and no special hardware.

- Sign up on the website (W-03): business name, owner name, phone, password, chosen web address (mamasafi.dialaservice.co.ke). An SMS code confirms the phone and the 14-day trial starts; the console opens on the setup checklist (B-01).
- Branch: name, location, opening hours.
- Prices: fill in the template or import a CSV. This is the longest step, so it saves as you go.
- M-Pesa (Basic): type the existing Till or Paybill number. That's enough to take payments today.
- Staff: invite by phone number; each gets an SMS to set a password and a PIN.
- Counter device: open /staff on the counter phone or tablet, sign in as owner or manager, tap "Register this device".
- Customers (optional): import names and phones from a CSV. No messages are sent unless the owner chooses the "We've gone digital" announcement.
- Practice order: a guided walk-in order with a pretend customer, marked as practice and left out of reports and SMS.
- Go live: the checklist confirms everything needed and the first real order can be taken.

Later, when the business is ready: connect Daraja for M-Pesa prompts and automatic confirmation (guided on B-03, including Safaricom's go-live paperwork); switch on online booking and riders (Growth); get its own SMS sender ID.

What makes it easy

- Every step can be skipped and resumed.
- Defaults are the safe choice: pay after weighing, release only when paid, reminders on.
- Staff get a practice mode that never touches real data.
- A one-page guide in English and Swahili can be printed for the counter.
- A WhatsApp help button connects to your support.
- The platform admin shows how far each business got, so your team can call the ones stuck at a step.

### Security, privacy and compliance

Every item is built into the milestone it touches and ticked off before the first paying business goes live.

Isolation between businesses

- ☐ Host-based business resolution; unknown hosts rejected before any view runs
- ☐ TenantModel base and a manager that refuses unscoped queries
- ☐ Postgres row-level security on every tenant table; the app's database role cannot bypass it
- ☐ CI check that every non-global model has the business column and a policy
- ☐ Cross-business 404 test on every endpoint
- ☐ File keys, caches, rate limits and idempotency keys all scoped by business

Accounts and access

- ☐ Custom user model before the first migration; unique (business, phone)
- ☐ Refresh token in an httpOnly, Secure, same-site cookie; access token in memory; rotation on every use
- ☐ Throttles on login, codes, PIN entry and payments
- ☐ Staff PINs only on registered devices, hashed, locking after 5 wrong tries
- ☐ SMS code confirmation for an owner's sensitive changes; authenticator app for platform admin
- ☐ Owner can see and sign out every device

Money

- ☐ Order paid only by a Safaricom callback, status query, matched Paybill payment, or a staff-recorded code or cash, each tied to a named staff member
- ☐ M-Pesa codes unique per business; Safaricom code format validated
- ☐ Each business's Daraja secrets encrypted, never returned, changed only with SMS confirmation
- ☐ Callback URLs carry an unguessable per-business token; amounts checked against the order
- ☐ Ledger append-only; cash-ups approved by a manager

Public order links

- ☐ 128-bit random tokens, stored hashed, expiring 30 days after the order completes
- ☐ Pages show the customer's first name and the order, never the address or full phone number
- ☐ Rate limited per IP; no search or listing of orders from public pages

Platform hygiene

- ☐ Secrets only in environment variables; .env git-ignored from the first commit
- ☐ HTTPS everywhere with HSTS; strict Content Security Policy; same-origin API, so no CORS
- ☐ Logs never contain passwords, codes, tokens, PINs or M-Pesa secrets
- ☐ Audit log on every change to orders, money, staff, settings and payment setup
- ☐ Daily backups with point-in-time recovery; a restore tested before launch
- ☐ Dependency and container vulnerability scanning in CI

Privacy and law (check with a lawyer before launch)

- ☐ Dial A Service registered with Kenya's Office of the Data Protection Commissioner as a data processor; rental terms name each business as the data controller
- ☐ Privacy policy, retention periods and deletion 90 days after cancellation
- ☐ Owner can export all business data at any time
- ☐ Marketing SMS only with the customer's opt-in; transactional SMS only for real orders
- ☐ KRA eTIMS invoicing requirements reviewed for businesses that must issue tax invoices

### Future-proofing decisions

Each decision costs little now and avoids a rewrite later. Anything not listed is deliberately kept simple until real usage asks for more.

| Area | Decided now | What it makes possible later |
| --- | --- | --- |
| Tenancy | Business column plus row-level security on every business table from day one | Thousands of businesses on one system; a marketplace layered on top if ever wanted |
| Plans and features | Every paid feature checked through one features(business) function driven by the plan | New plans, add-ons and price changes without code changes |
| Customers separate from users | Walk-in customers need no login; an account links later | Customer apps, loyalty and corporate accounts on the same records |
| Service catalogue | Category → service → pricing model | Dry cleaning, shoe care, house cleaning, car wash |
| Order lines and modifiers | Price comes from lines with modifiers | Mixed orders, express service, per-customer price lists |
| Payment methods | One payment interface; Daraja prompt, recorded code, Paybill match and cash as adapters | Airtel Money, cards or a licensed aggregator |
| M-Pesa levels | Basic works with just a Till number; Connected adds automation | Businesses start immediately and upgrade without re-onboarding |
| Money and tax | Decimal plus currency on every amount; VAT fields on orders | Other countries; KRA eTIMS invoices |
| Language | Every string through translation keys; English and Swahili at launch | More languages without touching screens |
| Time and country | UTC storage; timezone, currency and phone rules per business | Uganda, Tanzania and beyond |
| Notifications | Outbox plus channel adapters; every message charged to the SMS balance | WhatsApp and push notifications |
| Domain events | Every status change and payment writes an outbox event | Webhooks for businesses, integrations, analytics |
| Files | Private S3-compatible storage keyed by business | Millions of photos at low cost |
| API | /api/v1, additive changes only, idempotency keys on every POST | Android apps on older versions keep working; a public API for Business-plan customers |
| Domains | Host-based resolution through a domain table | Custom domains per business |
| Frontend | One codebase, three apps plus console, built per business at run time from config | Branded Android builds per business with Capacitor |
| Devices | Registered counter devices with staff PINs | Receipt and tag printers attached to a device |
| Reporting | Reports from read-only queries on a replica | A data warehouse fed by the same events |

### Repository, environments and deployment

One monorepo; one frontend build serves every business, because branding and settings load at run time from /business/config.

dial-a-service/   backend/     config/settings/  base.py  local.py  test.py  production.py     config/  urls.py  wsgi.py  celery.py     apps/  core  tenancy  billing  accounts  customers  catalog            branches  riders  orders  payments  notifications  support     requirements/  base.txt  dev.txt  prod.txt     manage.py  pytest.ini  .env.example   frontend/     src/apps/  console  staff  rider  customer  public     src/  components  api (generated from OpenAPI)  i18n/en  i18n/sw  lib     package.json  vite.config.ts  tsconfig.json  .env.example   website/        marketing site and business sign-up (static)   docs/   .github/workflows/ci.yml   render.yaml   README.md

Hosting

| Piece | Where | Notes |
| --- | --- | --- |
| DNS, TLS, routing | Cloudflare for dialaservice.co.ke and *.dialaservice.co.ke | /api/* goes to Django; everything else to the frontend build; custom domains later through Cloudflare's custom hostnames |
| API and platform admin | Render web service (gunicorn) | Admin on admin.dialaservice.co.ke, also behind Cloudflare Access |
| Background worker and schedules | Render worker (Celery) plus scheduled jobs | Jobs listed below |
| Queue | Redis (Render Key Value or Upstash) | TLS connection |
| Database | Neon Postgres | Main branch for production, a staging branch, a branch per developer; point-in-time recovery |
| Frontend and website | Cloudflare Pages | Static builds |
| Files | Cloudflare R2 (S3-compatible) | Private bucket; no download fees |
| Errors | Sentry | Web, worker and frontend |

| Environment | Where | M-Pesa |
| --- | --- | --- |
| Local | Windows, PyCharm, Neon dev branch | Daraja sandbox through a tunnel (cloudflared) |
| Staging | Render + Neon staging, test businesses only | Daraja sandbox |
| Production | Render + Neon main | Each business's own Daraja keys; yours for billing |

| Variable | Purpose |
| --- | --- |
| DJANGO_SECRET_KEY, DJANGO_DEBUG | Django core; debug off outside local |
| PLATFORM_ROOT_DOMAIN, DJANGO_ALLOWED_HOSTS | dialaservice.co.ke and .dialaservice.co.ke |
| DATABASE_URL | App role, subject to row-level security |
| DATABASE_MIGRATION_URL | Owner role, used only for migrations |
| REDIS_URL | Celery broker (rediss:// where required) |
| FIELD_ENCRYPTION_KEY | Encrypts each business's Daraja secrets |
| STORAGE_ENDPOINT, STORAGE_BUCKET, STORAGE_ACCESS_KEY, STORAGE_SECRET_KEY | Private file storage |
| PLATFORM_MPESA_* | Your own Daraja keys, shortcode, passkey and callback token for subscriptions |
| MPESA_ENV | sandbox or production |
| SMS_API_KEY, SMS_USERNAME, SMS_SENDER_ID | SMS gateway and the shared sender ID |
| RESEND_API_KEY, DEFAULT_FROM_EMAIL | Invoice and owner emails |
| SENTRY_DSN | Error tracking |

Scheduled and background jobs: outbox dispatch; SMS sending with retries; STK status checks for pending attempts; payment and uncollected-laundry reminders; subscription invoices, reminders and the grace, read-only and suspension steps; monthly SMS bundle credit; report and data exports; document expiry reminders.

CI on every push: ruff and eslint, TypeScript check, pytest against a real Postgres (row-level security can't be tested on SQLite), an OpenAPI comparison that fails on breaking API changes, the tenant-isolation checks, and the frontend build.

### Build milestones

The counter product (Starter plan) is built first, because it's what every laundry needs and it can be sold before delivery exists. Each milestone ends in something that runs and is tested; the next starts only when its "done when" is true.

| # | Milestone | Delivers | Done when |
| --- | --- | --- | --- |
| 0 | Design sign-off | This doc and the screen tabs approved; blocking decisions answered | Owner approves |
| 1 | Foundation | Repo, settings split, tenancy with all three isolation layers, per-business accounts, auth, invitations, registered devices and PINs, audit log, outbox, idempotency, uploads, CI; staging on Render + Neon + Cloudflare wildcard domain | Two test businesses on their own subdomains; every isolation test passes; CI green |
| 2 | Catalogue and pricing | Services, versioned prices, modifiers, VAT, template list, CSV import, quote endpoint, business config endpoint | Pricing tests cover per kg, per item, minimums, modifiers, discounts, VAT, rounding and snapshots |
| 3 | Counter core | Staff app: customers, walk-in and phone orders, receive, weigh with photos, condition notes, ready, release with collection code, queue, search, practice mode | A walk-in order goes from drop-off to collection on a phone and a tablet |
| 4 | Payments and messages | Cash and recorded M-Pesa codes; Daraja prompts, callbacks, status checks, Paybill matching; the business ledger; cash-up; public order and pay pages; SMS catalogue and balance | Every payment path tested, including duplicate, missing and part payments; ledger balances; cash-up matches |
| 5 | Business console | Dashboard, orders, customers, catalogue, branches, staff, devices, settings, branding, M-Pesa setup, reports, exports, audit | An owner runs a full day from the console and every report ties back to the ledger |
| 6 | Platform and billing | Website sign-up, setup checklist, plans and limits, trial, invoices, subscription payment by M-Pesa, grace and read-only, SMS top-ups, platform admin | A new business signs up, sets up, pays and is invoiced with no help from your team |
| 7 | Launch readiness | Security checklist, backups and a tested restore, monitoring and alerts, load test, your Daraja production go-live for billing | Checklist ticked; load test at 10× the expected pilot volume passes |
| 8 | Starter pilot | 3–5 real laundries on the Starter plan | Pilot measures agreed with the owner are met |
| 9 | Delivery (Growth) | Booking app, areas and slots, rider app, delivery jobs, dispatch board, rider pay | A booked order is picked up, processed and delivered, including one step done offline |
| 10 | Growth pilot | Businesses using pickup and delivery | Pilot measures met |
| 11 | After the MVP | Branded Android apps, custom domains, eTIMS, corporate accounts, WhatsApp, printers | Specified when they start |

### Open decisions

Only the first one blocks Milestone 1. Plan prices are needed before Milestone 6; the rest can be settled during the build.

- ☒ Product model: rent the system to laundry businesses; no marketplace
- ☒ Weight evidence: scale photo on every weighed order
- ☒ Release rule: laundry leaves only when paid (with trusted-customer exception proposed)
- ☐ Approve this design and the screen tabs as the basis for Milestone 1
- ☐ Plan prices for Starter, Growth and Business, and whether there's an annual discount
- ☐ SMS bundle sizes per plan and the top-up price
- ☐ Paid setup help: offered or not, and its price
- ☐ Trial length: 14 days proposed
- ☐ Grace period: 7 days before read-only proposed
- ☐ Brand: product name for businesses, colours, logo and the domain (dialaservice.co.ke assumed)
- ☐ SMS gateway and shared sender ID: provider and registration
- ☐ Your Daraja Paybill for subscriptions (the account to register now, since go-live takes time)
- ☐ Rental agreement and privacy terms: drafted by a lawyer, including data processor role and ODPC registration
- ☐ First pilot laundries: 3–5 businesses willing to try Starter
- ☐ Rider pay tracking: confirm the optional per-job pay feature is wanted for Growth
