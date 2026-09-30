> Converted from the Word export (Screens.docx) on 2026-10-01. Diagrams are in `diagrams.md`; the pricing formula is kept as LaTeX.

## Screens: shared rules and inventory

### Surfaces and navigation

Each business gets the surfaces below under its own web address, built from one React codebase and branded from its settings. Every screen has a permanent ID used in tickets, analytics events, commits and tests; IDs are never reused.

| Surface | Used by | Main navigation | Address | Plans |
| --- | --- | --- | --- | --- |
| Staff app | Counter and washing staff, branch managers | Bottom tabs: New order, Queue, Search, More (cash-up, account) | /staff | All |
| Business console | Owner, managers, accountant | Left sidebar: Dashboard, Orders, Customers, Payments, Reports, Catalogue, Team, Riders, Settings, Subscription | /console | All (Riders on Growth) |
| Public order pages | Any customer with an SMS link | None: one page per order | /o/{token} | All |
| Customer app | The business's customers | Bottom tabs: Home, Orders, Account | / | Growth and up |
| Rider app | The business's riders | Bottom tabs: Jobs, Earnings, Account; online switch in the header | /rider | Growth and up |
| Platform admin | Your team | Django admin menu | admin.dialaservice.co.ke | — |
| Website | Laundry owners | Home, Pricing, Start free trial, Find my business | dialaservice.co.ke | — |

ID prefixes: X shared system and sign-in screens, S staff app, A business console, B console setup, C customer app and public order pages, R rider app, P platform admin, W website.

Navigation rules for all apps

- The main action on any screen is one full-width button fixed at the bottom, within thumb reach. There is never more than one primary button per screen.
- Every notification and SMS link opens a specific screen (for example /orders/DAS-7K3P9Q), not the home screen.
- The Android back button works everywhere and never exits a flow without asking when there is unsaved input.
- The booking flow keeps its draft on the phone for 24 hours if the customer leaves halfway.
- A customer can go from opening the app to a confirmed booking in 3 screens after the first time.

### Screen inventory

137 screens: 132 in the MVP (built across Milestones 1 to 9) and 5 after it. "Built in" names the milestone from the design doc. Detailed specs are in the sub-tabs; shared screens are specified below.

| ID | Screen | App | Purpose | Plans | Built in |
| --- | --- | --- | --- | --- | --- |
| X-01 | Splash | All | Load business config and branding, check app version | All | M1 |
| X-02 | Update required | All | Block a broken app version | All | M1 |
| X-03 | Maintenance | All | Planned downtime | All | M1 |
| X-04 | Not found | All | Missing or not-yours records | All | M1 |
| X-10 | Log in | All | Phone + password | All | M1 |
| X-11 | Forgot password | All | Request reset code | All | M1 |
| X-12 | Enter code | All | 6-digit SMS code | All | M1 |
| X-13 | Set new password | All | New password | All | M1 |
| X-14 | Accept invitation | Staff, console, rider | First sign-in for invited people | All | M1 |
| X-15 | Switch user | Staff app | PIN switch on a registered counter device | All | M1 |
| W-01 | Home | Website | What the system does for a laundry | — | M6 |
| W-02 | Pricing | Website | Plans and what each includes | — | M6 |
| W-03 | Start free trial | Website | Create a business and its owner | — | M6 |
| W-04 | Find my business | Website | Owner or staff who forgot their business address | — | M6 |
| B-01 | Setup checklist | Console | Guided setup to the first order | All | M6 |
| B-02 | Branding | Console | Name, logo, colours, address | All | M5 |
| B-03 | M-Pesa connection | Console | Till or Paybill, Basic or Connected | All | M5 |
| A-01 | Dashboard | Console | Today and the chosen period at a glance | All | M5 |
| A-10 | Orders | Console | All orders with filters | All | M5 |
| A-11 | Order detail | Console | Full record and manager actions | All | M5 |
| A-20 | Customers | Console | Customer list | All | M5 |
| A-21 | Customer detail | Console | History, balance, trusted flag | All | M5 |
| A-22 | Import customers | Console | CSV import | All | M5 |
| A-30 | Catalogue and prices | Console | Services, prices, modifiers | All | M5 |
| A-31 | Import prices | Console | CSV import | All | M5 |
| A-33 | Areas and pickup times | Console | Delivery areas, fees, slots | Growth | M9 |
| A-40 | Branches | Console | Branch details, hours, capacity | All | M5 |
| A-41 | Team | Console | Staff, roles, rights, invitations | All | M5 |
| A-42 | Devices | Console | Registered counter devices and sessions | All | M5 |
| A-43 | Riders | Console | Rider records and verification | Growth | M9 |
| A-44 | Dispatch board | Console | Assign pickups and deliveries | Growth | M9 |
| A-50 | Payments | Console | Every payment by method | All | M5 |
| A-51 | Unmatched Paybill payments | Console | Payments needing a match | All | M5 |
| A-52 | Refunds | Console | Record refunds | All | M5 |
| A-53 | Cash-ups | Console | Review and approve cash-ups | All | M5 |
| A-54 | Rider pay | Console | Rider balances and payouts | Growth | M9 |
| A-60 | Reports | Console | Sales, orders, unpaid, uncollected, staff | All | M5 |
| A-61 | Settings | Console | Payment timing, cash, reminders, VAT, limits | All | M5 |
| A-62 | Content | Console | FAQs, terms, privacy, care policy | All | M5 |
| A-63 | Audit log | Console | Who did what | All | M5 |
| A-64 | Data export | Console | Download all business data | All | M5 |
| A-66 | Customer problems | Console | Tickets from customers | All | M5 |
| A-67 | Help | Console | Guides and contact platform support | All | M5 |
| A-70 | Subscription | Console | Plan, trial, upgrade | All | M6 |
| A-71 | Invoices | Console | Invoices and payment | All | M6 |
| A-72 | SMS balance | Console | Balance, usage, top-up | All | M6 |
| S-01 | Choose branch | Staff app | Pick a branch | All | M3 |
| S-02 | Register this device | Staff app | Make a counter device shared | All | M3 |
| S-10 | Queue | Staff app | Orders by stage | All | M3 |
| S-11 | Order detail | Staff app | One order and its next action | All | M3 |
| S-12 | Cancel order | Staff app | Stop an order with a reason | All | M3 |
| S-13 | Receive bags | Staff app | From a rider, or a returned delivery | All | M3 |
| S-14 | Weigh and price | Staff app | Weights, items, scale photos, price | All | M3 |
| S-15 | Condition notes | Staff app | Record existing damage | All | M3 |
| S-16 | Correct price | Staff app | Fix price before payment | All | M3 |
| S-17 | Mark ready | Staff app | Washing finished | All | M3 |
| S-18 | Hand over to rider | Staff app | Release a paid delivery | Growth | M9 |
| S-19 | Search | Staff app | Find an order or customer | All | M3 |
| S-20 | Report a problem | Staff app | Raise an issue | All | M3 |
| S-30 | Account | Staff app | Profile, PIN, sign out | All | M3 |
| S-40 | New order | Staff app | Walk-in or phone order | All | M3 |
| S-41 | Find or add customer | Staff app | Pick or create the customer | All | M3 |
| S-42 | Take payment | Staff app | M-Pesa prompt, recorded code or cash | All | M4 |
| S-43 | Release at counter | Staff app | Hand laundry to the customer | All | M3 |
| S-44 | Receipt and tags | Staff app | Send receipt, show tag number | All | M3 |
| S-50 | My cash-up | Staff app | Count the drawer at closing | All | M4 |
| S-51 | Branch today | Staff app | Manager's view of the day | All | M4 |
| C-01 | Welcome | Customer app | First-run introduction | Growth | M9 |
| C-02 | Check your area | Customer app | Coverage check | Growth | M9 |
| C-03 | Join waitlist | Customer app | Uncovered area | Growth | M9 |
| C-04 | Sign up | Customer app | Create account | Growth | M9 |
| C-05 | Verify phone | Customer app | Confirm number | Growth | M9 |
| C-10 | Home | Customer app | Active orders and booking | Growth | M9 |
| C-11 | Book 1: What needs washing | Customer app | Services and estimate | Growth | M9 |
| C-12 | Book 2: Pickup and delivery | Customer app | Address and slot | Growth | M9 |
| C-13 | Book 3: Review and confirm | Customer app | Final check | Growth | M9 |
| C-14 | Booking confirmed | Customer app | Reference and next steps | Growth | M9 |
| C-20 | Orders | Customer app | Active and past orders | Growth | M9 |
| C-21 | Order detail | Customer app | Tracking and actions | Growth | M9 |
| C-22 | Your laundry was weighed | Customer app | Weight, photo, price | Growth | M9 |
| C-23 | Pay | Customer app | Start payment | Growth | M9 |
| C-24 | Waiting for M-Pesa | Customer app | Prompt progress | Growth | M9 |
| C-25 | Pay to Till or Paybill | Customer app | Manual payment instructions | Growth | M9 |
| C-26 | Receipt | Customer app | Proof of payment | Growth | M9 |
| C-27 | Delivery code | Customer app | Code for the rider | Growth | M9 |
| C-28 | Cancel order | Customer app | Cancel before pickup | Growth | M9 |
| C-30 | Report a problem | Customer app | Weight, missing, damaged, other | Growth | M9 |
| C-31 | Rate your order | Customer app | Stars and comment | Growth | M9 |
| C-32 | Notifications | Customer app | Messages | Growth | M9 |
| C-33 | Help | Customer app | FAQs, WhatsApp, tickets | Growth | M9 |
| C-34 | Ticket | Customer app | One conversation | Growth | M9 |
| C-40 to C-49 | Account screens | Customer app | Profile, phone, addresses, language, notifications, password, delete, terms | Growth | M9 |
| C-60 | Order page | Public | Status, weight, photos, price from an SMS link | All | M4 |
| C-61 | Pay page | Public | Pay from the link without an account | All | M4 |
| C-62 | Receipt page | Public | Proof of payment and collection code | All | M4 |
| R-01 | Not active yet | Rider app | Pending or suspended | Growth | M9 |
| R-10 | Jobs | Rider app | Current and upcoming jobs | Growth | M9 |
| R-11 | New job | Rider app | Accept or decline | Growth | M9 |
| R-12 to R-14 | Pickup steps | Rider app | Go, collect bags, drop at branch | Growth | M9 |
| R-15 to R-17 | Delivery steps | Rider app | Collect, go, enter code | Growth | M9 |
| R-18 | Could not complete | Rider app | Failed job | Growth | M9 |
| R-19 | Waiting to sync | Rider app | Offline queue | Growth | M9 |
| R-20 to R-22 | Earnings, payouts, history | Rider app | Pay and past jobs | Growth | M9 |
| R-30, R-31 | Account, documents | Rider app | Profile and verification | Growth | M9 |
| P-01 | Businesses | Platform | Every tenant | — | M6 |
| P-02 | Business detail | Platform | Status, plan, usage, setup progress | — | M6 |
| P-03 | Onboarding funnel | Platform | Where new businesses get stuck | — | M6 |
| P-04 | Plans | Platform | Plan prices, limits, features | — | M6 |
| P-05 | Invoices and subscriptions | Platform | Billing across businesses | — | M6 |
| P-06 | Billing payments | Platform | Subscription payments and matching | — | M6 |
| P-07 | SMS | Platform | Usage, gateway health, sender IDs | — | M6 |
| P-08 | Support tickets | Platform | Help requests from businesses | — | M6 |
| P-09 | Platform health | Platform | Errors, queues, payment success | — | M7 |
| P-10 | Announcements | Platform | Message all or some businesses | — | M6 |
| P-11 | Staff and roles | Platform | Your team | — | M6 |
| P-12 | Audit log | Platform | Platform-level actions | — | M6 |
| A-80 | Branded Android app | Console | Request and manage a branded build | Business | Later |
| A-81 | Custom domain | Console | Use the business's own domain | Business | Later |
| C-50 | Laundry plans | Customer app | Customer subscriptions | Growth | Later |
| C-51 | Refer a friend | Customer app | Referral code | Growth | Later |
| R-40 | Multi-job route | Rider app | Several jobs in one trip | Growth | Later |

### Design system

All apps share one design system. A business can change only its brand tokens (colours, logo, name), so every white-labelled app still looks professional and status colours always mean the same thing.

Colour tokens (defaults are a proposal for Dial A Service, to be confirmed in brand work)

| Token | Default | Per business | Used for |
| --- | --- | --- | --- |
| brand-primary | #0F6B5C (deep green) | Yes | Primary buttons, active tab, links, focus ring |
| brand-on-primary | #FFFFFF | Derived | Text on primary; computed for contrast |
| brand-accent | #F2A900 (amber) | Yes | Highlights and badges, never errors |
| surface | #FFFFFF | No | Screens and cards |
| surface-muted | #F4F6F5 | No | Page background, grouped sections |
| text | #1B1F1D | No | Main text |
| text-muted | #5B635F | No | Secondary text, hints |
| border | #DCE1DE | No | Inputs, dividers, card outlines |
| success | #1E7F4F | No | Paid, delivered |
| warning | #A86400 | No | Payment due, attention |
| danger | #C23B30 | No | Errors, destructive actions |
| info | #2458B3 | No | Neutral status, tips |

A business's colours are checked on save; if the primary colour fails WCAG AA contrast against white text, the console refuses it. Dark mode is out of the MVP; the tokens allow it later.

Type, spacing and shape

- Fonts: Plus Jakarta Sans for headings, Inter for body. Both self-hosted, so the Android build works offline and there is no Google Fonts dependency. Money and weights use tabular figures so columns line up.
- Type scale (px / line height): 28/34 page title, 22/28 section title, 18/24 card title, 16/24 body, 14/20 secondary, 12/16 caption. Inputs are at least 16 px so phones don't zoom in.
- Spacing on a 4 px scale: 4, 8, 12, 16, 24, 32, 48. Screen side padding is 16.
- Corners: 8 for buttons and inputs, 12 for cards and sheets, fully round for chips.
- Depth: borders instead of shadows; one shadow level only for bottom sheets and the sticky action bar.
- Icons: Lucide (MIT licence), one set only, 24 px, 1.75 stroke. No stock illustrations in the MVP; empty states use an icon and a sentence.
- Motion: 150–250 ms, only for sheets opening, a timeline step completing, button press feedback and the payment success tick. Turned off when the phone asks for reduced motion.

Components (built once in the shared UI kit, each with loading, disabled and error variants)

Button (primary, secondary, text, danger), text input, phone input with fixed +254 prefix, password input with show/hide, number input with unit suffix (kg), text area, 6-box code input, 4-digit keypad, select as bottom sheet, quantity stepper, date chips, time-slot grid, segmented control, status badge, order card, job card, timeline, money row (label left, amount right), bottom sheet, confirm dialog, toast, banner (info, warning, error, offline), skeletons per card type, empty state, camera capture, photo viewer with zoom, open-in-maps button, call button, star rating, tab bar, app bar, list row, section header.

Status labels customers see (internal names stay in the code and admin)

| Internal status | Customer label | Badge colour |
| --- | --- | --- |
| Requested | Finding a shop | info |
| Assigned | Shop confirming | info |
| Accepted | Pickup scheduled | info |
| Picked up | Picked up | info |
| Processing | Being washed | info |
| Ready | Ready | success |
| Out for delivery | On the way | brand-primary |
| Completed | Delivered | success |
| Cancelled | Cancelled | text-muted |
| Payment: Unpaid (after weighing) | Payment due | warning |
| Payment: Pending | Waiting for M-Pesa | warning |
| Payment: Paid | Paid | success |
| Payment: Refunded | Refunded | text-muted |

Every badge has an icon and text as well as colour, so it reads without colour.

What a business can brand: logo (SVG, or PNG at least 512 px), app name, primary and accent colours, support phone and WhatsApp number, links to its terms and privacy pages, SMS sender ID. Everything else is fixed.

### Shared states and shared screens

Every screen handles the same states the same way, so the specs in the sub-tabs only mention a state when it differs from this table.

| State | When | What the user sees |
| --- | --- | --- |
| First load | Data not yet on the phone | Nothing for 200 ms, then skeletons shaped like the real content; no full-screen spinners |
| Refreshing | Pull to refresh, returning to a screen | Old data stays visible; a thin progress bar at the top |
| Submitting | A button action is in flight | Spinner inside the button, button disabled; a retry reuses the same idempotency key so nothing is done twice |
| Empty | No items yet | One short sentence and one action (for example, "No orders yet" + Book a pickup) |
| Field error | Validation fails | Message under the field in plain words; focus moves to the first bad field; input is never cleared |
| Server error | 5xx or unexpected response | Banner: what happened, a Retry button and a short support reference (the request ID) |
| Offline | No connection | Top banner. Customer and shop apps show cached data read-only with actions disabled and a reason; the rider app queues actions (R-19) |
| Session expired | Access token expired | Silent refresh; if that fails, Log in (X-10) and return to the same screen with any draft kept |
| Not found or not yours | Wrong ID or someone else's record | X-04, identical for both cases so nobody learns what exists |
| Too many attempts | Throttled | "Too many attempts. Try again in N minutes." with a countdown |
| Update required | App below minimum version | X-02, blocks the app |
| Maintenance | Planned downtime flag on | X-03 with the expected return time |

X-01 Splash. Business logo on the brand colour. Calls GET /business/config and GET /app/version in parallel. Uses the last cached config if offline. After 8 seconds without a response it shows "Can't connect" with Retry. Goes to X-02 if the version is too old, otherwise to the app's home or first-run screen.

X-02 Update required. Message "This version needs an update to keep working" and one button: reload (web) or open the Play Store (Android). No way past it.

X-03 Maintenance. Message with the expected return time from config; checks again every 60 seconds and continues on its own.

X-04 Not found. "We couldn't find that" and a button back to home. Used for 403 and 404 alike.

X-10 Log in

- Shows: business logo, phone input (+254 prefix; accepts 07…, 01…, 7… and 1…), password input with show/hide, Log in button, Forgot password link. Customer app adds "New here? Create an account"; rider and shop apps add "Got an invitation? Set up your account".
- Rules: the error is always "Phone number or password is incorrect" and never says which. Log in is disabled until both fields are filled. A suspended account sees "Your account is suspended. Contact {business support}" after a correct password.
- API: POST /auth/login. Success goes to the page the user was trying to reach, or home.

X-11 Forgot password

- Shows: phone input, Send code button.
- Rules: always answers "If this number has an account, we've sent a code", whether or not it exists. Limited to 3 codes per phone per hour.
- API: POST /auth/password-reset/request, then X-12.

X-12 Enter code

- Shows: "Enter the 6-digit code sent to 0712 345 678", six boxes, Resend code with a 60-second countdown, "Wrong number? Change it".
- Rules: typing moves to the next box; pasting fills all six; Android Chrome fills it automatically (WebOTP). The code is submitted as soon as the sixth digit is entered. After 3 wrong tries it shows how many attempts are left; after 5 the code is dead and a new one is needed. Codes expire after 10 minutes.
- API: the verify endpoint of whichever flow opened it.

X-13 Set new password

- Shows: new password, confirm password, a live checklist (at least 8 characters, not only numbers, not a common password), Save button.
- Rules: after a reset, every other session is signed out. Success signs the user in and goes home.
- API: POST /auth/password-reset/confirm or POST /auth/invitations/accept.

X-14 Accept invitation

- Reached from: the invitation SMS link, or "Got an invitation?" on X-10.
- Shows: "{Business} invited you to join as {Rider / Shop staff / Shop owner}", the invited phone number (read-only), Send code button.
- Rules: invitations expire after 7 days; an expired one shows "Ask {business} to send a new invitation". A phone number already registered in this business is refused.
- Flow: X-12, then X-13, then the app's home (riders not yet verified land on R-01).

### Content, accessibility and performance rules

| Item | Format on screen | Stored as |
| --- | --- | --- |
| Money | KSh 1,250 (whole shillings everywhere a customer pays) | Decimal amount + currency code |
| Weight | 6.4 kg (one decimal) | Decimal kg, 2 places |
| Date | Thu 2 Oct; adds the year only if not this year | UTC timestamp |
| Time window | 10am–12pm | Start and end timestamps |
| Recent time | "5 min ago" up to one hour, then the time | UTC timestamp |
| Phone number | 0712 345 678 | +254712345678 |
| Order reference | DAS-7K3P9Q: business prefix + 6 characters, no 0/O/1/I | Unique per business |
| Other people's names | First name + surname initial ("Wanjiru K.") for riders and shops | Full name |

Writing. Plain, short and friendly; "you" and "we". Buttons say what they do ("Send M-Pesa prompt", not "Submit"). Every error says what to do next. No internal words customers wouldn't use (no "tenant", "STK", "payload").

Language. English first, Swahili second. Every string lives in translation files keyed by screen ID (for example C-23.button.send_prompt), never in code or images. Layouts must survive Swahili text being around 30% longer.

Accessibility (WCAG 2.1 AA)

- Tap targets at least 44 × 44 px, with 8 px between them.
- Every input has a visible label, not just a placeholder.
- Icon-only buttons have screen-reader labels.
- A visible focus ring on every interactive element.
- Nothing relies on colour alone.
- Layouts still work with the phone's text size at 200%.

Performance on a mid-range Android over 3G

- First screen usable within 3 seconds.
- Under 200 KB of gzipped JavaScript per app at first load; other screens load when opened.
- Photos are resized on the phone before upload (longest side 1600 px, about 300 KB) and uploaded in the background with a progress indicator.
- Lists load 20 items per page.

Privacy on screen

- Staff see their business's customers' names and phone numbers; lists show masked numbers, the order and customer screens show them in full, and every full view of a customer record is logged.
- Riders see a customer's first name, surname initial, address and phone only while that job is active.
- Public order pages show the customer's first name and the order, never the address or the full phone number.
- Customers see the rider's first name, photo, vehicle plate and phone only during an active pickup or delivery.

### Notification catalogue

SMS is sent only when the person must act or would otherwise worry; everything else is in-app. Each template exists per business and per language, stays within 160 characters so it costs one SMS, and opens the right screen through its link.

| Event | To | Channel | English text (placeholders in braces) | Opens |
| --- | --- | --- | --- | --- |
| Phone code | Anyone | SMS | {code} is your {business} code. It expires in 10 minutes. Never share it. | X-12 |
| Invitation | Staff, rider, manager | SMS | {business} invited you to join as {role}. Set up your account: {link} | X-14 |
| Order received (walk-in or at branch) | Customer | SMS | {business}: we received {bags} bags, order {ref}. Collection code {code}. Track: {link} | C-60 |
| Booking received | Customer | SMS | {business}: pickup booked for {slot}, order {ref}. Track: {link} | C-60 or C-21 |
| New booking | Branch staff | In-app | New pickup {ref}, {slot}, {area}. | S-11 |
| New job | Rider | In-app + SMS | New {pickup/delivery} job {ref}, {area}, {slot}. Open the Rider app to accept. | R-11 |
| Rider on the way (pickup) | Customer | SMS | {rider} ({plate}) is on the way to collect order {ref}. | C-60 |
| Weighed and priced | Customer | SMS | Order {ref}: {kg} kg, KSh {total}. See photo and pay: {link} | C-60 |
| Payment received | Customer | SMS | KSh {amount} received for {ref}. Receipt: {link} | C-62 |
| Payment failed | Customer | Page and in-app | Payment for {ref} didn't go through: {reason}. | C-61 |
| Ready for collection | Customer | SMS | Order {ref} is ready at {branch}. {Pay KSh {total}: {link} \| Collection code {code}} | C-60 |
| Ready (delivery, paid) | Customer | In-app | Order {ref} is ready. A rider will bring it soon. | C-21 |
| Out for delivery | Customer | SMS | {rider} is bringing order {ref}. Delivery code: {code}. Share it only when you have your bags. | C-60 |
| Completed | Customer | SMS | Order {ref} complete. Thank you for choosing {business}! Rate us: {link} | C-60 |
| Payment reminder | Customer | SMS | Reminder: order {ref} is ready. Pay KSh {total}: {link} | C-61 |
| Uncollected reminder | Customer | SMS | Your laundry {ref} is waiting at {branch}. Opening hours: {hours}. | C-60 |
| Cancelled | Customer | SMS | Order {ref} was cancelled: {reason}. {refund_note} | C-60 |
| Refund recorded | Customer | SMS | KSh {amount} refunded for order {ref}. Ref {reference}. | C-60 |
| Support reply | Customer | In-app; SMS if unread after 1 hour | {business} replied about order {ref}. | C-34 |
| Rider paid | Rider | SMS | {business} paid you KSh {amount} for {period}. Ref {reference}. | R-21 |
| Trial ending | Owner | SMS + email | Your Dial A Service trial ends on {date}. Choose a plan to keep going: {link} | A-70 |
| Invoice issued | Owner | SMS + email | Invoice {number}: KSh {amount} due {date}. Pay: {link} | A-71 |
| Payment overdue | Owner | SMS + email, daily in grace | Invoice {number} is overdue. Your account becomes read-only on {date}. Pay: {link} | A-71 |
| SMS balance low | Owner | Console + SMS | Your SMS balance is low ({count} left). Top up: {link} | A-72 |

Rules

- Codes, payment, delivery code and cancellation messages can't be turned off. Optional messages (reminders, ratings) can be, on C-46.
- Marketing messages need separate opt-in and are out of the MVP.
- Reminders are not sent between 9pm and 7am.
- A failed SMS is retried 3 times over 15 minutes, then logged on A-43. A failed message never blocks an order.
