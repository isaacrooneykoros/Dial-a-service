# Staging deployment guide

How to put Dial A Service on **staging** (M1 task T12): Render + Neon + Cloudflare. It's a step-by-step guide for the owner. Nothing here has been deployed. Creating services, entering secrets and changing DNS are owner actions (`CLAUDE.md` §3).

> **Before the first staging deploy, two things must be settled:**
>
> 1. **D-52, how `/api/*` reaches Render with the business's address.** See step 6.
> 2. **No real business data on staging** until the platform admin has authenticator-app 2FA (D-35, Milestone 6). Use test businesses only.

Sources: design doc "Hosting" and "Environments"; ADR-0001 §5 (roles); ADR-0005 (CI); `render.yaml`; `.github/workflows/migrate-staging.yml`.

## What runs where

| Piece | Where | Database role |
| --- | --- | --- |
| API (`dial-api`) | Render web service, Frankfurt | `dial_app` (row-level security applies), Neon **pooled** host |
| Worker and schedules (`dial-worker`) | Render background worker | `dial_app`, pooled host |
| Platform admin (`dial-platform-admin`) | Render web service; serves only the health check until M6 | `dial_platform` (bypasses RLS), Neon **direct** host |
| Queue (`dial-redis`) | Render Key Value, private network only | — |
| Database | Neon project `dial-a-service`, branch `staging` | — |
| Migrations | GitHub Actions "Migrate staging", started by hand | `dial_owner`, direct host |
| Frontend | Cloudflare Pages (`frontend/`) | — |
| Files | Cloudflare R2, private bucket | — |
| DNS and TLS | Cloudflare (`dialaservice.co.ke`, `*.dialaservice.co.ke`) | — |

None of the Render services holds the owner role's password, so even a compromised API couldn't switch row-level security off (owner decision, 2026-10-03).

## 1. Neon: the staging branch and its roles

1. In the Neon Console (project `dial-a-service`), create a branch **`staging`** from `main`. It copies the `dial_owner` role and the `dialaservice` database.
2. Copy its **direct** connection string for `dial_owner` (connection pooling **off**, no `-pooler` in the host). Keep it in your password manager. This is `STAGING_DATABASE_MIGRATION_URL`.
3. Create the app roles on the staging branch. You choose their passwords here, because you'll need them for Render. In PowerShell, from `backend\` with the virtualenv active:

   ```powershell
   $env:DIAL_APP_PASSWORD = python -c "import secrets; print(secrets.token_urlsafe(32))"
   $env:DIAL_PLATFORM_PASSWORD = python -c "import secrets; print(secrets.token_urlsafe(32))"
   python -m scripts.db.setup_roles --admin-url "<paste the staging dial_owner URL>" --no-write-env
   ```

   Every line should say `[OK  ]`. Then save the two passwords in your password manager:

   ```powershell
   $env:DIAL_APP_PASSWORD
   $env:DIAL_PLATFORM_PASSWORD
   ```

   Close the PowerShell window afterwards, so they don't linger.
4. From these, build the two Render database URLs (same host as the owner URL, `?sslmode=require`):
   - **API and worker** `DATABASE_URL`: `dial_app`, on the **pooled** host (add `-pooler` after the endpoint ID):
     `postgresql://dial_app:<app password>@ep-xxxx-pooler.eu-central-1.aws.neon.tech/dialaservice?sslmode=require`
   - **Platform admin** `DATABASE_URL`: `dial_platform`, on the **direct** host:
     `postgresql://dial_platform:<platform password>@ep-xxxx.eu-central-1.aws.neon.tech/dialaservice?sslmode=require`

## 2. GitHub: the migration workflow

1. In the repository, open **Settings → Environments → New environment** and name it `staging`.
   - Optional: add yourself as a **required reviewer**, so every migration waits for your click.
2. In that environment, add the secret **`STAGING_DATABASE_MIGRATION_URL`** with the direct `dial_owner` URL from step 1.2.
3. Open **Actions → Migrate staging → Run workflow** (branch `main`). It lists pending migrations, applies them as `dial_owner`, and re-applies the grants.

Run it **before** deploying code that needs new migrations. Migrations must be backwards-compatible (add, don't rename or drop in the same release), so the running version keeps working while they run.

## 3. Cloudflare R2: private file storage

1. In **R2**, create a bucket named `dial-a-service-staging`. Keep it private: no public access, no custom domain.
2. In **R2 → Manage API tokens**, create a token with **Object Read & Write** on that bucket only. Note the **Access Key ID**, **Secret Access Key** and the **S3 endpoint** (`https://<account id>.r2.cloudflarestorage.com`).
3. Set a CORS rule on the bucket, so browsers can upload with the short-lived URLs the API hands out (ADR-0004):
   - allowed origins: `https://*.dialaservice.co.ke`;
   - methods: `PUT`;
   - headers: `Content-Type`.

## 4. Secrets to generate

Generate each of these once and keep them in your password manager:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"   # DJANGO_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(64))"   # OTP_HASH_KEY (a different value)
```

Sentry is optional: create a project and copy its DSN, or leave `SENTRY_DSN` empty.

## 5. Render: the services

1. **New → Blueprint** → connect the GitHub repository → Render reads `render.yaml`.
2. Fill in every value Render asks for (the `sync: false` keys):

   | Where | Key | Value |
   | --- | --- | --- |
   | Group `dial-staging-shared` | `DJANGO_SECRET_KEY`, `OTP_HASH_KEY` | From step 4 |
   | Group `dial-staging-shared` | `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY` | From step 3 |
   | Group `dial-staging-shared` | `SENTRY_DSN` | Optional |
   | `dial-api` and `dial-worker` | `DATABASE_URL` | The **dial_app pooled** URL |
   | `dial-platform-admin` | `DATABASE_URL` | The **dial_platform direct** URL |

3. Apply. Render builds each service. The API and the platform admin pass their health check at `/api/v1/health`.
   - Render's own addresses (`dial-api.onrender.com`) are allowed automatically through `RENDER_EXTERNAL_HOSTNAME`, and serve only the health check.
   - Any other path there answers "not found", because there's no business on that address.
4. Deploys then happen automatically once CI has passed on `main` (`autoDeployTrigger: checksPass`). Keep exactly **one** worker instance: it also runs the schedules.

The production settings refuse to start if anything unsafe is configured:
- debug mode on;
- a short or placeholder secret key;
- no allowed hosts;
- no Redis;
- storage other than R2;
- the console SMS sender, which would print codes into the logs.

Until the SMS gateway is chosen (D-08, Milestone 4), staging uses the **discard** sender: nothing is sent, printed or kept. So **codes and invitation links don't arrive on staging**. Sign in with accounts made with `create_business` (step 7), not with password reset or invitations.

## 6. Cloudflare: DNS and routing (needs D-52 first)

The design: every business address `{slug}.dialaservice.co.ke` serves the frontend from **Pages**, and `/api/*` on the same address goes to **Django on Render**. The API must receive the business's own address in the `Host` header, because that is how it knows which business a request is for (`CLAUDE.md` §6.1). It must also not be reachable around Cloudflare with a made-up address.

How Cloudflare hands `/api/*` to Render while keeping that address is **decision D-52** (`docs/decisions/OPEN.md`). Settle it before this step. The options are listed there.

What doesn't depend on D-52:

1. Add the zone `dialaservice.co.ke` to Cloudflare. Turn on **SSL/TLS → Full (strict)** and **Always Use HTTPS**.
2. Create the **Pages** project from `frontend/`:
   - build command `npm ci && npm run build`;
   - output directory `dist`;
   - environment variables `NODE_VERSION=22.23.2` and `VITE_APP_VERSION=<release version>`.
   It's a single-page app: unknown paths must serve `index.html`.
3. Point `*.dialaservice.co.ke` at the Pages project (proxied), with the API route from D-52 in front of it.
4. **Don't** create DNS for `admin.dialaservice.co.ke` yet. The platform admin arrives in M6, behind **Cloudflare Access** (only your team's emails) and 2FA (D-35).

## 7. First staging business

There's no `seed_dev` on staging: it refuses production settings by design. Create a test business from the Render **Shell** of `dial-api`:

```bash
python manage.py create_business --name "Staging Laundry" --slug staging-laundry \
  --host staging-laundry.dialaservice.co.ke --branch "Main branch" \
  --owner-phone 0700000901 --owner-first-name Test --owner-last-name Owner
```

It asks for the owner's password without showing it. Then open `https://staging-laundry.dialaservice.co.ke/console` and log in.

## Checklist before real businesses

- [ ] D-35: platform admin with authenticator-app 2FA, behind Cloudflare Access (M6)
- [ ] D-08: SMS gateway and sender ID registered, and its backend set (M4)
- [ ] D-52: API routing decided and tested: a forged `Host` sent straight to Render must not resolve a business
- [ ] Backups: Neon point-in-time recovery checked, and one restore tested (M7)
- [ ] Monitoring and alerts (M7)
