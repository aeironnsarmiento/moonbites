# Moonbites

Moonbites is a recipe extractor and cookbook app. Paste a recipe URL, let the
FastAPI backend extract structured recipe data, save it to Supabase, then browse
and edit the saved collection in a Vite + React frontend.

Saved recipes are public to read. Creating, importing, favoriting, and editing
recipes require an approved Google admin account through Supabase Auth.

## Features

- Import recipes from URLs using JSON-LD `Recipe` data.
- Fall back to HTML ingredient-section scraping when a page has one recipe node.
- Add manual recipes when no source URL exists.
- Browse saved recipes with pagination, sorting, cuisine filters, favorites, and detail pages.
- Edit recipe metadata plus ingredient/instruction overrides without mutating the original extracted text.
- Track default servings and times cooked.
- Deduplicate recipes by canonical URL and recipe content fingerprint.

## Architecture

### Backend

The backend is a FastAPI app under `backend/app`.

- `api/routes/` exposes extraction, auth, health, and saved recipe endpoints under `/api`.
- `services/extractor.py` fetches pages with `httpx`, parses JSON-LD with BeautifulSoup, and applies the ingredient fallback.
- `services/normalizer.py` converts raw recipe nodes into Pydantic models and handles recipe fingerprinting/deduplication.
- `repositories/recipe_imports.py` owns Supabase reads and writes, record sanitization, overrides, manual recipes, and list filtering.
- `clients/supabase_client.py` builds service-role, publishable, and user-scoped Supabase clients.
- `schemas/extract.py` defines API and persistence models shared across routes, services, and repositories.

### Frontend

The frontend lives in `src` and uses React, Vite, Chakra UI, and React Query.

- `services/` contains thin HTTP wrappers and Supabase Auth setup.
- `controllers/` converts API DTOs into UI models.
- `hooks/` owns React Query calls and shared UI state.
- `pages/` and `components/` render the app and consume hooks.
- `layouts/MainLayout` provides the shared shell; routes are defined in `App.tsx`.

In development, Vite proxies `/api` to the backend at `http://127.0.0.1:8000`.
In production, the frontend calls `/_/backend/api/...` through Vercel
experimental services.

## Local Setup

Install frontend dependencies:

```bash
npm install
```

Install backend dependencies:

```bash
python3 -m pip install -r backend/requirements.txt
```

For backend tests, also install:

```bash
python3 -m pip install -r backend/requirements-dev.txt
```

Create a root `.env` for frontend Supabase Auth:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your-publishable-key
```

Create `backend/.env` for the FastAPI service:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=your-publishable-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

Optional backend env vars:

```env
SUPABASE_TABLE_NAME=recipe_imports
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
REQUEST_TIMEOUT_SECONDS=15.0
YOUTUBE_API_KEY=your-youtube-data-api-key
```

## Supabase Auth and RLS

Moonbites uses Supabase Google OAuth for admin login and PostgreSQL row-level
security for write protection.

Supabase setup:

1. Enable the Google provider in Supabase Auth.
2. Apply `backend/supabase_schema.sql`.
3. Configure `public.hook_allow_recipe_admin_signup` as the Supabase Auth
   `Before User Created` Postgres hook.
4. Grant admin access with the local CLI.

Example admin grant:

```bash
python3 -m backend.scripts.admins grant admin@example.com
```

List or revoke admins:

```bash
python3 -m backend.scripts.admins list
python3 -m backend.scripts.admins revoke admin@example.com
```

Use the publishable key in browser/frontend env vars. Keep the service-role key
server-only in `backend/.env`.

## Running Locally

Start the backend:

```bash
npm run dev:backend:mac
```

On Windows:

```bash
npm run dev:backend:win
```

Start the frontend:

```bash
npm run dev
```

Open the app at `http://localhost:5173`.

Admin login is available at:

```text
http://localhost:5173/login
```

The login link is intentionally not shown in the header. After a successful
admin login, write controls such as `Create Recipe`, favorite toggles, and edit
buttons become visible.

## Commands

```bash
npm run dev              # Start Vite frontend on port 5173
npm run dev:backend:mac  # Start FastAPI backend on port 8000 for macOS/Linux
npm run dev:backend:win  # Start FastAPI backend on port 8000 for Windows
npm run build            # Typecheck and build frontend
npm run lint             # Run ESLint
npm run test             # Run frontend tests
python3 -m pytest        # Run backend tests
npm run preview          # Preview production frontend build
```

## Instagram Reel Import

Moonbites can import a recipe from a public Instagram Reel's caption, a
caption-linked recipe page, or (as a bounded fallback) the creator's own
public recipe site. This path is off by default and only activates once the
environment below is fully configured; it is designed to fail closed (report
`provider_unavailable` and save nothing) rather than fall back to paid usage.

### Required environment (`backend/.env`)

```env
INSTAGRAM_APIFY_TOKEN=your-dedicated-account-token
INSTAGRAM_REEL_ACTOR_ID=xMc5Ga1oCONPmWJIa
INSTAGRAM_PROFILE_ACTOR_ID=dSCLg0C3YEZ83HzYX
INSTAGRAM_REEL_ACTOR_BUILD=0.0.542
INSTAGRAM_PROFILE_ACTOR_BUILD=0.0.580
INSTAGRAM_REEL_MAX_CHARGE_USD=0.0073
INSTAGRAM_PROFILE_MAX_CHARGE_USD=0.0026
INSTAGRAM_MONTHLY_USAGE_STOP_USD=4.5
```

The Actor IDs, builds, and charge caps above are the exact values this
codebase was verified against; do not change them without re-verifying a
canary run and updating both the env defaults in
[`backend/app/core/config.py`](backend/app/core/config.py) and the pinned
constants in
[`backend/app/services/instagram/apify.py`](backend/app/services/instagram/apify.py).
The application also refuses to start an Actor for any Actor ID outside this
exact allowlist, regardless of configuration.

### Dedicated Apify account (zero-cash requirement)

Instagram acquisition runs through a **dedicated Apify account that has no
payment method or pay-as-you-go path attached** — never the personal or
organizational account used for anything else:

1. Create the account on Apify's Free plan only. Do not add a card.
2. Confirm the account shows the fixed $5/month included-credit maximum with
   no upgrade path available.
3. Generate an API token scoped to account reads and Actor Run access on
   only the two Actor resources above. Actor Run access unavoidably implies
   a webhook-management scope in Apify's permission model; this is an
   accepted exception — Moonbites never creates or uses a run webhook.
4. Before every Actor start, the app re-reads this account's live plan tier,
   credit/limit figures, and current usage, and refuses to start if the
   plan drifted off Free, the $5 maximum changed, or usage has reached
   `INSTAGRAM_MONTHLY_USAGE_STOP_USD` ($4.50, below the $5 hard limit as a
   safety margin against reporting lag).

If Apify ever changes this account's contract (adds a payment prompt, changes
the free limit, or requires broader token scopes than above), treat that as a
blocking change: do not relax the safety margin to route around it.

### Schema — apply before deploying Instagram-aware code

Additive schema changes must be applied and verified **before** deploying any
backend build that reads `linked_recipe_url` or the private job tables.
Rolling those out in the other order means the new code queries columns or
tables that do not exist yet.

1. **Preflight audit (read-only, run first):** query for existing duplicate
   `submitted_url` or `final_url` values and any rows that are already the
   same canonical Instagram Reel identity in different URL forms. If any
   are found, stop and resolve them by hand — the schema step below
   intentionally skips adding the `submitted_url`/`final_url` unique
   constraints (with a `RAISE NOTICE`, not an error) rather than failing the
   whole apply, and Instagram import safety depends on both constraints
   actually being present. Never delete or merge rows automatically.
2. **Apply** [`backend/supabase_schema.sql`](backend/supabase_schema.sql).
   It is idempotent and safe to re-run.
3. **Verify postconditions** before deploying code that depends on them:
   - `recipe_imports.linked_recipe_url` exists, is nullable, and carries no
     uniqueness constraint.
   - Both `recipe_imports_submitted_url_key` and `recipe_imports_final_url_key`
     unique constraints are present (see step 1 if either is missing).
   - `public.search_recipe_imports` returns `linked_recipe_url` in its
     result columns.
   - `public.instagram_import_jobs` and `public.instagram_provider_admission`
     exist, have row-level security enabled, and grant **no** access to
     `anon`/`authenticated` — only the service-role backend reads or writes
     them.
   - The partial unique index enforcing one active job per
     `(owner_email, canonical_reel_url)` exists on `instagram_import_jobs`.

   `backend/tests/repositories/test_supabase_schema.py` asserts the SQL text
   itself contains all of the above; treat a passing `python3 -m pytest
   backend/tests/repositories/test_supabase_schema.py` as necessary but not
   sufficient — it does not confirm the schema was actually applied to a
   given database.

### Job cleanup and thumbnail audits

Neither script mutates anything unless you pass `--apply`; without it, both
report only what they *would* do.

```bash
# Terminalize stale jobs, reconcile the provider-admission slot, and delete
# expired terminal job rows. Run this on a schedule (e.g. every 15 minutes).
python3 -m backend.scripts.cleanup_instagram_import_jobs
python3 -m backend.scripts.cleanup_instagram_import_jobs --apply

# Find (and optionally delete) managed thumbnail objects with no referencing
# recipe_imports row. Covers both tiktok/ and instagram/ storage paths.
python3 -m backend.scripts.audit_social_thumbnails
python3 -m backend.scripts.audit_social_thumbnails --apply
```

### Rollback

Disabling the Instagram import path is expand-only in reverse: unset
`INSTAGRAM_APIFY_TOKEN` (or any of the other `INSTAGRAM_*` env vars) and
redeploy. The backend fails closed on missing configuration before any Actor
start, so this alone stops all Instagram acquisition. Do **not** drop the
additive schema (`linked_recipe_url`, `instagram_import_jobs`,
`instagram_provider_admission`) as part of a rollback — those columns and
tables are backward-compatible with the pre-Instagram code path, and
existing non-Instagram rows and readers are unaffected by their presence.
Schema contraction, if ever needed, is separate, deliberate work done after
confirming no code references the columns being dropped.

### Live acceptance smoke

This is the only step in the Instagram import feature that makes real,
billable Apify calls and writes to a live database, and it should be run
once, deliberately, after every item above is configured and verified — not
as part of routine development or CI. It is intentionally **not** something
this assistant runs on its own: it requires the dedicated Apify token and a
target Supabase project to already be configured by a human, and it spends
real (small, capped) provider usage. Before running it, confirm the schema
postconditions above hold, and confirm current Apify usage is below $4.50.

Then submit each of the three representative Reels once each through a real
running instance of the app, let each durable job advance to a terminal
state, and confirm:

- [Caption-complete](https://www.instagram.com/reel/DZuzc9PNedT/): saves
  directly from the caption with no Profile Actor start.
- [Link-in-bio](https://www.instagram.com/reel/DcMelrnkfZe/): resolves via a
  caption link or the creator's profile, saves with `linked_recipe_url` set.
- [Comment-for-recipe](https://www.instagram.com/reel/Daa0ZKGOuZb/): resolves
  via Creator-site Lookup only, without any Instagram comment or DM.

Record the resulting job states, Actor run IDs, and elapsed time. A
creator-bio or caption content change since these were captured is
acceptance-data drift, not a regression — re-verify against the current
content before treating a mismatch as a bug. Closing the client mid-import
and resubmitting the exact same Reel URL should resume the same job rather
than starting a second Actor run.

## Deployment Notes

`vercel.json` defines two Vercel experimental services:

- `frontend` at `/`
- `backend` at `/_/backend`

In production, frontend API calls resolve to `/_/backend/api/...`.

Set production CORS to the deployed frontend domain:

```env
BACKEND_CORS_ORIGINS=https://your-frontend-domain.example
```

## Troubleshooting

### Login Works But Write Controls Do Not Appear

Check DevTools Network for `GET /api/auth/me`.

- `200`: backend recognized the admin session.
- `401`: Supabase session token is missing or invalid.
- `403`: logged-in Google email is not in `public.recipe_admins`.
- `503`: backend is missing `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, or `SUPABASE_SERVICE_ROLE_KEY`.

Also confirm:

- Root `.env` uses `VITE_SUPABASE_PUBLISHABLE_KEY=...`, not `VITE_SUPABASE_PUBLISHABLE_KEY=SUPABASE_PUBLISHABLE_KEY=...`.
- `backend/.env` uses the same Supabase project URL as root `.env`.
- `python3 -m backend.scripts.admins list` shows the logged-in Google email.
- The backend and frontend were restarted after env changes.

### API Calls Fail In Development

Run both servers. The frontend dev server only proxies `/api` when the backend is
running on `127.0.0.1:8000`.

### Supabase Not Configured

Backend repositories return a 503-style error when required Supabase env vars are
missing. Check `backend/.env`, restart the backend, then retry.
