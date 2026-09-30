# Diagrams

These are text versions of the three diagrams in the design doc. The Markdown export replaces diagrams with placeholders, so this file is the source Claude Code reads.

## 1. Architecture: one API serves every business, each kept separate

```mermaid
flowchart LR
  subgraph Clients["Per business: {slug}.dialaservice.co.ke"]
    STAFF["Staff app /staff"]
    CONSOLE["Business console /console"]
    CUST["Customer app / (Growth)"]
    RIDER["Rider app /rider (Growth)"]
    PUBLIC["Public order pages /o/{token}"]
  end

  CF["Cloudflare: wildcard DNS + TLS<br/>/api/* to Django, rest to Pages"]

  subgraph Render
    API["Django REST API (dial_app role)<br/>every request scoped to one business"]
    WORKER["Celery worker (dial_app role)<br/>outbox, SMS, reminders, STK status checks"]
    PADMIN["Platform admin (dial_platform role)<br/>admin.dialaservice.co.ke"]
  end

  PG[("Neon Postgres<br/>row-level security")]
  REDIS[("Redis queue")]
  R2[("Cloudflare R2<br/>private photos")]
  DARAJA["M-Pesa Daraja<br/>each business's own keys;<br/>platform keys for billing"]
  SMS["SMS gateway"]
  EMAIL["Resend email"]

  STAFF & CONSOLE & CUST & RIDER & PUBLIC --> CF --> API
  API --> PG
  API --> REDIS --> WORKER
  WORKER --> PG
  API --> R2
  API <--> DARAJA
  WORKER --> SMS
  WORKER --> EMAIL
  PADMIN --> PG
```

## 2. Order state machine: every order passes the counter and leaves only when paid

```mermaid
stateDiagram-v2
  [*] --> booked: online or phone booking (Growth)
  [*] --> received: walk-in order at the counter
  booked --> picked_up: rider collects, counts bags, photo
  picked_up --> received: branch confirms bag count
  received --> processing: weighed, scale photo per weighed line, price sent
  processing --> ready: washed and packed, outgoing bag count set
  ready --> out_for_delivery: rider collects, only if paid or trusted
  out_for_delivery --> completed: customer's delivery code
  ready --> completed: collected at counter with collection code, only if paid or trusted

  booked --> cancelled: customer or staff
  picked_up --> cancelled: staff
  received --> cancelled: staff, before weighing
  processing --> cancelled: manager, refund recorded first if paid
  ready --> cancelled: manager, refund recorded first if paid
  out_for_delivery --> cancelled: manager, refund recorded first if paid

  completed --> [*]
  cancelled --> [*]
```

Payment status runs alongside the order status:

```mermaid
stateDiagram-v2
  [*] --> unpaid
  unpaid --> pending: M-Pesa prompt sent
  pending --> unpaid: failed, cancelled or timed out
  pending --> paid: callback or status query confirms full amount
  unpaid --> part_paid: recorded code, cash or Paybill for less than the total
  part_paid --> paid: remaining amount received
  unpaid --> paid: recorded code, cash or Paybill for the full total
  paid --> part_refunded: partial refund recorded
  paid --> refunded: full refund recorded
  part_refunded --> refunded: remaining refunded
```

## 3. Payment flow for a connected business: only the M-Pesa result can mark an order paid

```mermaid
sequenceDiagram
  autonumber
  participant S as Staff app
  participant C as Customer phone
  participant A as Dial A Service API
  participant D as M-Pesa Daraja (business keys)

  S->>A: record weight and scale photo (POST /staff/orders/{ref}/weigh)
  A->>A: pricing.py computes total; order becomes processing
  A-->>C: SMS: weight, price, link to /o/{token} (via outbox)
  C->>A: tap Pay on C-61 (or staff sends prompt from S-42)
  A->>A: create PaymentAttempt (pending), amount from stored total
  A->>D: STK Push with business shortcode and passkey
  D-->>C: PIN prompt
  D->>A: callback to /payments/mpesa/stk/{business token}
  A->>A: match CheckoutRequestID, lock row, ignore if already final, check amount
  A->>A: mark paid once, write balanced ledger transaction, outbox receipt SMS
  A-->>C: receipt SMS with link to C-62
  A-->>S: order shows Paid, release enabled
  Note over A,D: No callback in time: worker runs an STK status query and applies the result through the same code path
```

**Basic businesses** (no Daraja yet): the customer pays the business's Till or Paybill directly. Staff record the M-Pesa code and amount on S-42 after seeing the payment in the business's own M-Pesa messages. The code must match Safaricom's format and be unused in this business, and it is recorded against the staff member and device.
