# Rider app screens (R-)

> Screens sub-tab "Rider app", pasted by the owner on 2026-10-01. Tables were rebuilt from the pasted text; wording is unchanged.

## Navigation and activation

The rider app is built for one hand, bright sunlight and weak network. It shows one job at a time with one large button for the next step, and every action still works offline.

- **Tabs:** Jobs, Earnings, Account. The header carries the Online/Offline switch on every tab.
- **Getting in:** admin creates the rider on A-43 → invitation SMS → X-14 → X-12 → X-13 → R-01 until verified → R-10.
- **Sizing:** primary buttons 56 px tall; addresses in 18 px text; high-contrast colours for outdoor use.
- **Permissions:** camera is asked for at the first photo; location only when the rider taps Arrived, to record where it happened. There is no live tracking in the MVP.

| Job kind | Steps the rider goes through |
| --- | --- |
| Pickup | New → Accepted → On the way → Arrived → Collected (bag count + photo) → At shop → Handed over (shop confirms) |
| Delivery | New → Accepted → At shop → Collected from shop (paid orders only) → On the way → Arrived → Delivered (customer's code) |

### R-01 Not active yet

- **Shows** one of two states. Pending verification: "We're checking your documents. We'll text you when you're approved", with Documents → R-31. Suspended: the reason category and a Call support button.
- **Actions:** Log out.
- **API:** `GET /me` (rider status).

## Jobs and pickups

### R-10 Jobs

- **Shows:**
  - Online switch with its meaning ("You're online. You can receive jobs").
  - Now: the job in progress as a large card with its current step and one Continue button.
  - New: assigned jobs waiting for an answer, each with a countdown to its accept deadline.
  - Upcoming: accepted jobs not started, sorted by window.
  - Each card: Pickup or Delivery badge, window, area and estate, bag count (deliveries), reference, and a sync icon if actions are still queued.
  - Banner linking to R-19 when anything is waiting to sync.
- **Rules:** going offline is blocked while a job is in progress ("Finish your current job first"). While online and open, the list refreshes every 20 seconds; a new job plays a sound and vibrates (Android build).
- **Empty:** online: "No jobs right now. Stay online and we'll send one." Offline: "You're offline. Go online to get jobs."
- **API:** `GET /rider/jobs`, `POST /rider/availability`.

### R-11 New job

- **Shows:** job kind; window; area and estate only (the exact address and customer name appear after accepting); bag count for deliveries; the amount the rider earns for this job (riders on a per-job pay rule only); countdown to the accept deadline.
- **Actions:** Accept (primary) → the job moves to Upcoming or Now; Decline → reason (Too far, Busy, Vehicle problem, Other).
- **Rules:** an unanswered job expires at the deadline (a business setting, default 5 minutes) and returns to the admin queue. Declines and expiries count towards the acceptance rate shown on R-30.
- **API:** `POST /rider/jobs/{id}/accept`, `POST /rider/jobs/{id}/decline`.

### R-12 Pickup: go to customer

- **Shows:** step bar (Go → Collect → Drop at shop); customer first name and surname initial, or the handover person if the customer named one; full address (estate, building, house number, landmark, rider directions); window; Open in maps (saved coordinates or the address text, opened in the phone's own maps app at no API cost); Call.
- **Actions:** Start trip (sends the customer "rider on the way" SMS) → I've arrived (records time and, if allowed, location) → R-13. Secondary: Can't complete → R-18.
- **Rules:** the phone number is available only while this job is active. "Customer not home" can be chosen only 10 minutes after Arrived and after at least one call (a business setting).
- **API:** `POST /rider/jobs/{id}/start`, `POST /rider/jobs/{id}/arrived`.

### R-13 Pickup: collect bags

- **Shows:** what the customer declared, for reference ("Wash & fold, medium bag; 2 duvets"); bag count stepper (1–20); Take photo of all bags (camera only, required); checkbox "Each bag is tagged with {ref}"; Confirm collected.
- **Rules:** the rider never weighs or prices anything. Confirming tells the customer "{n} bags collected" in-app. Works offline: the action and photo are queued and sent when there is signal.
- **API:** `POST /rider/jobs/{id}/collect` (bag count, photo).

### R-14 Pickup: drop at shop

- **Shows:** shop name, address, Open in maps, Call shop; after arrival: "Hand over {n} bags to the shop", then "Waiting for the shop to confirm" until the shop confirms on S-13.
- **Rules:** the job completes when the shop confirms. If the shop counts a different number, the shop's count is recorded, both counts go to a ticket on A-66 and the job still completes, so the rider isn't stuck at the counter.
- **API:** `POST /rider/jobs/{id}/arrived-at-shop`; status by refreshing `GET /rider/jobs/{id}`.

## Deliveries, failed jobs and offline

### R-15 Delivery: collect from shop

- **Shows:** step bar (Collect → Go → Deliver); shop name, address, Open in maps, Call shop; order reference; expected bag count; "Waiting for the shop to hand over" until the shop confirms on S-18; then "Do you have {n} bags?" with Yes and "No, count is different".
- **Rules:** delivery jobs are created only for paid orders. If a payment is reversed before handover, the screen shows "Don't collect: payment not confirmed" and the job is cancelled. A different count opens a ticket on A-66 and holds the job until support answers.
- **API:** `POST /rider/jobs/{id}/collect`.

### R-16 Delivery: go to customer

- **Shows:** same layout as R-12 with the delivery address, the customer's delivery timing, Open in maps and Call.
- **Actions:** Start trip (sends the customer the delivery code SMS) → I've arrived → R-17. Secondary: Can't complete → R-18.
- **API:** `POST /rider/jobs/{id}/start`, `POST /rider/jobs/{id}/arrived`.

### R-17 Delivery: enter code

- **Shows:** "Hand over all {n} bags, then ask {customer} for the delivery code"; a 4-digit keypad; Complete delivery.
- **Rules:** a correct code completes the job and the order, with a success screen. A wrong code shakes the field and shows attempts left; after 5 wrong codes, entry locks and the screen shows Call support. "Customer doesn't have the code" also goes to support, who can complete the delivery from A-11 with a reason after checking identity. The code is checked by the server only, never on the phone, so it can't be guessed offline; without signal the rider waits for network or calls support.
- **API:** `POST /rider/jobs/{id}/complete` with `{code}`.

### R-18 Could not complete

- **Shows:** reasons by job kind. Pickup: Customer not home, Not answering, Wrong or unclear address, Cancelled at the door, Unsafe location, Other. Delivery: the same plus Customer refused the laundry. Optional photo of the gate or door; notes; Confirm.
- **Rules:** "not home" and "not answering" need at least one call from the app and 10 minutes since Arrived. A failed pickup returns the order to Accepted for admin to reschedule, and the customer is told. A failed delivery means the rider returns the bags to the shop (confirmed on S-13 as a return) and the order goes back to Ready. Any redelivery fee follows the open cancellation decision.
- **API:** `POST /rider/jobs/{id}/fail`.

### R-19 Waiting to sync

- **Shows:** queued actions in order (for example "Collected 3 bags · DAS-7K3P9Q · 10:42"), each marked Sending, Waiting for network or Failed; Retry all.
- **Rules:** the queue is stored on the phone and survives the app closing. Each action carries its own idempotency key and is sent in the order it happened; photos are compressed first. If the server rejects an action (for example the job was reassigned), it says so in plain words ("This job was given to another rider. Your update wasn't saved"). The rider cannot log out while anything is unsent.

## Earnings, history and account

### R-20 Earnings

- **Shows:** period switch (This week, Last week, This month); earned, paid out, and balance due; next payout date; a line per completed job ("Pickup · DAS-7K3P9Q · KSh {amount}"); adjustments with their reason (bonus or deduction); Payouts → R-21.
- **Rules:** every figure is a sum of ledger entries, never a stored balance. A job's amount appears once the job is completed. Amounts appear only for riders on a per-job pay rule (A-43); riders on a salary see their job counts instead.
- **API:** `GET /rider/earnings?period={p}`.

### R-21 Payout detail

- **Shows:** amount; period covered; method (M-Pesa); reference; date; the jobs included; "Something wrong?" → opens a support ticket.
- **API:** `GET /rider/payouts/{id}`.

### R-22 Job history

- **Shows:** completed and failed jobs by week, newest first; tapping one opens a read-only view with each step's time, the bag counts and the photos.
- **API:** `GET /rider/jobs?scope=history&cursor={c}`.

### R-30 Account

- **Shows:** photo, name, phone; rating (share of thumbs up), acceptance rate, completion rate; rows for Documents and vehicle, Language, Help (call or WhatsApp support), Change password, Log out.
- **Rules:** Log out is blocked while R-19 has unsent actions.

### R-31 Documents and vehicle

- **Shows:** each required document with its status (Verified, Pending, Rejected with the reason) and a button to upload or replace a photo: national ID, driving licence (for motorbike or car), police clearance certificate (if the business requires it). Vehicle: type (motorbike, bicycle, on foot, car) and plate.
- **Rules:** the business chooses which documents are required. A replaced document goes back to Pending. Licence expiry is recorded, and the rider is reminded 30 days before it expires. Document photos are stored privately and are visible only to admins.
- **API:** `GET /rider/documents`, `POST /rider/documents`.

## After the pilot

R-40 lets one rider carry several jobs in one trip, in an order the system suggests. It is specified when order volume makes batching worthwhile.
