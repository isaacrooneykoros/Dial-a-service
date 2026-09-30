# Staff app screens (S-, X-15)

> Screens sub-tab "Shop app screens", pasted by the owner on 2026-10-01. Tables were rebuilt from the pasted text; wording is unchanged.

## Navigation, roles and devices

The staff app runs the counter and the washing floor: take orders, weigh, get paid, release. It works on the counter's phone or tablet in a browser; nothing is installed.

|  | Staff | Branch manager |
| --- | --- | --- |
| Tabs | New order, Queue, Search, More | Same, plus Branch today in More |
| Orders and payments | Their branch | Their branches |
| Cash | Only with the cash right | Yes |
| Discounts, price corrections | Only with those rights | Yes |
| Cash-up | Their own (S-50) | Approve everyone's (S-51) |
| Register devices | No | Yes (S-02) |

- **Phone and tablet:** on a phone, queue and order detail are separate screens; on a tablet (768 px and wider) they sit side by side.
- **Alerts:** a new online booking plays a sound and shows a banner while the app is open.
- **Needs a connection:** order references and prices come from the server, so creating orders and taking payments need network. Screens say so clearly when offline. An offline counter mode is possible later using blocks of references issued to each device in advance.

### S-01 Choose branch

- **Shows:** the branches this person works at. Shown only when there are several; the last choice is remembered; switch from S-30.
- **API:** `GET /me/branches`.

### S-02 Register this device

- **Purpose:** turn a counter phone or tablet into a shared device where staff switch with PINs (X-15).
- **Shows:** device name ("Front counter tablet"); branch; Register.
- **Rules:** manager or owner only. The device appears in the console (A-42), where it can be removed at any time. Registering signs the manager out of that device, leaving it on the PIN screen.
- **API:** `POST /staff/devices`.

### X-15 Switch user

- **Shows:** the staff photos and names for this branch; tap a name and enter a 4-digit PIN.
- **Rules:** only on registered devices. Locks after 5 idle minutes. 5 wrong PINs lock the device until a manager unlocks it. Every action afterwards is recorded against the person who switched in.
- **API:** `POST /auth/pin-switch`.

## Counter: new orders, payment and release

### S-40 New order

- **Purpose:** take a walk-in or phone order in under a minute, weighing and pricing it on the spot.
- **Shows, top to bottom, on one screen:**
  1. Customer: picked with S-41; shows name, masked phone, a Trusted badge, and a warning if they owe money on another order ("Owes KSh 450 on MSF-4H2K8P").
  2. How it came: Walk-in, or Phone/WhatsApp.
  3. Fulfilment: Collect here, or Deliver (Growth; asks address and delivery time). Choosing Pickup (Growth) instead creates a Booked order for a rider and ends here.
  4. Items: quick-add buttons for the business's most-used services. Per-kg lines have a weight field and a Take scale photo button; per-item lines have steppers. Modifiers such as Express appear as switches.
  5. Weigh later: a switch for busy moments. The order is saved as Received with its bag count, and weighing happens on S-14.
  6. Bags: count, and Condition notes (S-15).
  7. Discount: only for staff with the discount right; amount or %, with a reason.
  8. Summary from the server: lines, discount, VAT if the business is registered, total.
  9. Buttons: Save and take payment (to S-42), or Save, pay later (to S-44). Pay later is hidden when the business requires payment at drop-off.
- **Rules:** a weighed line needs its scale photo. The order is created with an idempotency key; the reference is issued by the server, and the "order received" SMS goes out with the collection code and tracking link.
- **API:** `POST /quotes` for the live summary, `POST /staff/orders`.

### S-41 Find or add customer

- **Shows:** a search box on the number keypad (phone first; names also work); results with name, masked phone, last order date, amount owed and Trusted badge; Add new customer with phone and name (both required) and optional notes; "No phone" option with a warning that they won't receive SMS.
- **Rules:** a phone already in this business opens the existing customer. Creating a customer sends nothing by itself.
- **API:** `GET /staff/customers?q={query}`, `POST /staff/customers`.

### S-42 Take payment

- **Shows:** amount due, order reference, customer; three method tabs.
  - M-Pesa prompt (Connected businesses): phone prefilled; Send prompt; an inline 90-second waiting ring; the result in plain words, with Try again.
  - M-Pesa code: the business's Till or Paybill number to show the customer; fields for the 10-character M-Pesa code and the amount; checkbox "I've seen this payment on our M-Pesa".
  - Cash (only with the cash right): amount received; change shown in large type.
  - Part payment: an amount field when the business allows part payments.
- **Rules:** a recorded code must match Safaricom's format and not be used before in this business ("This code was already used on MSF-4H2K8P"). Every payment records the staff member and device. The receipt SMS goes out automatically. For a Connected Paybill, a matching manual payment appears as a banner ("KSh 1,250 received from JOHN K.") with Apply to this order.
- **API:** `POST /staff/orders/{ref}/payments`, `POST /staff/orders/{ref}/payments/prompt`.

### S-43 Release at counter

- **Shows:** a 4-digit collection code keypad, with Find by phone or reference as the alternative; the order card with customer name, bag count and balance.
  - Unpaid: a large red "Not paid: KSh {due}" with Take payment (S-42); Release is disabled.
  - Trusted customer, unpaid: an amber note "Trusted: may pay later"; Release allowed with a reason; the balance stays owed.
  - Paid: "Hand over {n} bags", checkbox "Customer checked the items", Release.
- **Rules:** 5 wrong codes lock that order until a manager unlocks it. Releasing without the code (customer lost it) requires finding the customer by phone, confirming the name and the reason "No code: identity checked"; it is audited. Release completes the order and sends the thank-you SMS.
- **API:** `POST /staff/orders/{ref}/release`.

### S-44 Receipt and tags

- **Shows:** the reference in very large type with "Write {ref} on every bag's tag"; bag count; receipt summary; a QR code the customer can scan to open the order page (C-60) without an SMS; Resend receipt SMS; Print (browser print in 80 mm receipt layout, optional); New order.
- **Rules:** the receipt SMS is sent once automatically; staff can resend it up to 3 times.
- **API:** `POST /staff/orders/{ref}/receipt`.

## Queue and order detail

### S-10 Queue

- **Shows:** stage tabs with counts, then order cards for the chosen stage.

| Stage tab | Orders in it | Primary action on the card |
| --- | --- | --- |
| Pickups | Booked, rider not yet collected (Growth) | — |
| Incoming | Picked up, on the way to the branch (Growth) | Receive bags |
| To weigh | Received, not yet weighed | Weigh |
| Washing | Processing | Mark ready |
| Ready | Ready, with Paid or Not paid and Collect or Deliver badges | Release, or Hand over for paid deliveries |
| Done today | Completed today | — |

- **Card contents:** reference; customer name; service summary; bag count; time in this stage; badges for Due by (from the turnaround setting), Paid or Not paid, Collect or Deliver, Trusted, Problem, and an icon when there are special instructions.
- **Rules:** oldest first in every tab, so work is done in order. Refreshes every 30 seconds. Managers with several branches get a branch filter.
- **Empty:** "Nothing here right now".
- **API:** `GET /staff/orders?stage={stage}`.

### S-11 Order detail

- **Shows, top to bottom:**
  1. Reference in very large type (for tags), status, and badges for channel (Walk-in, Phone, Online) and fulfilment (Collect, Deliver).
  2. Instructions box when present (preferences and notes).
  3. Customer name and masked phone; tapping reveals it and offers Call (logged).
  4. Lines, weights and scale photos; condition notes with photos.
  5. Payments (method, amount, who recorded it) and the balance due.
  6. Bag counts at every handover; rider card while a rider is involved.
  7. Timeline.
- **Primary action by state:** Picked up → Receive bags (S-13); Received → Weigh and price (S-14); Processing → Mark ready (S-17); Ready to collect → Release (S-43); Ready to deliver and paid → Hand over (S-18).
- **Always available while money is owed:** Take payment (S-42).
- **Secondary:** Condition notes (S-15), Correct price (S-16, before any payment, with the right), Cancel (S-12), Resend receipt (S-44), Report a problem (S-20).
- **API:** `GET /staff/orders/{ref}`.

## Decline, receive, weigh and price

### S-12 Cancel order

- **Shows:** reasons (Customer changed their mind, Duplicate order, Can't do this item, Other with text); whether anything was paid and what refund is due; Cancel order (danger).
- **Rules:** staff can cancel before weighing; after that only a manager. If anything was paid, the refund is recorded (A-52) before the cancellation completes. The customer gets the cancellation SMS.
- **API:** `POST /staff/orders/{ref}/cancel`.

### S-13 Receive from rider

- **Shows:** rider name and photo; "Rider recorded {n} bags"; "How many bags did you receive?" stepper prefilled with the rider's count; checkbox "All bags tagged {ref}"; Confirm received. The same screen, titled "Receive return", is used when a failed delivery comes back.
- **Rules:** a different count shows "Rider recorded 3 bags. You counted 2." and asks for a note. Confirming records the shop's count, opens a ticket on A-66 and releases the rider.
- **API:** `POST /shop/orders/{ref}/receive`.

### S-14 Weigh and price

- **Purpose:** record exactly what was received and what it costs, with evidence. This screen creates the customer's bill.
- **Shows:**
  - One line per declared by-weight service with a weight field (numeric keypad, kg, one decimal) and its own scale photo (camera only, must show the scale reading with the laundry on it; Retake).
  - One line per declared by-item service with a count stepper.
  - Add line: add a service the customer didn't declare (for example two duvets found in the bag).
  - Remove line: a declared item that wasn't in the bags, with a reason.
  - Condition notes: a count and a link to S-15.
  - Live price preview from the server: each line, any minimum charge applied, delivery fee, total.
  - Send price to customer, with a confirm sheet: "Send KSh 1,250 for 6.4 kg to Wanjiru K.? You can correct it until she pays."
- **Rules:**
  - A price can't be sent without a scale photo for every weighed line.
  - Weights outside 0.5–60 kg per line, or more than 50% different from the customer's estimate, ask "Are you sure?" before sending.
  - Needs a connection, because the server calculates the price; offline, the button is disabled with the reason.
  - Sending moves the order to Processing and sends the customer the "weighed and priced" SMS that opens the order page (C-60).
  - Photos upload in the background as soon as they are taken, so sending is quick.
- **API:** `POST /quotes` for the preview, `POST /shop/orders/{ref}/weigh` (lines and photo IDs) with an idempotency key.

### S-15 Condition notes

- **Purpose:** record stains and damage that were already there, so the shop isn't blamed later.
- **Shows:** existing notes; Add note with item description ("White shirt"), issue (Stain, Tear, Missing button, Colour fading, Other), a required photo and an optional comment.
- **Rules:** notes can be added until the order is marked ready. The customer sees every note on C-22 and C-21.
- **API:** `POST /shop/orders/{ref}/condition-notes`.

### S-16 Correct price

- **Shows:** the S-14 lines, editable; reason (Wrong weight entered, Missed an item, Wrong service, Other); Send corrected price.
- **Rules:** allowed only before any money is received, and blocked while an M-Pesa prompt is pending. After a payment, changes go through admin (a refund or an extra charge). The customer is told "Price updated by the shop: {reason}". Every correction is audited.
- **API:** `POST /shop/orders/{ref}/reprice`.

## Ready, handover, search and account

### S-17 Mark ready

- **Shows:** checklist of what the customer asked for (for example "Ironed", "Hypoallergenic detergent used"); bags going out, prefilled with the received count and changeable with a reason ("Combined into fewer bags"); checkbox "All bags tagged {ref}"; Mark ready.
- **Rules:** the customer is told it's ready: with "a rider will bring it soon" if paid, or with a payment request if not. A paid order goes onto the dispatch board (A-44) for a delivery rider.
- **API:** `POST /shop/orders/{ref}/ready`.

### S-18 Hand over to rider

- **Shows:** the assigned rider's photo, first name and plate, so staff can check it's the right person; bag count; "Hand {n} bags to {rider}"; Confirm handover.
- **Rules:** if the order isn't paid, the screen shows a large red "Don't release: payment not received" and nothing can be confirmed. If no rider is assigned, it says so. The rider confirms the count on their side (R-15).
- **API:** `POST /shop/orders/{ref}/handover`.

### S-19 Search

- **Shows:** a search box accepting a full reference, its last 4 characters, or a customer first name; results as order cards; recent searches.
- **Rules:** The customer's phone number, or its last 4 digits, also works. Results cover this branch; managers can search all their branches.
- **API:** `GET /shop/orders?q={query}`.

### S-20 Report a problem

- **Shows:** types (Bag count mismatch, Undeclared or unsuitable item such as leather, Damaged during washing, Instructions unclear, Payment problem, Other); description; up to 4 photos; Submit.
- **Rules:** creates a ticket on A-66 linked to the order. Reporting damage caused by the shop itself is encouraged, and the ticket records who reported it first.
- **API:** `POST /shop/orders/{ref}/issues`.

### S-30 Account

- **Shows:** name, phone, shop and role; Switch branch (only with several); Change PIN; Language; Change password; Help (call or WhatsApp support); Log out.

## End of day

Owner-level screens (dashboard, staff, prices, reports) now live in the business console. The staff app keeps only what happens at the counter at closing.

### S-50 My cash-up

- **Purpose:** each person closes their own drawer, so missing cash is traced to one person and one day.
- **Shows:** today's cash payments this person recorded (time, order, amount); expected cash; "Counted cash" field; the difference, calculated live; a note (required when there is a difference); this person's recorded M-Pesa codes and prompt payments, for information; Submit.
- **Rules:** one cash-up per person per branch per day. After submitting, that day's cash entries are locked; a cash payment recorded later that day is marked "after cash-up" and appears on the manager's review. A cash-up waits for manager approval.
- **API:** `GET /staff/cashup/today`, `POST /staff/cashup`.

### S-51 Branch today

- **Purpose:** the branch manager's closing view, without opening the console.
- **Shows:** orders received, ready and completed today; sales; payments by method (M-Pesa prompt, M-Pesa code, cash); ready but unpaid (count and value); uncollected for more than 7 days; open problems; each person's cash-up with Expected, Counted, Difference and Approve or Query.
- **Rules:** Query sends the note back to the staff member. Approved cash-ups can't be changed; corrections are new adjustment entries by a manager, with a reason.
- **API:** `GET /staff/branch-today`, `POST /staff/cashups/{id}/approve`, `POST /staff/cashups/{id}/query`.
