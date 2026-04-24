# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Frontend (Vite + React):
- `npm run dev` — start the Vite dev server on port 5173. It proxies `/api` to `http://127.0.0.1:8000` (see `vite.config.ts`), so the backend must be running for API calls.
- `npm run build` — typecheck (`tsc -b`) then Vite build.
- `npm run lint` — ESLint over the repo.
- `npm run preview` — preview the production build.

Backend (FastAPI + Supabase):
- `npm run dev:backend:mac` / `dev:backend:win` — runs `uvicorn backend.main:app --reload` on port 8000. Requires `python-dotenv`, `fastapi`, `uvicorn`, `httpx`, `beautifulsoup4`, `supabase` (see `backend/requirements.txt`).
- Backend env vars live in `backend/.env` (loaded by `backend/app/core/config.py`): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, optional `SUPABASE_TABLE_NAME` (default `recipe_imports`), `BACKEND_CORS_ORIGINS`, `REQUEST_TIMEOUT_SECONDS`, and request header overrides.
- Schema for the Supabase table is in `backend/supabase_schema.sql`.
- `python -m pytest` — run the backend test suite.
## Architecture

The app is a recipe extractor: user pastes a URL, the backend fetches the page, pulls JSON-LD `@type: Recipe` blocks (with an HTML-ingredient-section fallback), normalizes them, dedupes by content fingerprint, and persists to Supabase. The frontend browses, edits overrides, and tracks "times cooked."

### Backend layers (`backend/app/`)
- `api/routes/` — FastAPI routers. `extract.py` exposes `POST /api/extract` and `GET /api/health`; `recipes.py` exposes CRUD on saved imports (`/api/recipes`, `/api/recipes/manual`, `/api/recipes/{id}`, `PATCH .../times-cooked`, `PATCH .../overrides`). The top-level `api/routes/__init__.py` mounts both under `/api`.
- `services/extractor.py` — HTTP fetch via `httpx` (with a 403 retry that adds `Sec-Fetch-*` headers), JSON-LD block parsing via BeautifulSoup, and the HTML ingredient-section scraper that only applies as a fallback when exactly one recipe node is found.
- `services/normalizer.py` — converts raw JSON-LD nodes to the `NormalizedRecipe` pydantic model: ISO-8601 durations → human strings, nutrition key remap, ingredient-sections flattening, and `build_recipe_fingerprint` / `dedupe_normalized_recipes` (SHA-256 over a canonical subset — name casefolded, ingredients, instructions, yield, cookTime, cuisine, nutrition).
- `repositories/recipe_imports.py` — all Supabase reads/writes. Saves dedupe by canonicalized submitted/final URL before insert. Reads always re-sanitize with `_sanitize_record` (validates pydantic, re-dedupes recipes, normalizes overrides). Manual recipes get a `manual://<uuid>` sentinel URL (see `is_manual_recipe_url`).
- `clients/supabase_client.py` — `lru_cache`d Supabase client; returns `None` when env vars are missing, which repositories translate into 503 responses.
- `schemas/extract.py` — pydantic models shared across routes, services, and repositories. Note the `_strip_ingredient_markers` validator that strips bullet/checkbox glyphs from ingredient strings on deserialization.

### Frontend layers (`src/`)
The frontend follows a strict service → controller → hook → page/component pipeline. Do not skip layers when adding a new API call:
- `services/` — thin `fetch` wrappers. `apiClient.ts` resolves the base URL: dev uses relative paths (proxied by Vite), prod uses `/_/backend` (Vercel experimental services, see `vercel.json`), override with `VITE_API_BASE_URL`. `recipeService.ts` / `extractService.ts` are the only places that know HTTP shapes.
- `controllers/` — transform API DTOs into UI models (`RecipeCardItem`, formatted dates, manual-URL rewriting) and apply client-side dedup via `utils/recipeDedup.ts`. Throw on invalid shapes.
- `hooks/` — React Query wrappers (`useRecipeList`, `useRecipeDetail`, `useCreateRecipe`, `useExtractRecipe`). Mutations invalidate both `["recipe-list"]` and `["recipe-detail", id]`. The global client in `main.tsx` has `staleTime: 5min`, `gcTime: 30min`, no refetch on focus.
- `pages/` and `components/` — consume hooks only. Each component has a colocated `.scss` file (per-component SCSS, not global).
- `layouts/MainLayout` wraps all routes; routing is in `App.tsx`.

Chakra theme (`src/styles/chakraTheme.ts`) defines the `brand` color scale anchored on accent `#f0f4e3`; prefer `colorScheme="brand"` over hardcoded colors.

### Cross-cutting concerns
- **Dedup happens in three places**: `normalizer.dedupe_normalized_recipes` (during extract), `recipe_imports._dedupe_recipe_import_records` (by URL, on list reads), and frontend `utils/recipeDedup.ts` (defensive, on controller boundary). When adding fields that should affect identity, update `build_recipe_fingerprint`.
- **Overrides** (`recipe_overrides_json`) are a `{ recipe_index_str: { ingredients: {row_str: text}, instructions: {row_str: text} } }` map. Keys are stringified ints; `_sanitize_recipe_overrides` enforces that shape on every read/write. Empty override entries are dropped, not stored.
- **Supabase not configured** surfaces as `RuntimeError("... not configured ...")` from repositories; routes translate the substring `"not configured"` into HTTP 503 and other `RuntimeError`s into 502.
- **Proxying in production**: the frontend calls `/_/backend/api/...`; Vercel rewrites route that to the FastAPI service defined in `vercel.json`.