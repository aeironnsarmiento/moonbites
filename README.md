# Moonlake Cookbook (Moonbites)

A modern recipe extractor and manager built with Vite + React + Chakra UI (frontend) and FastAPI + Supabase (backend).  
Paste a recipe URL, extract and normalize the recipe, save to Supabase, and browse/search your collection.

---

## Features

- Paste a recipe URL and extract structured recipe data (name, ingredients, steps, yield, time, nutrition, cuisine)
- Normalizes and saves recipes to Supabase (PostgreSQL)
- Paginated recipe list with detail view
- Chakra UI theming with custom accent color (`#f0f4e3`)
- FastAPI backend with clean service/repository structure
- React Query for fast, cached recipe browsing
- Fully component-based frontend with per-component SCSS

## Backend CORS

Set the production backend CORS origin to the deployed frontend domain:

```env
BACKEND_CORS_ORIGINS=https://moonbites-blue.vercel.app
```

When `BACKEND_CORS_ORIGINS` is not set, the backend allows only the local Vite
development origins.

## Supabase Auth and RLS

Saved recipes are publicly readable. Creating, importing, favoriting, and editing
recipes requires an admin Google account.

Frontend env:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your-publishable-key
```

Backend env:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=your-publishable-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
ADMIN_EMAILS=admin@example.com,second-admin@example.com
```

Supabase setup:

1. Enable Google provider in Supabase Auth.
2. Apply `backend/supabase_schema.sql`.
3. Insert lowercase admin emails into `public.recipe_admins`.
4. Configure `public.hook_allow_recipe_admin_signup` as the Auth
   `Before User Created` Postgres hook.
