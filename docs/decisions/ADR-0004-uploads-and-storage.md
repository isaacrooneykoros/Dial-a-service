# ADR-0004: Uploads and private file storage

- **Status:** Accepted under the approved M1 plan (T08); owner decisions D-24 (an `Upload` table) and D-48 (limits)
- **Date:** 2026-10-01
- **Sources:** design doc ("Files are per business", Hosting: Cloudflare R2 private bucket), `10-screens-shared.md` (photos resized on the phone to about 300 KB, uploaded in the background), kickoff T08

## Decision

### Flow

1. The app asks for an upload: `POST /api/v1/uploads {content_type, size}`.
2. The server records a `core.Upload` row (`pending`) and returns a short-lived URL to `PUT` the file to, with the headers to send. The file goes straight to storage, not through Django (production).
3. The app uploads the bytes, then confirms: `POST /api/v1/uploads/{id}/complete`. The server checks that the stored object exists with the declared size and type, and marks the row `uploaded`.
4. Later records (order photos in M3, condition notes, tickets, rider documents) refer to the `Upload` by ID. Only `uploaded` rows may be used.

### Rules

- **Keys always start with the business ID:** `{business_id}/uploads/{upload_id}.{ext}`. A key never contains anything the client chose.
- **Types:** `image/jpeg`, `image/png`, `image/webp` only. **Size:** at most 5 MB (D-48; phones resize to about 300 KB first).
- **Upload URLs live 5 minutes.** Download URLs (signed, for viewing photos) arrive with the screens that show photos (M3); they will also be issued only after checking the business.
- **Private:** the bucket is never public.

### Storage adapters (`STORAGE_BACKEND`)

| Setting | Used for | How |
| --- | --- | --- |
| `r2` | Staging, production | Cloudflare R2 through boto3 (S3 API): presigned `PUT` URLs and `HEAD` on complete. Configured by `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`. |
| `local` (default) | Development, tests | A signed, expiring Django endpoint (`PUT /api/v1/uploads/{id}/content?token=...`) that writes into `backend/media_private/` (git-ignored). The token is signed with the secret key and binds the upload, the business and the expiry, so it is useless on another business's host or after 5 minutes. |

Production settings refuse `local`.

### Alternatives rejected

- **MinIO in Docker for local development:** an extra service to run on Windows; the local adapter gives the same flow with nothing to install.
- **Uploading through Django in production:** ties up web workers on slow 3G uploads and costs bandwidth; direct-to-R2 avoids both.
- **django-storages for presigned uploads:** it doesn't generate presigned `PUT` URLs for us; boto3 (approved) does it directly. django-storages stays available for server-side file access later.
