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
