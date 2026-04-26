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
