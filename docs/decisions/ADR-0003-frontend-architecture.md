# ADR-0003: Frontend architecture

- **Status:** Accepted (owner, 2026-10-01)
- **Date:** 2026-10-01
- **Sources:** `CLAUDE.md` §4 and §6.8; `10-screens-shared.md` (design system, shared states, content and performance rules); `11-staff-app.md` (X-15, S-02); owner answers of 2026-10-01

## Context

One frontend build must serve every business, branded at run time. It has five route areas, works on mid-range Android phones over 3G (under 200 KB of gzipped JavaScript per app at first load), and keeps every string in translation files.

## Decision

### 1. One Vite app, five route areas

- React + TypeScript (`strict`, plus `noUncheckedIndexedAccess`), Vite and React Router.
- Route areas are **lazy-loaded chunks**, so a counter tablet never downloads console code:

  | Path | Area | M1 content |
  | --- | --- | --- |
  | `/staff/*` | Staff app | X-10 to X-13, X-15, S-02, a placeholder home |
  | `/console/*` | Business console | X-10 to X-13, a minimal invite form, a placeholder home |
  | `/rider/*` | Rider app | Placeholder (M9) |
  | `/` | Customer app | Placeholder (M9) |
  | `/o/:token` | Public order pages | Placeholder (M4) |
  | `/invite/:token` | Shared | X-14 flow, then the PIN step, then the right area for the role |

- Sign-in screens live at `/{area}/login`, `/{area}/forgot-password`, and so on. They are one shared component set, parameterised by area (the customer app adds "New here?" only from M9).
- CI checks a per-area bundle budget: the build fails if an area's first-load JS goes over 200 KB gzipped.

### 2. Start-up (X-01)

- `GET /business/config` and `GET /app/version` run in parallel, with an **8-second** timeout that then shows "Can't connect" with Retry.
- The last good config is cached in `localStorage` (it holds no secrets) and used when offline.
- **Branding** is applied by setting CSS variables on `:root`:
  - `--brand-primary` and `--brand-accent` come from config;
  - `--brand-on-primary` is computed for contrast (white or near-black);
  - the other tokens are fixed.
- **Version (X-02):** the build embeds `VITE_APP_VERSION`. If it's below the `minimum` for app `web`, X-02 blocks the app.
- **Maintenance (X-03):** a maintenance flag in config shows X-03, which checks again every 60 seconds.
- The last thing X-01 does is try a silent `POST /auth/refresh` to restore a session.

### 3. API client

- **Generation:** `npm run api:gen` runs `openapi-typescript` over `backend/openapi.yaml` into `src/api/schema.d.ts`. `openapi-fetch` gives a typed client in `src/api/client.ts`, and CI fails if the generated file is out of date.
- **Middleware**, in order:
  1. `Authorization: Bearer` from the in-memory token store;
  2. `Accept-Language` from i18n;
  3. `Idempotency-Key` on mutating requests: generated once per user action and **reused on retries** of that action, as the shared "Submitting" state requires;
  4. on 401, a **single-flight** refresh (many requests share one refresh), then one retry; if refresh fails, go to X-10 with `returnTo` and keep drafts;
  5. error envelope parsing into a typed `ApiError {code, message, fields, requestId, retryAfter}`.
- **TanStack Query** handles server state: no refetch on window focus for mutations, `retry` only for network errors, 20-item cursor pagination helpers.
- **Money** travels as strings, and no `number` type is used for amounts anywhere. A lint rule plus types enforce it (`Money = string` branded).

### 4. The token store

- The access token lives in a module-level variable, never in `localStorage` or `sessionStorage`.
- The refresh token is the httpOnly cookie, and the device token is the httpOnly `das_device` cookie (ADR-0002). JavaScript never sees either.
- The API is same-origin, so there is no CORS. In development, Vite proxies `/api` to Django at `http://127.0.0.1:8000` with `changeOrigin: false`, so Django sees `mamasafi.localhost` and resolves the business.

### 5. i18n

- i18next + react-i18next, with one JSON file per area and a shared namespace: `src/i18n/en/{shared,staff,console,…}.json`.
- Keys are screen-ID namespaced: `"X-10.button.log_in"`, `"X-15.error.wrong_pin"`. Shared state components use `shared.*`.
- **Swahili (owner answer Q5):** the `sw` files exist but stay empty, and `fallbackLng: "en"`. Nothing is shown untranslated as a raw key. When Swahili is wanted, only the `sw` files are filled.
- A test fails if any `.tsx` file contains a user-facing string literal outside `t()` (checked with an ESLint rule) or a key that isn't in `en`.
- **Wording (owner answer Q5):** strings the specs give are used exactly. Missing ones are written by me following the content rules (plain, "you" and "we", say what to do next) and listed in the task report for you to see.

### 6. Design tokens and styling

- `src/styles/tokens.css` defines every colour token from the Screens tab as CSS variables, plus the type scale, 4-px spacing, radii (8 for controls, 12 for cards, full for chips), and one shadow for sheets and the sticky bar.
- **Tailwind CSS** (current stable version at scaffold time) maps its theme to those variables, so `bg-brand-primary` follows the business's brand. No raw hex values appear in components; lint enforces this.
- **Fonts:** Plus Jakarta Sans (headings) and Inter (body) as self-hosted WOFF2 files (SIL OFL) in `src/styles/fonts/`, with `font-display: swap` and tabular figures for money and weights.
- **Icons:** `lucide-react`, 24 px, stroke 1.75. Icon-only buttons need an `aria-label` (lint rule).
- Motion only as the spec lists, and switched off under `prefers-reduced-motion`.

### 7. Shared UI kit and shared states (`src/components/`)

- **M1 builds** what the M1 screens need, each with loading, disabled and error variants:
  - Button (primary, secondary, text, danger), TextInput, PhoneInput (fixed +254), PasswordInput (show/hide);
  - CodeInput (6 boxes, paste, WebOTP), PinKeypad (4 digits);
  - Banner (info, warning, error, offline), Toast, ConfirmDialog, EmptyState, Skeleton, AppBar, ListRow.
- **Shared states** are components and hooks used by every screen:
  - `<FirstLoad>`: nothing for 200 ms, then skeletons;
  - `<RefreshBar>`;
  - `<ServerErrorBanner>` with Retry and the request ID;
  - `<OfflineBanner>` from `navigator.onLine` plus failed fetches;
  - `<Throttled>` with a countdown;
  - `<SessionExpired>` handling in the client;
  - X-02, X-03 and X-04 screens.
- Field errors from the envelope's `fields` map onto react-hook-form, with focus on the first bad field and input never cleared.

### 8. Forms and validation

- react-hook-form + zod schemas per screen.
- Client validation is for convenience only; the server's envelope is the authority.
- Phone input accepts the same forms as the backend (07…, 01…, 7…, 1…). The client validates the shape only; the server normalises.

### 9. Formatting (`src/lib/format.ts`)

- `formatMoney("1250.00", "KES")` gives "KSh 1,250". Whole shillings are shown where customers pay; the string input is parsed without floats.
- `formatWeight("6.40")` gives "6.4 kg".
- `formatDate`: "Thu 2 Oct", with the year only if it isn't this year, in the business's timezone.
- `formatTimeWindow`: "10am–12pm".
- `formatRecent`: "5 min ago" up to an hour, then the time.
- `formatPhone("+254712345678")` gives "0712 345 678", and `maskPhone` gives "0712 ••• 678".
- `formatName("Wanjiru", "Kamau")` gives "Wanjiru K.".
- Nothing else formats these values; lint bans `toFixed` and `toLocaleString` in `src/apps`.

### 10. Testing

- Vitest + Testing Library: `lib/` fully covered.
- API middleware is tested for single-flight refresh, idempotency-key reuse and envelope parsing.
- Component tests cover X-10 to X-15 and the PIN step.
- `fetch` is mocked with a small in-repo helper, not MSW, because MSW would be a new dependency.

## Consequences

- Every business's app is the same static build on Cloudflare Pages; a rebrand needs no rebuild.
- Route-level code splitting keeps the staff app small, even as the console grows.
- Anything outside `CLAUDE.md` §4 (a QR code library for S-44, for example) will come to you with its own ADR.

## Alternatives rejected

- **Separate builds per area:** more CI and deploy work for no user benefit, since lazy chunks give the same size result.
- **Tokens in `localStorage`:** readable by any injected script.
- **Runtime Google Fonts:** forbidden by the design (offline Android build, no third-party dependency).
