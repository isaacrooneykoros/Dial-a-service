# Dial A Service

A multi-tenant system that laundry businesses in Kenya rent monthly to run their counter, pickups, deliveries, payments and reports. Each business gets its own address (`{slug}.dialaservice.co.ke`), branding, staff and M-Pesa Till or Paybill.

## Where things are

| Path | What |
| --- | --- |
| `CLAUDE.md` | How code is written in this repository (binding) |
| `docs/design/` | Design doc, screen specs and diagrams (the source of truth) |
| `docs/decisions/` | Architecture decisions (ADRs) and open decisions |
| `docs/plans/` | Milestone plans |
| `backend/` | Django REST API (from Milestone 1, task T01b) |
| `frontend/` | React + TypeScript app (from Milestone 1, task T09a) |

## Run it locally on Windows

You need Python 3.12, Node 22 (22.22.2 or newer) and Git. Use PowerShell. The development database is a Neon branch; set it up once with [`docs/ops/neon-dev.md`](docs/ops/neon-dev.md).

### 1. Backend (first time)

From `backend\`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements\dev.txt
Copy-Item .env.example .env
```

Open `backend\.env` and fill in the values. Each line in `.env.example` says what it is for. Then follow `docs/ops/neon-dev.md`:
- it has you set `DATABASE_MIGRATION_URL` in `.env` yourself (never paste it anywhere else);
- `python -m scripts.db.setup_roles` then creates the app roles and writes `DATABASE_URL` and `PLATFORM_DATABASE_URL` into `.env`.

Then create the tables and the sample businesses:

```powershell
.\scripts\migrate.ps1          # runs migrations as dial_owner
python manage.py seed_dev       # two businesses with logins (prints them)
```

### 2. Frontend (first time)

From `frontend\`:

```powershell
npm ci
```

### 3. Every day

Two PowerShell windows:

```powershell
# window 1, in backend\
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

```powershell
# window 2, in frontend\
npm run dev
```

Open Chrome or Edge (they send `*.localhost` to your own computer):

| Business | Staff app | Console |
| --- | --- | --- |
| Mama Safi Laundry | <http://mamasafi.localhost:5173/staff> | <http://mamasafi.localhost:5173/console> |
| CleanPro Dry Cleaners | <http://cleanpro.localhost:5173/staff> | <http://cleanpro.localhost:5173/console> |

`seed_dev` prints every login. Each business has an owner, a manager and a staff member, on fake numbers `0700 000 1xx` (Mama Safi) and `0700 000 2xx` (CleanPro). They all have the password `dial-dev-pass`, and each has a PIN for counter devices. Running `seed_dev` again is safe: it resets those passwords and PINs and creates nothing twice.

Text messages (codes, invitations) aren't sent in development. They are printed in the `runserver` window, and that's where you read the 6-digit codes.

Background jobs run straight away inside the API while `REDIS_URL` is empty, so you don't need Redis or Celery to try the apps. To run the worker the way production does, set `REDIS_URL` and start `celery -A config worker --pool=solo -l info` (`--pool=solo` because the default pool doesn't run on Windows).

### 4. Try the M1 journey

1. **Branding:** open both businesses. Each shows its own name and colours.
2. **Log in:** go to the console at `mamasafi.localhost:5173/console` and log in as the owner (`0700 000 101`).
3. **Reset a password:** log out, choose **Forgot password?**, and use the code printed in the `runserver` window.
4. **Invite someone:** in the console, invite a person on a new number, for example `0711 000 001`, as **Shop staff** at Kilimani. Copy the `/invite/...` link from the SMS printed in the `runserver` window and open it. Then:
   - send the code;
   - enter the code from the `runserver` window;
   - set a password and a PIN.
5. **Register a counter device:** in the staff app, log in as the manager (`0700 000 102`) and choose **Register this device**. The device now opens on **Who's using this device?**; tap a name and enter that person's PIN.

### Checks

```powershell
# backendpytest
ruff check . ; ruff format --check . ; mypy .
python manage.py check_openapi

# frontendnpm run typecheck ; npm run lint ; npm run test
npm run build ; npm run budget
```

The backend tests run against a test database on Neon as the `dial_app` role, so row-level security is really exercised. They take several minutes.

### Adding a business by hand

Until self-serve sign-up arrives (M6):

```powershell
python manage.py create_business --name "Safi Wash" --slug safiwash --branch "Ngong Road" `
  --owner-phone 0712345678 --owner-first-name Grace --owner-last-name Wambui
```

It asks for the owner's password (and an optional PIN) without showing what you type. In development the address is `safiwash.localhost`; pass `--host` for another.
