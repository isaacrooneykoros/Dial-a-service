# Platform admin and website screens (P-, W-)

> Screens sub-tab "Platform and website", pasted by the owner on 2026-10-01. Tables were rebuilt from the pasted text; wording is unchanged.

## Website and business sign-up

The website sells the product and lets a laundry start a trial without talking to anyone. It is a fast static site in English and Swahili, with a WhatsApp chat button on every page.

### W-01 Home

- **Shows:** headline ("Run your laundry from your phone"); the six problems the system solves, each with its answer; how it works in three steps (sign up; add your prices and M-Pesa Till; take your first order today); screenshots of the staff app, a receipt SMS and the customer order page; a pricing summary; Start free trial.
- **Rules:** written for laundry owners, not developers. Page titles and text target searches such as "laundry management system Kenya".

### W-02 Pricing

- **Shows:** Starter, Growth and Business cards with prices and the feature comparison from the design doc; "14 days free, no payment needed"; FAQs (Do I need Daraja? No, start with your Till number. Who owns my data? You do. Can I cancel any time? Yes. How are SMS charged?); Start free trial.

### W-03 Start free trial

- **Shows:** business name; your name; phone; password; web address, suggested from the business name with a live availability check (____.dialaservice.co.ke); number of branches (1, 2–3, 4 or more, used to suggest a plan); agreement to the terms and privacy policy; Start free trial.
- **Flow:** SMS code (X-12) → the system creates the business on trial, the owner account, a first branch, default settings, the service template and the web address → hands the owner to {address}/console, already signed in through a one-time token → B-01.
- **Rules:** web addresses use a–z, 0–9 and hyphens; reserved words (www, admin, api, app, console, staff, rider) are refused. One trial per phone number. Sign-up is throttled per phone and IP. Each step is recorded for the onboarding funnel (P-03).
- **API:** `POST /platform/signup` on the platform host.

### W-04 Find my business

- **Shows:** phone number; Send me my links.
- **Rules:** always answers "If this number has accounts, we've sent the links by SMS"; the SMS lists each business where that phone has an account. Nothing is revealed on screen.

## Platform admin

Your team runs the platform from Django admin on admin.dialaservice.co.ke, with custom screens where stock admin isn't enough (P-02, P-03, P-09). It requires an authenticator app, sits behind Cloudflare Access, and never shows any business's M-Pesa secrets or lets anyone change a business's orders.

| Action | Super admin | Support | Finance |
| --- | --- | --- | --- |
| View businesses and setup progress | Yes | Yes | Yes |
| View as business (read-only) | Yes | Yes | No |
| Extend trial, apply credit, change plan | Yes | No | Yes |
| Suspend or reactivate a business | Yes | No | No |
| Invoices, billing payments, SMS top-ups | Yes | No | Yes |
| Plans and prices | Yes | No | No |
| Support tickets, announcements | Yes | Yes | No |
| Staff and roles | Yes | No | No |

### P-01 Businesses

- **Columns:** name, web address, plan, status, trial end, created, last active, orders in the last 30 days, SMS balance, M-Pesa level.
- **Filters and search:** status, plan, trial ending this week, overdue, inactive for 7 days, M-Pesa level.

### P-02 Business detail

- **Shows:** owner and contacts; subscription and invoices; usage against limits; setup checklist progress; M-Pesa status (level, last callback, recent failure rate, never secrets); SMS usage; tickets; internal notes.
- **Actions, each with a reason and audited:** extend trial; apply a credit or discount; change plan; suspend or reactivate; resend the owner's invitation; reset the owner's password after an identity check; view as business (read-only, a visible banner in their console log, ends after 30 minutes); run a data export on request; schedule deletion.

### P-03 Onboarding funnel

- **Shows:** sign-ups per week and how many reached each checklist step, went live, and paid; businesses stuck at a step for more than 2 days, with the owner's phone and Call.
- **Why:** this is where you win or lose businesses without "looking for users": a short call at the right step converts trials.

### P-04 Plans

- **Shows:** each plan's name, monthly price, limits, features, SMS bundle and whether it's shown on the website.
- **Rules:** a price change applies to new invoices only; existing businesses can be kept on their old price.

### P-05 Invoices and subscriptions

- **Shows:** all invoices with status; overdue list with days overdue; businesses entering grace, read-only or suspension this week.
- **Actions:** mark paid manually with a receipt; issue a credit note.

### P-06 Billing payments

- **Shows:** M-Pesa prompts and Paybill payments to your Paybill; unmatched payments.
- **Actions:** match a payment to an invoice or SMS top-up.

### P-07 SMS

- **Shows:** gateway status, delivery rate, cost per message, usage by business, failed messages, and sender ID requests with status (Requested, Submitted to networks, Approved, Rejected).

### P-08 Support tickets

- **Shows:** tickets from businesses (A-67) with a side panel of the business's plan, setup and recent errors; response time against the target.
- **Actions:** reply, assign, resolve.

### P-09 Platform health

- **Shows:** API error rate and response times; worker queue depth and failed jobs; M-Pesa callback delay and success rate by business; SMS failure rate; database size and slow queries; links to Sentry.
- **Rules:** alerts go to your team by SMS or email when a value crosses its threshold.

### P-10 Announcements

- **Shows:** compose a message to all businesses or a filtered set; channels (console banner, SMS, email); schedule.

### P-11 Staff and roles

- **Shows:** your team with role (Super admin, Support, Finance), authenticator status and last login; invite, change role, deactivate.

### P-12 Audit log

- **Shows:** every platform action, including view-as sessions, with before and after values. Read-only.
