create extension if not exists pgcrypto;

create table if not exists public.recipe_imports (
  id uuid primary key default gen_random_uuid(),
  submitted_url text not null,
  final_url text not null,
  page_title text,
  times_cooked integer not null default 0,
  recipes_json jsonb not null,
  recipe_overrides_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

alter table public.recipe_imports
  add column if not exists times_cooked integer not null default 0;

alter table public.recipe_imports
  add column if not exists recipe_overrides_json jsonb not null default '{}'::jsonb;

alter table public.recipe_imports
  drop column if exists recipe_count;

create index if not exists recipe_imports_created_at_idx
  on public.recipe_imports (created_at desc);

create index if not exists recipe_imports_submitted_url_idx
  on public.recipe_imports (submitted_url);

alter table public.recipe_imports
  add column if not exists image_url text;

-- Server-managed durable copy of third-party thumbnails. This path is kept
-- internal; public API responses continue to expose only image_url.
alter table public.recipe_imports
  add column if not exists image_storage_path text;

insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values (
  'recipe-thumbnails',
  'recipe-thumbnails',
  true,
  5242880,
  array['image/jpeg', 'image/png', 'image/webp', 'image/avif']
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

alter table public.recipe_imports
  add column if not exists is_favorite boolean not null default false;

alter table public.recipe_imports
  add column if not exists servings integer;

-- Admin-attached video for recipes whose own source cannot be embedded.
-- Kept separate from submitted_url/final_url so provenance is never rewritten.
alter table public.recipe_imports
  add column if not exists fallback_video_url text;

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

grant usage on schema public to anon, authenticated;
grant select on public.recipe_imports to anon, authenticated;
grant insert, update, delete on public.recipe_imports to authenticated;

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

drop policy if exists "Recipe admins can delete recipe imports" on public.recipe_imports;
create policy "Recipe admins can delete recipe imports"
  on public.recipe_imports
  for delete
  to authenticated
  using (public.is_recipe_admin());

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

-- ---------------------------------------------------------------------------
-- Optimization migration: indexes, UNIQUE, generated cuisines column, RPCs.
-- Idempotent. URL UNIQUE constraints are skipped when legacy duplicates exist;
-- resolve duplicates and rerun this schema to add the skipped constraint(s).
-- ---------------------------------------------------------------------------

create index if not exists recipe_imports_page_title_idx
  on public.recipe_imports (page_title);

create index if not exists recipe_imports_final_url_idx
  on public.recipe_imports (final_url);

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'recipe_imports_submitted_url_key'
  ) then
    if exists (
      select 1
      from (
        select submitted_url
        from public.recipe_imports
        group by submitted_url
        having count(*) > 1
      ) duplicates
    ) then
      raise notice
        'Skipping recipe_imports_submitted_url_key; duplicate submitted_url values exist. Resolve duplicates and rerun this schema.';
    else
      alter table public.recipe_imports
        add constraint recipe_imports_submitted_url_key unique (submitted_url);
    end if;
  end if;
end$$;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'recipe_imports_final_url_key'
  ) then
    if exists (
      select 1
      from (
        select final_url
        from public.recipe_imports
        group by final_url
        having count(*) > 1
      ) duplicates
    ) then
      raise notice
        'Skipping recipe_imports_final_url_key; duplicate final_url values exist. Resolve duplicates and rerun this schema.';
    else
      alter table public.recipe_imports
        add constraint recipe_imports_final_url_key unique (final_url);
    end if;
  end if;
end$$;

create or replace function public.recipe_cuisine_bucket(value text)
returns text
language sql
immutable
set search_path = public
as $$
  with normalized as (
    select btrim(
      regexp_replace(
        replace(
          regexp_replace(
            lower(btrim(coalesce(value, ''))),
            '[^[:alnum:]_[:space:]-]',
            ' ',
            'g'
          ),
          '-',
          ' '
        ),
        '[[:space:]]+',
        ' ',
        'g'
      )
    ) as key
  )
  select case
    when key = '' then null
    when key in (
      'american',
      'america',
      'north american',
      'north america',
      'united states',
      'united states of america',
      'usa',
      'us',
      'u s',
      'u s a',
      'southern',
      'southern us',
      'southern united states',
      'cajun',
      'creole',
      'tex mex',
      'new england',
      'southwestern'
    ) then 'american'
    when key in (
      'british',
      'english',
      'england',
      'uk',
      'u k',
      'united kingdom',
      'great britain',
      'scottish',
      'scotland',
      'welsh',
      'wales',
      'irish',
      'ireland'
    ) then 'british'
    when key in ('chinese', 'china', 'szechuan', 'sichuan', 'cantonese') then 'chinese'
    when key in ('french', 'france') then 'french'
    when key in ('greek', 'greece') then 'greek'
    when key in ('indian', 'india') then 'indian'
    when key in ('italian', 'italy') then 'italian'
    when key in ('japanese', 'japan') then 'japanese'
    when key in ('korean', 'korea', 'south korea') then 'korean'
    when key = 'mediterranean' then 'mediterranean'
    when key in ('mexican', 'mexico') then 'mexican'
    when key in ('middle eastern', 'middle east', 'levantine', 'levant') then 'middle eastern'
    when key in ('moroccan', 'morocco') then 'moroccan'
    when key in ('spanish', 'spain') then 'spanish'
    when key in ('thai', 'thailand') then 'thai'
    when key in ('vietnamese', 'vietnam') then 'vietnamese'
    else 'other'
  end
  from normalized;
$$;

create or replace function public.extract_recipe_cuisines(recipes jsonb)
returns text[]
language sql
immutable
set search_path = public
as $$
  with raw_values as (
    select value
    from jsonb_array_elements(
      case jsonb_typeof(recipes)
        when 'array' then recipes
        else '[]'::jsonb
      end
    ) recipe(node),
    lateral jsonb_array_elements_text(
      case jsonb_typeof(recipe.node->'recipeCuisine')
        when 'array' then recipe.node->'recipeCuisine'
        when 'string' then jsonb_build_array(recipe.node->'recipeCuisine')
        else '[]'::jsonb
      end
    ) cuisine(value)
  ),
  buckets as (
    select public.recipe_cuisine_bucket(value) as label
    from raw_values
  ),
  known as (
    select distinct label
    from buckets
    where label is not null and label <> 'other'
  )
  select case
    when exists (select 1 from known)
      then array(select label from known order by label)
    when exists (select 1 from buckets where label = 'other')
      then array['other']::text[]
    else '{}'::text[]
  end;
$$;

alter table public.recipe_imports
  add column if not exists cuisines text[]
  generated always as (public.extract_recipe_cuisines(recipes_json)) stored;

create index if not exists recipe_imports_cuisines_gin_idx
  on public.recipe_imports using gin (cuisines);

create or replace function public.cuisine_facets()
returns table(label text, count bigint)
language sql
stable
security invoker
set search_path = public
as $$
  select cuisine.label, count(*)::bigint
  from public.recipe_imports,
       lateral unnest(cuisines) as cuisine(label)
  group by cuisine.label
  order by cuisine.label;
$$;

grant execute on function public.cuisine_facets() to anon, authenticated;

create or replace function public.increment_times_cooked(
  p_id uuid,
  p_delta int
) returns setof public.recipe_imports
language sql
security invoker
set search_path = public
as $$
  update public.recipe_imports
     set times_cooked = greatest(0, times_cooked + p_delta)
   where id = p_id
  returning *;
$$;

create or replace function public.toggle_recipe_favorite(
  p_id uuid
) returns setof public.recipe_imports
language sql
security invoker
set search_path = public
as $$
  update public.recipe_imports
     set is_favorite = not is_favorite
   where id = p_id
  returning *;
$$;

create or replace function public.set_recipe_override(
  p_id uuid,
  p_recipe_key text,
  p_override jsonb
) returns setof public.recipe_imports
language sql
security invoker
set search_path = public
as $$
  update public.recipe_imports
     set recipe_overrides_json =
       case
         when p_override is null or p_override = '{}'::jsonb
           then coalesce(recipe_overrides_json, '{}'::jsonb) - p_recipe_key
         else jsonb_set(
           coalesce(recipe_overrides_json, '{}'::jsonb),
           array[p_recipe_key],
           p_override,
           true
         )
       end
   where id = p_id
  returning *;
$$;

grant execute on function public.increment_times_cooked(uuid, int) to authenticated;
grant execute on function public.toggle_recipe_favorite(uuid) to authenticated;
grant execute on function public.set_recipe_override(uuid, text, jsonb) to authenticated;

-- ---------------------------------------------------------------------------
-- Global recipe search: ranked, filtered, paginated search RPC.
-- Dropped before create because "create or replace" cannot change the
-- signature of a table-returning function on schema re-apply.
-- ---------------------------------------------------------------------------

drop function if exists public.search_recipe_imports(text, text, boolean, text, integer, integer);

create function public.search_recipe_imports(
  p_term text,
  p_cuisine text default null,
  p_favorite boolean default null,
  p_sort text default 'recent',
  p_limit integer default 10,
  p_offset integer default 0
) returns table (
  id uuid,
  submitted_url text,
  final_url text,
  page_title text,
  times_cooked integer,
  recipes_json jsonb,
  recipe_overrides_json jsonb,
  image_url text,
  is_favorite boolean,
  servings integer,
  fallback_video_url text,
  created_at timestamptz,
  total_count bigint
)
language sql
stable
security invoker
set search_path = public
as $$
  with patterns as (
    select
      lower(btrim(coalesce(p_term, ''))) as exact_term,
      replace(replace(replace(btrim(coalesce(p_term, '')), '\', '\\'), '%', '\%'), '_', '\_') as escaped_term
  ),
  matched as (
    select
      r.id,
      r.submitted_url,
      r.final_url,
      r.page_title,
      r.times_cooked,
      r.recipes_json,
      r.recipe_overrides_json,
      r.image_url,
      r.is_favorite,
      r.servings,
      r.fallback_video_url,
      r.created_at,
      case
        when lower(coalesce(r.recipes_json->0->>'name', '')) = p.exact_term
          or lower(coalesce(r.page_title, '')) = p.exact_term
          then 1
        when coalesce(r.recipes_json->0->>'name', '') ilike p.escaped_term || '%'
          or coalesce(r.page_title, '') ilike p.escaped_term || '%'
          then 2
        when coalesce(r.recipes_json->0->>'name', '') ilike '%' || p.escaped_term || '%'
          or coalesce(r.page_title, '') ilike '%' || p.escaped_term || '%'
          then 3
        else 4
      end as match_rank
    from public.recipe_imports r, patterns p
    where (
        coalesce(r.recipes_json->0->>'name', '') ilike '%' || p.escaped_term || '%'
        or coalesce(r.page_title, '') ilike '%' || p.escaped_term || '%'
        or exists (
          select 1
          from jsonb_array_elements(
            case jsonb_typeof(r.recipes_json)
              when 'array' then r.recipes_json
              else '[]'::jsonb
            end
          ) recipe(node)
          where exists (
            select 1
            from jsonb_array_elements_text(
              case jsonb_typeof(recipe.node->'ingredients')
                when 'array' then recipe.node->'ingredients'
                else '[]'::jsonb
              end
            ) ingredient(value)
            where ingredient.value ilike '%' || p.escaped_term || '%'
          )
          or exists (
            select 1
            from jsonb_array_elements_text(
              case jsonb_typeof(recipe.node->'recipeCuisine')
                when 'array' then recipe.node->'recipeCuisine'
                when 'string' then jsonb_build_array(recipe.node->'recipeCuisine')
                else '[]'::jsonb
              end
            ) cuisine(value)
            where cuisine.value ilike '%' || p.escaped_term || '%'
          )
        )
        or exists (
          select 1
          from unnest(r.cuisines) bucket(label)
          where bucket.label ilike '%' || p.escaped_term || '%'
        )
        or substring(lower(r.submitted_url) from '^https?://([^/]+)') ilike '%' || p.escaped_term || '%'
        or substring(lower(r.final_url) from '^https?://([^/]+)') ilike '%' || p.escaped_term || '%'
      )
      and (p_cuisine is null or r.cuisines @> array[p_cuisine])
      and (p_favorite is not true or r.is_favorite)
  )
  select
    m.id,
    m.submitted_url,
    m.final_url,
    m.page_title,
    m.times_cooked,
    m.recipes_json,
    m.recipe_overrides_json,
    m.image_url,
    m.is_favorite,
    m.servings,
    m.fallback_video_url,
    m.created_at,
    count(*) over () as total_count
  from matched m
  order by m.match_rank,
    case when p_sort = 'times_cooked' then m.times_cooked end desc nulls last,
    case when p_sort = 'favorites' then m.is_favorite end desc nulls last,
    case when p_sort = 'az' then m.page_title end asc nulls last,
    case when p_sort = 'za' then m.page_title end desc nulls last,
    case when p_sort = 'za' then m.created_at end asc nulls last,
    m.created_at desc,
    m.id
  limit greatest(p_limit, 0)
  offset greatest(p_offset, 0)
$$;

grant execute on function public.search_recipe_imports(text, text, boolean, text, integer, integer) to anon, authenticated;
