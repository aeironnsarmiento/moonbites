create extension if not exists pgcrypto;

create table if not exists public.recipe_imports (
  id uuid primary key default gen_random_uuid(),
  submitted_url text not null,
  final_url text not null,
  page_title text,
  recipe_count integer not null default 0,
  times_cooked integer not null default 0,
  recipes_json jsonb not null,
  recipe_overrides_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

alter table public.recipe_imports
  add column if not exists times_cooked integer not null default 0;

alter table public.recipe_imports
  add column if not exists recipe_overrides_json jsonb not null default '{}'::jsonb;

create index if not exists recipe_imports_created_at_idx
  on public.recipe_imports (created_at desc);

create index if not exists recipe_imports_submitted_url_idx
  on public.recipe_imports (submitted_url);

alter table public.recipe_imports
  add column if not exists image_url text;

alter table public.recipe_imports
  add column if not exists is_favorite boolean not null default false;

alter table public.recipe_imports
  add column if not exists servings integer;

create index if not exists recipe_imports_is_favorite_idx
  on public.recipe_imports (is_favorite) where is_favorite = true;

create index if not exists recipe_imports_times_cooked_idx
  on public.recipe_imports (times_cooked desc);
