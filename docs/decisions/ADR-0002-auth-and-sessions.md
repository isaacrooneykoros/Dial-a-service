# ADR-0002: Authentication, sessions, invitations and devices

- **Status:** Accepted (owner, 2026-10-01)
- **Date:** 2026-10-01
- **Sources:** design doc "Roles, permissions and sign-in"; `10-screens-shared.md` X-10 to X-14; `11-staff-app.md` S-02, X-15, S-30; `12-business-console.md` A-41, A-42; `CLAUDE.md` §6.5 and §6.7; owner answers of 2026-10-01 (UNDERSTANDING §5)

## Context

Everyone signs in with phone and password on their business's own address. Staff join by SMS invitation, and counter devices switch people by a personal 4-digit PIN. The owner must see and end any session. Access tokens stay in memory; the refresh token sits in an httpOnly cookie.

## Decision

### 1. Users

- `accounts.User` extends `AbstractBaseUser` only, **not** `PermissionsMixin`. That mixin would add auth group and permission link tables with no business column. Django admin access for platform staff comes from `is_staff` and simple `has_perm`/`has_module_perms` methods driven by the platform role.
- **Fields:**

  | Field | Type or values |
  | --- | --- |
  | `id` | UUID |
  | `business` | nullable FK; see ADR-0001 §3 |
  | `phone` | E.164 |
  | `first_name`, `last_name` | text |
  | `role` | `owner`, `manager`, `accountant`, `staff`, `rider`, `customer`, `platform_super_admin`, `platform_support`, `platform_finance` |
  | `language` | `en` or `sw` |
  | `is_phone_verified` | boolean |
  | `status` | `active`, `suspended`, `deactivated` |
  | `pin_hash`, `pin_set_at` | nullable |
  | `can_accept_cash`, `can_give_discounts`, `can_correct_prices` | booleans (the three per-person rights from A-41; stored now because invitations carry them; enforced from M3/M4) |
  | `is_staff` | boolean |
  | `last_login`, timestamps | |

- **Constraints:** unique `(business, phone)` where business is set; unique `phone` where business is null; a check constraint that platform roles have no business and business roles do.
- **`USERNAME_FIELD = "phone"`.** Phone isn't globally unique, so a custom backend, `BusinessPhoneBackend`, authenticates by `(current business, phone)`, and Django's `auth.W004` warning is silenced with a comment pointing here.
- **Passwords:** Django's PBKDF2 hasher (Argon2 would need a dependency outside the approved list). The validators match the X-13 checklist exactly: minimum length 8, not only numbers, not a common password.

### 2. Phone numbers

- One module, `apps/accounts/phones.py`, built on `phonenumbers`, with `normalize_ke_phone(raw) -> str` and `mask_phone(e164) -> "0712 ••• 678"`.
- It accepts `07…`, `01…`, `7…`, `1…`, `+254…` and `254…`, with spaces or dashes. It rejects anything that isn't a valid Kenyan mobile number, and stores `+2547XXXXXXXX` or `+2541XXXXXXXX`.
- It is table-tested with every input form listed in the kickoff.

### 3. Access and refresh tokens, and sessions

- **Our own session table:** `accounts.UserSession(TenantModel)` has user, device (nullable), kind (`password` or `pin`), user agent, IP, created_at, last_seen_at, expires_at, revoked_at, revoke_reason, `refresh_hash` and `previous_refresh_hash`. We don't use simplejwt's blacklist app, whose tables have no business column and would be readable across businesses.
- **Access token:** a JWT signed by simplejwt's `AccessToken`, valid for **15 minutes**, with claims `user_id`, `business_id` and `session_id`. The authentication class rejects the token when:
  - `business_id` doesn't match the host's business (a token from `mamasafi` is useless on `cleanpro`);
  - the session is revoked or expired;
  - the user isn't active.

  Checking the session on every request costs one indexed lookup. It makes sign-out from A-42 and deactivation on A-41 take effect **at once**, as the screens require.
- **Refresh token:** a random 256-bit opaque string, not a JWT, stored as SHA-256. It is valid for **7 days** from sign-in and **rotates on every use**. If a token that was already rotated is presented again (a sign of theft), the whole session is revoked.
- **Refresh cookie `das_refresh`:**
  - `HttpOnly`, `Secure` (off only in local settings), `SameSite=Strict`;
  - `Path=/api/v1/auth`;
  - no `Domain` attribute, so it belongs to one business's host only.
- **Frontend:** keeps the access token in memory only. On page load it calls `POST /auth/refresh` to restore the session (ADR-0003).
- **Signing out every session:** a password reset or password change (X-13, C-47) revokes all of the user's sessions except the new one. Deactivation revokes all of them.

### 4. SMS codes (`PhoneOTP`)

- `PhoneOTP(TenantModel)` has phone, purpose (`password_reset`, `invitation`; `verify_phone` is added with customer sign-up in M9), code_hash, expires_at, attempts, used_at.
- **Code:** 6 digits from `secrets`. It is stored as HMAC-SHA256 with a server-side key (`OTP_HASH_KEY`), because a slow password hash adds nothing for a 6-digit code.
- **Rules from X-11 and X-12:**
  - codes expire after **10 minutes**;
  - the attempts-left count shows after 3 wrong tries, and the code is dead after **5**;
  - a new code cancels the previous one for the same purpose;
  - **3 sends per phone per hour** (counted across purposes, per business);
  - **at least 60 seconds** between sends.
- **No enumeration:** `password-reset/request` always answers the same way and takes similar time. It creates no code and sends no SMS for unknown phones, but counts toward the limits.
- **Sending:** the code goes out as a `Notification` through the outbox (ADR-0001 §6), using the "Phone code" template. The plaintext code exists only in the notification payload, which is scrubbed after sending and never logged.

### 5. Endpoints (M1)

All paths are under `/api/v1`. POSTs follow the idempotency rules in §8.

| Endpoint | Purpose |
| --- | --- |
| `POST /auth/login` | X-10. `{phone, password}` returns `{access, user}` and sets the cookie. Errors are always `invalid_credentials` with "Phone number or password is incorrect". A suspended user gets `account_suspended` **only after a correct password**, with the business support phone. |
| `POST /auth/refresh` | Rotate the cookie and return a new access token |
| `POST /auth/logout` | Revoke the current session and clear the cookie |
| `POST /auth/password-reset/request` | X-11 |
| `POST /auth/password-reset/verify` | X-12. `{phone, code}` returns a single-use `reset_token` (10 minutes). **Not in the design doc's list.** X-12 must show "attempts left" as soon as the sixth digit is typed, so the code has to be checked before X-13. |
| `POST /auth/password-reset/confirm` | X-13. `{reset_token, password}` signs the user in and revokes all other sessions |
| `POST /auth/password/change` | `{current_password, new_password}` revokes other sessions |
| `GET /auth/invitations/{token}` | X-14 details: business name, role label, phone. 410 `invitation_expired` or `invitation_used`. |
| `POST /auth/invitations/{token}/send-code` | X-14 "Send code" |
| `POST /auth/invitations/{token}/verify` | X-12 in the invitation flow; returns a single-use `setup_token` |
| `POST /auth/invitations/accept` | X-13 in the invitation flow. `{setup_token, password}` creates the user as phone-verified, adds branch memberships, signs them in and marks the invitation accepted. |
| `POST /me/pin` | The PIN step after X-13 (owner answer Q1). `{pin}` sets the first PIN. Changing an existing PIN (S-30, M3) will also need the current PIN or password. |
| `GET /me` | The signed-in user, rights and branches |
| `GET /me/branches` | S-01 data |
| `POST /console/invitations` | Minimal invite form. Owner or manager; roles `manager`, `accountant`, `staff` only. |
| `GET /console/invitations` | List pending invitations |
| `POST /console/invitations/{id}/resend` | Resend an invitation |
| `POST /console/invitations/{id}/cancel` | Cancel an invitation |
| `POST /staff/devices` | S-02 register this device |
| `GET /devices/current` | X-15: device, branch, lock state and roster, identified by the device cookie |
| `POST /auth/pin-switch` | X-15 |
| `GET /console/sessions` | List sessions (owner and manager) |
| `POST /console/sessions/{id}/revoke` | Sign a session out |
| `GET /console/devices` | List registered devices |
| `POST /console/devices/{id}/remove` | Remove a device |

`POST /auth/register` and `verify-phone` are **not built in M1** (owner answer Q2). They come with C-04 and C-05 in M9.

### 6. Invitations

- `Invitation(TenantModel)` has phone, first and last name, role, the three rights, `invited_by`, token_hash, expires_at (**7 days**), accepted_at, cancelled_at and `sent_count`. Branches are held in an explicit `InvitationBranch(TenantModel)` link table.
- The token is 32 random bytes, URL-safe, stored as SHA-256. The link is `https://{business host}/invite/{token}`, and that route renders X-14.
- **Who can invite in M1:** owners and managers can invite `manager`, `accountant` and `staff`. Owners inviting owners comes in **M5** with SMS confirmation (owner answer Q7); riders come in M9.
- **Refused:**
  - a phone that already has an account in this business ("A phone number already registered in this business is refused"), both at invite time and at accept time;
  - a second pending invitation for the same phone (the first is resent instead).
- **Plan limits are not checked** (`TODO(decision): plan-limits`, D-28).
- **SMS:** the invitation SMS uses the catalogue text: "{business} invited you to join as {role}. Set up your account: {link}".

### 7. Registered devices and PIN switching

- `Device(TenantModel)` has branch, name, registered_by, status (`active`, `locked`, `removed`), failed_pin_attempts, locked_at, last_seen_at and token_hash.
- **Registering (S-02):** an owner can register a device for any branch; a manager only for a branch they work at (as built in T06a: the design doc gives owners "everything in their business"). The server:
  - sets an `HttpOnly` cookie `das_device` (`Path=/api/v1`, `SameSite=Strict`, one year) holding a random 256-bit token stored hashed; JavaScript can never read it;
  - revokes the manager's own session on that device, as S-02 requires, leaving the device on X-15.
- **Roster (X-15):** `GET /devices/current` lists active users with a PIN who are members of the device's branch and have role `owner`, `manager` or `staff`. It shows names and initials; photos are D-45.
- **PIN switch:** `POST /auth/pin-switch {user_id, pin}` requires an active device cookie. On success it:
  - creates a `kind=pin` session bound to the device;
  - revokes any previous PIN session on that device;
  - resets the device's failure count.

  A wrong PIN increments the **device's** count and returns attempts left. At **5** the device becomes `locked`.
- **Unlocking (owner answer Q9):** an owner or manager of that branch signs in with phone and password on the locked device (`POST /auth/login` with the device cookie present). That unlocks it, and the unlock is audited. An Unlock button on A-42 follows in M5.
- **Idle lock:** after 5 idle minutes, the client calls `/auth/logout` for the PIN session and returns to X-15. The server doesn't track idleness.
- **Removing a device (A-42):** sets it to `removed` and revokes every session bound to it at once.
- **PINs:** 4 digits, hashed with Django's hasher, and they work only through `pin-switch`. Common PINs (`0000`, `1234` and the like) are refused, and the list lives in code.

### 8. Idempotency on auth endpoints

`Idempotency-Key` is **required** on authenticated mutating POSTs (§6.5). On the anonymous auth endpoints (login, refresh, password reset, invitation steps, pin-switch) it is **optional**. Those endpoints are safe to repeat or are protected by throttles and single-use tokens, and a failed first attempt must not block a retry. When a key is sent, it is stored per business, anonymous, IP and key.

### 9. Throttles

Throttles are keyed by business plus IP or user (or phone where stated). Rates live in settings; these are the starting values:

| Scope | Rate |
| --- | --- |
| Login | 10 per 15 min per business+phone; 30 per 15 min per business+IP |
| Code sends | 3 per hour per business+phone (spec); 20 per hour per business+IP |
| Code checks | 5 attempts per code (spec); 30 per 15 min per business+IP |
| PIN switch | 5 wrong tries per device lock it (spec); 30 per 15 min per business+IP |
| Authenticated default | 300 per minute per business+user |
| Anonymous default | 60 per minute per business+IP |

A throttled request returns 429 with the envelope code `throttled` and a `retry_after` value in seconds for the X-screens countdown ("Too many attempts. Try again in N minutes.").

### 10. Audit

Every mutating action writes an `AuditLog` row with actor, action, object, before and after values, IP and device. In M1 that covers login, logout, password reset and change, invitation create, resend, cancel and accept, PIN set, device register, remove and unlock, pin-switch, and session revoke. Codes, tokens, PINs and passwords never appear in before or after values.

## Consequences

- Sign-out is immediate everywhere, at the cost of one session lookup per request.
- A person who works at two laundries has two accounts, as the design doc says. Each address has its own cookies.
- `password-reset/verify` and the invitation `verify` and `send-code` endpoints are additions to the design doc's endpoint list. They are additive, and `openapi.yaml` records them.

## Alternatives rejected

- **JWT refresh tokens with simplejwt's blacklist:** its tables aren't tenant-scoped, and they give no per-device session list.
- **Django session cookies for everything:** the design explicitly asks for an in-memory access token and a refresh cookie, and later Android builds use the same token API.
- **PIN stored per device:** contradicts X-15, S-30 and A-41 (D-25).
