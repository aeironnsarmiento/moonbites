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

create table if not exists public.recipe_admins (
  email text primary key check (email = lower(email)),
  created_at timestamptz not null default timezone('utc', now())
);

alter table public.recipe_admins enable row level security;

revoke all on table public.recipe_admins from anon, authenticated, public;

create or replace function public.is_recipe_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.recipe_admins
    where email = lower(coalesce(auth.jwt() ->> 'email', ''))
  );
$$;

revoke execute on function public.is_recipe_admin() from anon, public;
grant execute on function public.is_recipe_admin() to authenticated;

alter table public.recipe_imports enable row level security;

drop policy if exists "Recipe imports are publicly readable" on public.recipe_imports;
create policy "Recipe imports are publicly readable"
  on public.recipe_imports
  for select
  to anon, authenticated
  using (true);

drop policy if exists "Recipe admins can insert recipe imports" on public.recipe_imports;
create policy "Recipe admins can insert recipe imports"
  on public.recipe_imports
  for insert
  to authenticated
  with check (public.is_recipe_admin());

drop policy if exists "Recipe admins can update recipe imports" on public.recipe_imports;
create policy "Recipe admins can update recipe imports"
  on public.recipe_imports
  for update
  to authenticated
  using (public.is_recipe_admin())
  with check (public.is_recipe_admin());

create or replace function public.hook_allow_recipe_admin_signup(event jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  requested_email text;
begin
  requested_email := lower(coalesce(event->'user'->>'email', ''));

  if exists (
    select 1
    from public.recipe_admins
    where email = requested_email
  ) then
    return '{}'::jsonb;
  end if;

  return jsonb_build_object(
    'error',
    jsonb_build_object(
      'http_code', 403,
      'message', 'This Google account is not approved for Moonbites admin access.'
    )
  );
end;
$$;

grant execute on function public.hook_allow_recipe_admin_signup(jsonb)
  to supabase_auth_admin;
revoke execute on function public.hook_allow_recipe_admin_signup(jsonb)
  from anon, authenticated, public;

-- Seed admins manually after applying this schema, for example:
-- insert into public.recipe_admins (email) values ('admin@example.com')
-- on conflict (email) do nothing;
