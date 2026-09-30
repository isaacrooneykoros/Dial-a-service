# Customer app and public order pages (C-)

> Screens sub-tab "Customer app", pasted by the owner on 2026-10-01. Tables were rebuilt from the pasted text; wording is unchanged.

## Navigation and first run

Every customer of every business uses the public order pages (C-60 to C-62) through SMS links, with no app or account. The customer app (C-01 to C-49) is for businesses on Growth and up that take online bookings: it has three tabs (Home, Orders, Account), carries the business's own name and colours, and gets laundry booked, paid and delivered with as little effort as possible. Shared states and sign-in screens (X-) are on the Screens tab.

- **First run:** X-01 Splash → C-01 Welcome → C-02 Check your area → C-04 Sign up → C-05 Verify phone → C-10 Home. If the area isn't covered: C-02 → C-03 Join waitlist.
- **Returning:** X-01 → C-10 Home when signed in, otherwise X-10 Log in.
- **Booking:** C-10 → C-11 → C-12 → C-13 → C-14.
- **Paying:** SMS link or C-21 → C-22 → C-23 → C-24 → C-26, with C-25 as the Paybill fallback.

### C-01 Welcome

- **Purpose:** explain the service in five seconds and start sign-up.
- **Reached from:** X-01 on a device that has never signed in.
- **Shows:** business logo; one-line promise ("Laundry picked up, washed and delivered"); three points with icons: pickup at your door, weighed with photo proof, pay by M-Pesa after weighing; language switch (EN / SW) top right.
- **Actions:** Get started (primary) → C-02; I have an account → X-10; See prices (text link) → bottom sheet listing services and prices, read-only.
- **Rules:** shown once per device. All text and prices come from the business config, so every white-labelled app has its own wording.
- **API:** none; uses config loaded by X-01.

### C-02 Check your area

- **Purpose:** avoid signing up people the business can't serve.
- **Shows:** "Where should we pick up your laundry?"; searchable list of active service areas grouped by town; "My area isn't listed" at the bottom.
- **Actions:** pick an area → Continue → C-04 (the area is carried into the first address); "My area isn't listed" → C-03.
- **Rules:** no location permission is asked here; the list is enough for the pilot.
- **API:** areas come from `GET /business/config`.

### C-03 Join waitlist

- **Purpose:** turn uncovered areas into expansion data instead of lost visitors.
- **Shows:** "We're not in your area yet"; area name (free text, prefilled if typed in C-02); phone number; checkbox "Text me when you launch in my area"; Notify me button.
- **Actions:** Notify me → success message "We'll let you know" with Browse prices; back → C-02.
- **Rules:** one entry per phone per area; consent stored with time. Admin sees waitlist counts by area on A-41.
- **API:** `POST /waitlist`.

## Sign-up and verification

Log in, forgot password, enter code and set new password are the shared screens X-10 to X-13.

### C-04 Sign up

- **Purpose:** create a customer account for this business.
- **Shows:** first name; last name; phone (+254 prefix); password with the live checklist from X-13; checkbox "I agree to the Terms and Privacy Policy" with both linked (C-49); Create account button; "Already have an account? Log in".
- **Rules:** all fields required; the button stays disabled until the form is valid and the box is ticked. An existing number shows "This number already has an account" with Log in and Reset password buttons. The accepted terms and privacy versions are stored with a timestamp (Data Protection Act consent record). Sign-up is throttled per phone and per IP.
- **Success:** account created but not verified → C-05.
- **API:** `POST /auth/register`.

### C-05 Verify phone

- **Purpose:** prove the customer owns the number that will receive M-Pesa prompts and order SMS.
- **Shows:** X-12 titled "Verify your number".
- **Rules:** an unverified customer can browse prices and orders but cannot book; C-10 shows a "Verify your number" banner that returns here. Signing in with an unverified account also lands here.
- **Success:** → C-10 with a one-time tip card "Book your first pickup".
- **API:** `POST /auth/verify-phone`, `POST /auth/verify-phone/resend`.

## Home and booking

### C-10 Home

- **Purpose:** show what needs the customer's attention and make booking one tap away.
- **Shows, top to bottom:**
  1. App bar: logo, notification bell with unread count.
  2. Greeting with first name.
  3. Action card for the single most urgent thing, in this priority: payment due → rider on the way with delivery code → price just sent → rider on the way for pickup. Example: "DAS-7K3P9Q: pay KSh 1,250" with a Pay button.
  4. Active orders: up to 3 order cards, then "See all" → C-20.
  5. Book a pickup: full-width primary button.
  6. Services and prices: one card per service (for example "Wash & fold · KSh {rate}/kg", "Duvet · KSh {price} each").
  7. How it works: four steps, shown until the first completed order.
- **Rules:** Book a pickup is disabled with the reason shown when the phone isn't verified ("Verify your number to book") or an earlier order is unpaid after weighing ("Pay for DAS-7K3P9Q first"). While visible, active orders refresh every 30 seconds.
- **Empty (first visit):** greeting, How it works, Book a pickup.
- **API:** `GET /orders?scope=active`, `GET /notifications/unread-count`; services from config.

### C-11 Book 1 of 3: What needs washing

- **Purpose:** capture what the customer is sending and give an honest estimate.
- **Shows:**
  - Step indicator "1 of 3".
  - By weight services (for example Wash & fold, Wash & iron), each with its price per kg and minimum charge and a select toggle. When selected: "About how much?" chips: Small bag (about 3 kg), Medium (about 6 kg), Large (about 10 kg), Not sure.
  - By item services (for example Duvet, Blanket, Suit, Curtains per panel), each with price and a quantity stepper (0–20).
  - Preferences, only those the business enables: detergent (Standard / Hypoallergenic), fabric softener (Yes / No), wash whites separately (default Yes). A preference with a charge shows it ("+ KSh {x}/kg").
  - Special instructions (up to 300 characters).
  - Checkbox: "I've emptied pockets and removed valuables".
  - Sticky bottom bar: "Estimated KSh 900–1,100 · final price after weighing" and Continue.
- **Rules:** at least one service and the checkbox are required. The estimate is a range from the chosen bag sizes; with "Not sure" it shows the per-kg price instead of a range. The estimate refreshes 400 ms after the last change. The draft is kept on the phone for 24 hours.
- **API:** `POST /quotes` (saves nothing, charges nothing).

### C-12 Book 2 of 3: Pickup and delivery

- **Purpose:** where and when to collect, and where to return.
- **Shows:**
  - Pickup address: default address card with Change (bottom sheet of saved addresses plus "Add new address" → C-44, which returns here).
  - Pickup day: chips for today and the next 6 days.
  - Pickup time: grid of 2-hour windows (for example 8–10am to 6–8pm); full windows greyed with "Full".
  - Handover: "I'll hand it over" (default) or "Someone else will" with their name and phone.
  - Delivery address: toggle "Deliver to the same address" (on by default); off shows a second address picker.
  - Delivery timing: Any time / Evenings (5–8pm) / Weekends only, with the note "We deliver after your laundry is ready and paid".
- **Rules:** windows come from the server, based on business hours, the area and remaining capacity. Today's windows starting less than 60 minutes away (a business setting) are hidden. Addresses outside active areas can't be picked and show "We don't serve this area yet" with a waitlist link.
- **API:** `GET /slots?area={id}&date={date}`, `GET /addresses`.

### C-13 Book 3 of 3: Review and confirm

- **Purpose:** one last check, then book.
- **Shows:** summary cards, each with Edit returning to its step: what's being washed, preferences, pickup (address, day, window, handover person), delivery (address, timing). Then the price: estimated laundry range, delivery fee (exact), estimated total range. Then a "How payment works" box: "We weigh your laundry at the shop and send the price with a photo of the scale. Pay by M-Pesa; we deliver once it's paid." Then a care note linking the business's care policy. Confirm booking button.
- **Rules:** the screen re-fetches the estimate when it opens and never trusts numbers carried from step 1. It generates one idempotency key when opened, so a double tap or a retry creates only one order. If the window filled up meanwhile, a sheet shows "That time just filled up" with the two nearest free windows.
- **Pending decision:** if the delivery fee is charged at booking, this screen shows "Pay delivery fee now: KSh {fee}" and runs the payment flow before C-14.
- **API:** `POST /orders` with an `Idempotency-Key` header.

### C-14 Booking confirmed

- **Shows:** success tick, "Pickup booked", order reference with Copy, pickup day and window, three next steps (the rider collects and counts your bags; the shop weighs them and sends the price with a photo; you pay by M-Pesa and we deliver). Buttons: View order (primary) → C-21, Back to home.
- **Rules:** the back button goes to Home, never back into the booking flow. The draft is cleared.

## Orders, tracking and payment

### C-20 Orders

- **Shows:** segmented control Active / Past; order cards with reference, booking date, service summary ("Wash & fold · 2 duvets"), status badge, "Payment due" badge when relevant, and the total (or "Est. KSh 900–1,100" before weighing).
- **Rules:** newest first, 20 per page, pull to refresh. Tapping a card opens C-21.
- **Empty:** Active: "No orders in progress" + Book a pickup. Past: "Your finished orders will show here".
- **API:** `GET /orders?scope=active|past&cursor={c}`.

### C-21 Order detail

- **Purpose:** the single place to follow an order and act on it.
- **Shows, top to bottom:** reference and status badge; next step card (table below); timeline of every status with times, future steps greyed; rider card during an active pickup or delivery (photo, first name, vehicle plate, Call); branch line ("At {branch}", with its address and hours); items and weight (declared items, then after weighing the actual lines, weight, scale photo thumbnail and any condition notes with photos); price breakdown (lines, delivery fee, discount, total, marked "estimated" before weighing); payment (status, receipt link); addresses, pickup window, instructions.
- **Rules:** refreshes every 30 seconds while the order is active and the screen is open. The delivery code appears only when the order is out for delivery. Report a problem stays available until 48 hours after delivery (business setting).
- **API:** `GET /orders/{ref}`.

| State | Next step card says | Actions |
| --- | --- | --- |
| Requested, Assigned | We're confirming a shop for your pickup | Cancel |
| Accepted | Pickup {day, window}. We'll tell you when the rider is on the way | Cancel |
| Accepted, rider on the way | {Rider} is on the way to collect | Call rider |
| Picked up | {n} bags collected. The shop will weigh them next | — |
| Processing, unpaid | Weighed: {kg} kg, KSh {total} | Pay (primary), Something's not right |
| Processing, payment pending | Waiting for M-Pesa confirmation | — |
| Processing, part paid | KSh {paid} of KSh {total} received | Pay the rest |
| Processing, paid | Paid. Your laundry is being washed | — |
| Ready, unpaid | Ready! Pay KSh {total} to get it delivered | Pay |
| Ready, paid | Ready. We're assigning a rider | — |
| Out for delivery | {Rider} is on the way | Show delivery code |
| Completed | Delivered {date, time} | Rate, Book again, Report a problem |
| Cancelled | Cancelled: {reason}. {Refund status} | Book again |

Book again opens C-11 prefilled with the same services, preferences and addresses.

### C-22 Your laundry was weighed

- **Purpose:** the moment of trust: show exactly what was weighed and why it costs what it costs.
- **Reached from:** the "weighed and priced" SMS, the notification, or the next step card.
- **Shows:** weight in large type ("6.4 kg"); scale photo (tap to zoom); price lines (for example "Wash & fold · 6.4 kg × KSh {rate} = KSh {amount}", "Duvet × 2 = KSh {amount}"); delivery fee; total; the shop's condition notes with photos, if any; "Your estimate was KSh 900–1,100". Buttons: Pay KSh {total} (primary) → C-23; "Something's not right" → C-30 with the type preset to weight or price.
- **Rules:** if the shop corrected the price (S-16), a banner shows "Price updated by the shop: {reason}". Raising a problem doesn't stop the washing.
- **API:** `GET /orders/{ref}`.

### C-23 Pay

- **Shows:** amount due in large type; order reference; M-Pesa number prefilled with the account's phone and "Pay from a different number" to edit it; Send M-Pesa prompt button; note "You'll get a prompt on this phone. Enter your M-Pesa PIN to pay."; text link "Pay by Paybill instead" → C-25.
- **Rules:** the amount always comes from the server. If an attempt started less than 90 seconds ago, this screen jumps to C-24 instead of starting another. An already-paid order goes straight to C-26.
- **API:** `POST /orders/{ref}/pay` with `{phone}` and an idempotency key.

### C-24 Waiting for M-Pesa

- **Shows:** "Check your phone"; "Enter your M-Pesa PIN on the prompt sent to 0712 345 678"; a 90-second progress ring; tip "No prompt? Make sure your phone is on and unlocked".
- **Outcomes:** success → C-26 with the success tick. Failure shows the reason in plain words with Try again and Pay by Paybill: "You cancelled the payment", "Not enough M-Pesa balance", "Wrong PIN entered", "The prompt expired", or "M-Pesa couldn't complete the payment".
- **Rules:** checks status every 3 seconds for 90 seconds. Leaving the screen is safe: the server keeps checking with Safaricom and sends a notification when it knows.
- **API:** `GET /orders/{ref}/payment`.

### C-25 Pay to Till or Paybill

- **Shows:** numbered steps for the business's Paybill (a Till shows the Buy Goods steps and no account number): M-Pesa → Lipa na M-Pesa → Pay Bill → Business number {paybill} (Copy) → Account number {ref} (Copy) → Amount KSh {amount} (Copy) → enter PIN. Below: live status "Waiting for your payment…" and the warning "Use the exact account number so we can match your payment".
- **Rules:** checks every 10 seconds while open. A smaller amount shows "KSh {paid} of KSh {total} received" with the remaining amount. More than the total marks the order paid and flags the extra for a refund on A-51. Payments with a wrong account number land on A-51 for staff to match.
- **API:** `GET /orders/{ref}/payment`.

### C-26 Receipt

- **Shows:** success tick; "Payment received"; amount; M-Pesa receipt code; date and time; paying number masked (0712 ••• 678); order reference; business name. Buttons: Done → C-21, Share receipt (phone share sheet with a text receipt).
- **API:** `GET /orders/{ref}/payment`.

### C-27 Delivery code

- **Shows:** the 4-digit code in very large type; "Give this code to {rider} only after you've received all {n} bags"; rider card with Call; "Not home? Send the code to someone" (enter a phone number, sends one SMS).
- **Rules:** available only while the order is out for delivery; the code is never shown to shops or riders.
- **API:** `GET /orders/{ref}`, `POST /orders/{ref}/share-code`.

### C-28 Cancel order

- **Shows:** "Cancel order {ref}?"; reasons (Booked by mistake, Wrong time, Found another option, Other with text); "Nothing will be charged"; Cancel order (danger); Keep order.
- **Rules:** allowed while the order is Requested, Assigned or Accepted and the pickup rider hasn't marked "Arrived". Once the rider has started, the screen warns "The rider is already on the way"; any fee depends on the open cancellation decision.
- **API:** `POST /orders/{ref}/cancel`.

## Problems, reviews, help and account

### C-30 Report a problem

- **Shows:** type chooser: Weight or price looks wrong, Item missing, Item damaged, Late, Rider or shop behaviour, Payment problem, Other. Fields change by type: missing → which items and how many; damaged → up to 4 photos (camera or gallery) and a description; weight or price → description (the scale photo is attached automatically); others → description. Submit button.
- **Rules:** available from C-21 and C-22 until 48 hours after delivery. One open ticket per type per order; a second attempt opens the existing ticket. Submitting creates a ticket and opens C-34.
- **API:** `POST /orders/{ref}/issues` (multipart with photos).

### C-31 Rate your order

- **Shows:** 1–5 stars; tags that change with the rating (4–5 stars: On time, Clean, Well folded, Friendly rider; 1–3 stars: Late, Not clean, Missing items, Damaged, Rude); thumbs up or down for the rider; comment up to 500 characters; Submit; Skip.
- **Rules:** one review per order, editable for 24 hours. A rating of 2 or less asks "Want us to fix this?" and links to C-30.
- **API:** `POST /orders/{ref}/review`.

### C-32 Notifications

- **Shows:** list, newest first, grouped Today and Earlier, with an unread dot; Mark all as read.
- **Rules:** tapping marks it read and opens its screen. Kept for 90 days.
- **Empty:** "No notifications yet".
- **API:** `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all`.

### C-33 Help

- **Shows:** Chat on WhatsApp (opens the business's WhatsApp with "Hi, I need help with order {ref}" when opened from an order); Call support; FAQs as expandable rows (how pricing works, how weighing works, lost or damaged items, paying by Paybill, cancelling); My tickets with status.
- **Rules:** FAQ text is business content editable in admin, per language.
- **API:** `GET /support/tickets`, `GET /business/content?type=faq`.

### C-34 Ticket

- **Shows:** type, order reference and status (Open, Waiting for you, Resolved); message thread with photos; reply box with photo attach; when resolved, the outcome (for example "Refund of KSh 300 sent, M-Pesa {receipt}").
- **Rules:** a resolved ticket can be reopened within 7 days.
- **API:** `GET /support/tickets/{id}`, `POST /support/tickets/{id}/messages`.

### C-40 Account

- **Shows:** name and phone; rows for Edit profile, Addresses, Language, Notification settings, Change password, Help, Terms and privacy, Log out; Delete account at the bottom in red; app version.

### C-41 Edit profile

- **Shows:** first name, last name, email (optional, for emailed receipts); Save.
- **API:** `PATCH /me`.

### C-42 Change phone number

- **Flow:** enter the new number → code sent to the new number (X-12) → confirm with current password → done. The old number receives an SMS telling them the number changed.
- **Rules:** a number already used in this business is refused.
- **API:** `POST /me/phone/change`, `POST /me/phone/confirm`.

### C-43 Addresses

- **Shows:** address cards (label, estate, building, landmark, Default badge); Add address; each card opens C-44; delete via the card's menu with confirmation.
- **Rules:** up to 10 addresses. Deleting never affects past orders, because orders keep their own copy of the address.
- **API:** `GET /addresses`, `DELETE /addresses/{id}`.

### C-44 Add or edit address

- **Shows:** label (Home, Work, Other with a custom name); area (active areas only, required); estate or road (required); building or house name (required); house or door number; landmark (for example "Opposite Naivas"); directions for the rider (up to 300 characters); "Save my current location" (asks for location permission only when tapped, then shows "Location saved"); Set as default; Save.
- **Rules:** no map is drawn in the MVP, which avoids map API costs; riders open the saved location in their own maps app.
- **API:** `POST /addresses`, `PATCH /addresses/{id}`.

### C-45 Language

- **Shows:** English, Kiswahili. Applies immediately and is saved to the profile, so SMS arrive in the same language.
- **API:** `PATCH /me`.

### C-46 Notification settings

- **Shows:** required messages listed but locked on (codes, payments, delivery, cancellations); optional toggles for payment reminders and rating requests.
- **API:** `PATCH /me/notification-preferences`.

### C-47 Change password

- **Shows:** current password, new password with checklist, confirm; Save. Every other session is signed out.
- **API:** `POST /auth/password/change`.

### C-48 Delete account

- **Shows:** what is deleted (profile, addresses, saved preferences) and what is kept (order and payment records for the legal retention period, with the name and phone removed); Continue → code sent to the phone (X-12) → Delete my account.
- **Rules:** blocked while any order is active or unpaid, naming the order.
- **API:** `POST /me/delete` (anonymises; nothing financial is removed).

### C-49 Terms and privacy

- **Shows:** the business's terms, privacy policy and care policy with version and date.
- **Rules:** when a new version is published, the next app open shows a blocking sheet to accept it, and the acceptance is recorded.

## After the pilot

C-50 Laundry plans (monthly subscriptions for regular customers) and C-51 Refer a friend are specified when their milestone starts.

## Public order pages (no app, no account)

These three pages are how most customers see the system, including every walk-in on the Starter plan. They open from the SMS link or the QR code on S-44, work in any phone browser, carry the business's branding, and are hidden from search engines.

### C-60 Order page

- **Shows:** business logo and name; order reference; status in plain words with a simple progress bar (Received → Washing → Ready → Collected or Delivered); customer first name; items, weights, scale photos (tap to zoom) and condition notes; price breakdown; amount paid and balance; the collection code once the order is ready; branch address, opening hours, Call and WhatsApp buttons.
- **Actions:** Pay now (→ C-61) while anything is owed; Report a problem (a short form that lands on A-66); Rate after completion; Book a pickup (Growth).
- **Rules:** opened only with the token from the SMS or QR. The link expires 30 days after completion ("This link has expired. Contact {business}"). Rate limited. Never shows the address or the full phone number.
- **API:** `GET /o/{token}`.

### C-61 Pay page

- **Shows:** amount due (with part payments already made).
  - Connected business: the customer's number masked (0712 ••• 678) with "Pay from another number"; Send M-Pesa prompt; the waiting state from C-24; success goes to C-62.
  - Basic business: the Till or Paybill number and, for a Paybill, the order reference as account number, each with Copy; step-by-step instructions; "I've paid" button.
- **Rules:** "I've paid" shows "Thanks, {business} will confirm when they see your payment" and puts an in-app alert in the staff app to record the code. It never marks the order paid by itself.
- **API:** `POST /o/{token}/pay`, `GET /o/{token}/payment`.

### C-62 Receipt page

- **Shows:** success tick; amount; method; M-Pesa receipt; date and time; business name; order reference; collection code; any balance still owed; Share.
- **API:** `GET /o/{token}/receipt`.
