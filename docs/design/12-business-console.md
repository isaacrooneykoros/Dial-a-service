# Business console screens (A-, B-)

> Screens sub-tab "Business console", pasted by the owner on 2026-10-01. Tables were rebuilt from the pasted text; wording is unchanged.

## Navigation, roles and layout

The console is where an owner sets up, watches and fixes the business from anywhere. It is built for a laptop or tablet and remains usable on a phone for quick checks.

**Sidebar:** Dashboard · Orders · Customers · Payments (Payments, Unmatched, Refunds, Cash-ups, Rider pay) · Reports · Catalogue (Services and prices, Areas and pickup times) · Team (Staff, Devices, Riders, Dispatch) · Settings (Business settings, Branding, M-Pesa, Content, Audit log, Data export) · Subscription (Plan, Invoices, SMS) · Help.

**Top bar:** branch selector (All branches or one), search by order reference or customer phone, notifications, account menu.

| Area | Owner | Manager | Accountant |
| --- | --- | --- | --- |
| Dashboard, orders, customers | Yes | Yes (their branches) | Read |
| Order corrections and cancellations after weighing | Yes | Yes | No |
| Payments, refunds, cash-ups | Yes | Yes | Yes |
| Reports and exports | Yes | Yes (their branches) | Yes |
| Catalogue, prices, areas | Yes | Yes | No |
| Team, devices, riders | Yes | Yes, except owners | No |
| Settings, branding, content | Yes | Yes, except payment settings | No |
| M-Pesa connection | Yes | No | No |
| Subscription, invoices, SMS top-up | Yes | No | Read and pay |
| Audit log | Yes | Read | Read |
| Full data export | Yes | No | No |

**Rules for every console screen**

- Every change is audited with before and after values. Money actions ask for a reason.
- M-Pesa changes, adding an owner and full data export need an SMS code sent to the owner.
- A banner shows the setup checklist until it is complete, and the subscription state when trial is ending, payment is overdue or the account is read-only.
- Customer phone numbers are masked in lists; revealing one is logged.
- Tables can be filtered, sorted and exported to CSV; exports over 5,000 rows are prepared in the background and offered as a download.

## Setup

### B-01 Setup checklist

- **Purpose:** get a new business from sign-up to its first real order without help.
- **Shows:** a progress bar and one row per step, each with its status (Not started, In progress, Done, Skipped) and a Continue button: Branch details (A-40) · Prices (A-30 or A-31) · M-Pesa (B-03) · Staff (A-41) · Counter device (S-02 on the counter device) · Customers, optional (A-22) · Practice order (opens the staff app in practice mode) · Go live. On the side: "Chat with us on WhatsApp" and "Book a setup session" (paid setup, if offered).
- **Rules:** each step completes itself when its data exists (for example, Prices is done once at least one service has a price). Go live is enabled when Branch, Prices, M-Pesa and at least one person who can take orders are done. After going live the checklist collapses into a "Setup complete" card that can be reopened.
- **API:** `GET /console/setup`.

### B-02 Branding

- **Shows:** business name as customers see it; logo upload (SVG, or PNG at least 512 px); primary and accent colours with a live contrast check; a live preview of the order page (C-60) on a phone mock-up and of the receipt SMS; web address (chosen at sign-up; can be changed once, with the old address redirecting for 90 days); receipt footer text (for example "Items left over 30 days are donated"); support phone and WhatsApp number; terms, privacy and care policy (edit on A-62).
- **Rules:** a colour that fails contrast with white text is refused, with a suggestion of the nearest passing shade.
- **API:** `GET /console/branding`, `PATCH /console/branding`.

### B-03 M-Pesa connection

- **Purpose:** take M-Pesa today with what the business already has, and add automation when ready.
- **Shows, step 1 (Basic):** Till or Paybill; the number; optionally a different Till per branch. Saving is enough to take payments by recorded M-Pesa code.
- **Shows, step 2 (Connect, optional):** what Connected adds (prompts to the customer's phone, automatic confirmation, pay links in reminders); a step-by-step guide to Safaricom's Daraja portal with screenshots (create an app, request go-live, find the consumer key, secret and passkey); fields for those values; Test (sends a KSh 1 prompt to the owner's phone); for a Paybill, Register payment URLs; status Connected or Failed with the reason in plain words; the time of the last callback received; Disconnect.
- **Rules:** owner only; changes need an SMS code. Secrets are shown only while typing and then as ••••; they are never sent back to the browser. If callbacks stop arriving for 24 hours while prompts are being sent, the owner is alerted and the dashboard shows it.
- **API:** `GET /console/payment-config`, `PUT /console/payment-config`, `POST /console/payment-config/test`, `POST /console/payment-config/register-urls`.

## Dashboard and orders

### A-01 Dashboard

- **Purpose:** in ten seconds, tell the owner how the business is doing and what needs them.
- **Shows:**
  - Date range (Today, 7 days, 30 days, Custom) and the branch selector.
  - Needs attention, each opening a filtered list: ready but unpaid (count, value, oldest); uncollected for more than 7 days; cash-ups waiting for approval; open customer problems; unmatched Paybill payments; M-Pesa connection problems; low SMS balance; pickups without a rider (Growth).
  - Numbers: orders received and completed; sales; money collected; money owed to the business; average order value; kg processed; average turnaround (received to ready); returning customers as a share of all customers; new customers.
  - Charts: sales per day (bars); money collected per day split by method (stacked bars); orders by branch (bars); orders by hour of day (bars), to plan staffing.
- **Rules:** money figures come from the ledger and match the reports exactly; days follow the business's timezone. Refreshes every 60 seconds while open.
- **API:** `GET /console/dashboard?from={d}&to={d}&branch={id}`.

### A-10 Orders

- **Columns:** reference, date, branch, customer, channel, fulfilment, status, payment status, total, balance, time in current status.
- **Filters:** branch, status, payment status, channel, fulfilment, date range, created by, has a problem, trusted customer, overdue (past turnaround).
- **Search:** reference, customer name or phone, M-Pesa code.
- **Actions:** Export CSV.

### A-11 Order detail

- **Shows:** everything on S-11, plus: every payment with who recorded it and from which device; ledger entries; messages sent and their delivery status; the order's audit trail; photos at full size.
- **Manager actions, each with a reason:** correct the price (before payment, as on S-16; after payment it creates an extra charge or a refund); cancel at any point before completion (the refund is recorded first); release to a trusted customer unpaid; move to another branch; resend any message; add an internal note.
- **API:** `GET /console/orders/{ref}` and action endpoints under it.

## Customers, catalogue and prices

### A-20 Customers

- **Columns:** name, masked phone, orders, total spent, amount owed, last order, Trusted.
- **Filters:** owes money, not seen for 30/60/90 days, trusted, has an app account.
- **Actions:** Add customer, Import (A-22), Export CSV.

### A-21 Customer detail

- **Shows:** name, phone (reveal is logged), notes, marketing consent, addresses, orders, payments, balance owed, problems raised.
- **Actions:** edit; set Trusted with a maximum amount they may owe (owner or manager); merge two records of the same person (orders move to the kept record); anonymise on the customer's request.
- **Rules:** a trusted customer can take laundry unpaid only while their total owed stays under their maximum.

### A-22 Import customers

- **Flow:** download the CSV template (name, phone, notes) → upload → preview showing rows to add, rows to update and rows with errors (invalid phone, duplicate in file) → Import.
- **Optional:** send the "We've gone digital" SMS to imported customers, with the SMS cost shown before confirming.

### A-30 Catalogue and prices

- **Shows:** categories and services; for each: name in English and Swahili, pricing model (per kg, per item, flat), current price and minimum charge, active switch, and position in the staff app's quick-add buttons (drag to reorder). Modifiers: Express and chargeable preferences, as a percentage or an amount. Branch price overrides. A calculator ("price for 6.4 kg of wash and fold, express").
- **Rules:** changing a price creates a new version starting now or at a chosen future time; past versions are read-only. Services used by past orders can be switched off but never deleted.
- **API:** `/console/catalog/...`.

### A-31 Import prices

- **Flow:** CSV template (service, category, pricing model, price, minimum) → preview with changes highlighted → Apply as a new price version from a chosen time.

### A-33 Areas and pickup times (Growth)

- **Shows:** delivery areas with name, town, delivery fee and serving branch; pickup windows per weekday with the number of orders each can take; same-day cut-off; waitlist entries from the booking app counted by area.
- **Rules:** switching an area off stops new bookings there and never affects existing orders.

## Branches, team, devices and riders

### A-40 Branches

- **Shows per branch:** name, address and landmark, phone, opening hours per weekday, closed dates, daily capacity in kg, turnaround target in hours, and its own Till or Paybill if it uses a different one (set on B-03).
- **Rules:** the number of branches is limited by the plan; adding one past the limit offers an upgrade. A branch with orders can be closed but never deleted.

### A-41 Team

- **Shows:** people with role (Owner, Manager, Accountant, Staff), branches, the three rights for staff (accept cash, give discounts, correct prices), last active, and status; pending invitations with Resend and Cancel.
- **Actions:** Invite (name, phone, role, branches, rights) sends the invitation SMS; change role, branches or rights; Reset PIN; Deactivate (signs the person out of every device at once).
- **Rules:** the plan limits staff accounts. Only an owner can add or remove owners, confirmed with an SMS code. The last owner can't be removed.

### A-42 Devices

- **Shows:** registered counter devices (name, branch, registered by, last used) with Remove; and every signed-in session per person (device, browser, last active) with Sign out.
- **Rules:** removing a device ends every PIN session on it immediately.

### A-43 Riders (Growth)

- **Shows:** riders with status (Invited, Pending checks, Active, Suspended), areas, vehicle and plate, document checks (each approved or rejected with a reason), pay rule (none, fixed amount per job, or a share of the delivery fee), acceptance and completion rates.
- **Actions:** invite, approve, suspend with reason, change pay rule, reset password.

### A-44 Dispatch board (Growth)

- **Shows:** three columns: pickups needing a rider (by window), paid deliveries needing a rider, jobs in progress. Beside them, riders online with their current job count and areas.
- **Actions:** Assign (one click on a suggested rider in the area); Reassign; see a job's history.
- **Rules:** a job not accepted before its deadline is highlighted and can be reassigned. The server refuses a second assignment of the same job, so two managers can't double-assign. Automatic dispatch can later be switched on as a feature flag.

## Payments, refunds, cash-ups and rider pay

### A-50 Payments

- **Columns:** time, order, customer, method (M-Pesa prompt, M-Pesa code, Paybill matched, cash), amount, M-Pesa code or receipt, recorded by, device, branch, status.
- **Totals:** by method for the chosen period and branch.
- **Actions:** Export CSV; Reverse a payment (owner or manager, with a reason; for example a recorded code later found not to exist on the business's M-Pesa). A reversal writes reversing ledger entries and puts the balance back on the order.
- **Later:** upload the M-Pesa statement to reconcile recorded codes automatically.

### A-51 Unmatched Paybill payments (Connected Paybill)

- **Shows:** payments whose account number matched no order, and payments that were more or less than the order total: time, amount, payer name as sent by M-Pesa, phone, account text, receipt.
- **Actions:** Match to an order (search by reference or phone; shows due against paid; writes the ledger entries and texts the customer's receipt); Mark for refund (goes to A-52).
- **Rules:** a payment can be matched once; every match is audited.

### A-52 Refunds

- **Record a refund:** order, amount (no more than paid minus earlier refunds), method (M-Pesa send money, M-Pesa reversal, cash), reference, reason.
- **Rules:** owner, manager or accountant only. Recording writes ledger entries and sends the customer the refund SMS. The platform never moves the money itself in the MVP.

### A-53 Cash-ups

- **Shows:** by day, branch and person: expected, counted, difference, status (Submitted, Approved, Queried); a trend per person of shortages and overages over the last 30 days.
- **Actions:** Approve; Query with a note (goes back to S-50).

### A-54 Rider pay (Growth)

- **Shows:** each rider's balance owed from their pay rule, jobs in the period, and payout history.
- **Actions:** Record payout (amount up to the balance, method, reference); the rider gets the payout SMS.
- **Rules:** shown only for riders with a pay rule; businesses paying riders a salary can leave it off.

## Reports, settings, content, audit and export

### A-60 Reports

Every report has a date range, a branch filter, a chart and a table, and exports to CSV or PDF.

| Report | Answers |
| --- | --- |
| Sales | Sales by day, branch and service; discounts and cancellations |
| Money collected | Payments by method, staff member and branch |
| Money owed | Who owes what and for how long (0–7, 8–30, over 30 days) |
| Uncollected laundry | Ready orders not collected, by age |
| Turnaround | Hours from received to ready, by branch and service, against the target |
| Staff activity | Orders created and weighed, cash handled, discounts given, price corrections, cash-up differences |
| Customers | New and returning customers; top customers by spend |
| VAT | Sales and VAT per period, for businesses registered for VAT |
| Riders (Growth) | Jobs, failures by reason, pay |

### A-61 Settings

| Group | Settings |
| --- | --- |
| Orders | When customers pay (drop-off, after weighing, collection); pay later allowed; part payments allowed; turnaround target; collection code required; uncollected reminder days |
| Money | Cash accepted; maximum discount %; VAT registered, rate, prices include VAT |
| Messages | Which optional SMS are sent; reminder schedule; quiet hours (default 9pm–7am) |
| Delivery (Growth) | Online booking on or off; riders on or off; rider accept deadline; wait before "customer not home" |

- **Rules:** every change is audited; changes apply to new orders only.

### A-62 Content

- **Shows:** FAQs, terms, privacy policy and care policy in English and Swahili, starting from editable templates, each with a version and publish date.
- **Rules:** published versions never change; publishing a new terms or privacy version makes customers accept it at their next visit.

### A-63 Audit log

- **Shows:** who did what and when, from which device, with before and after values; filters by person, action, object and date. Read-only for everyone.

### A-64 Data export

- **Flow:** choose everything or chosen parts (customers, orders, payments, ledger, photos) → SMS code to the owner → prepared in the background → download link valid for 24 hours, sent to the owner by SMS and email.
- **Rules:** owner only; every export is logged.

### A-66 Customer problems

- **Shows:** a queue of problems raised by customers (C-30) and staff (S-20): type, order, customer, status, age.
- **Actions:** reply (reaches the customer in-app or by SMS); assign to a person; internal note; resolve with an outcome (refund on A-52, price corrected, rewash, compensation, no action) and a note the customer sees.

### A-67 Help

- **Shows:** searchable guides with screenshots in English and Swahili; system status; Contact Dial A Service (opens a ticket to your team, P-08) and WhatsApp support.

## Subscription, invoices and SMS

### A-70 Subscription

- **Shows:** current plan and status (Trial with days left, Active, Overdue, Read-only); usage against limits (branches, staff, riders, SMS this month); plans side by side with what each adds; Upgrade or Change plan; Cancel subscription.
- **Rules:** an upgrade applies at once and the price difference is added to the next invoice; a downgrade applies at the end of the period and only if usage fits the smaller plan (otherwise it lists what to remove). Cancelling asks for a reason, reminds the owner to export data (A-64), and states the 90-day deletion date.
- **API:** `GET /console/billing/subscription`, `POST /console/billing/change-plan`, `POST /console/billing/cancel`.

### A-71 Invoices

- **Shows:** invoices (number, period, amount, status, due date); Pay now, which sends an M-Pesa prompt to the owner's phone or shows the platform Paybill with the invoice number as account; Download PDF.
- **Rules:** a paid invoice updates the plan status within seconds of Safaricom's confirmation. Paying an overdue invoice lifts read-only mode at once.
- **API:** `GET /console/billing/invoices`, `POST /console/billing/invoices/{number}/pay`.

### A-72 SMS balance

- **Shows:** balance; this month's usage by message type (receipts, ready alerts, reminders, codes); top-up packs with prices; Top up (M-Pesa prompt); the low-balance warning level; request for the business's own sender ID (a paid add-on) with its status.
- **Rules:** the plan's bundle is added on each billing date and doesn't carry over; top-ups do carry over. When the balance reaches zero, only sign-in codes still go out.
- **API:** `GET /console/billing/sms`, `POST /console/billing/sms/top-up`.

## After the MVP

A-80 Branded Android app (request a build with the business's name and icon) and A-81 Custom domain (connect the business's own domain) are specified when their milestone starts.
