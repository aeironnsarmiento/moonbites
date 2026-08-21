from pathlib import Path
import re


SCHEMA_SQL = (
    Path(__file__).resolve().parents[2] / "supabase_schema.sql"
).read_text()


def test_recipe_imports_grants_delete_to_authenticated_users():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert (
        "grant insert, update, delete on public.recipe_imports to authenticated"
        in normalized_sql
    )


def test_recipe_imports_has_admin_delete_policy():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert (
        'create policy "recipe admins can delete recipe imports" '
        "on public.recipe_imports for delete to authenticated "
        "using (public.is_recipe_admin())"
    ) in normalized_sql


def test_recipe_imports_unique_url_constraints_skip_when_duplicates_exist():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert "duplicate submitted_url values exist" in normalized_sql
    assert "duplicate final_url values exist" in normalized_sql
    assert "raise notice" in normalized_sql
    assert "having count(*) > 1" in normalized_sql


def test_recipe_imports_has_immutable_cuisine_helpers_and_gin_index():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert "create or replace function public.recipe_cuisine_bucket" in normalized_sql
    assert "immutable" in normalized_sql
    assert "create or replace function public.extract_recipe_cuisines" in normalized_sql
    assert (
        "generated always as (public.extract_recipe_cuisines(recipes_json)) stored"
        in normalized_sql
    )
    assert (
        "create index if not exists recipe_imports_cuisines_gin_idx "
        "on public.recipe_imports using gin (cuisines)"
    ) in normalized_sql


def test_recipe_imports_generated_cuisines_column_has_no_subquery():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()
    match = re.search(
        r"add column if not exists cuisines text\[\] generated always as \((.*?)\) stored",
        normalized_sql,
    )

    assert match is not None
    assert "select " not in match.group(1)


def test_recipe_imports_has_cuisine_facets_rpc():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert "create or replace function public.cuisine_facets()" in normalized_sql
    assert "returns table(label text, count bigint)" in normalized_sql
    assert "grant execute on function public.cuisine_facets() to anon, authenticated" in normalized_sql


def _search_function_sql() -> str:
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()
    start = normalized_sql.index("create function public.search_recipe_imports")
    end = normalized_sql.index(
        "grant execute on function public.search_recipe_imports"
    )
    return normalized_sql[start:end]


def test_search_recipe_imports_drops_before_create():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    drop_index = normalized_sql.index(
        "drop function if exists public.search_recipe_imports"
    )
    create_index = normalized_sql.index(
        "create function public.search_recipe_imports"
    )

    assert drop_index < create_index


def test_search_recipe_imports_returns_record_columns_with_window_count():
    function_sql = _search_function_sql()

    assert "returns table" in function_sql
    assert "total_count bigint" in function_sql
    assert "count(*) over () as total_count" in function_sql
    assert "limit greatest(p_limit, 0)" in function_sql
    assert "offset greatest(p_offset, 0)" in function_sql


def test_recipe_imports_has_fallback_video_url_column():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert (
        "alter table public.recipe_imports add column if not exists fallback_video_url text"
        in normalized_sql
    )


def test_recipe_imports_has_internal_thumbnail_storage_and_public_bucket():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert (
        "alter table public.recipe_imports add column if not exists "
        "image_storage_path text"
    ) in normalized_sql
    assert "insert into storage.buckets" in normalized_sql
    assert "'recipe-thumbnails', 'recipe-thumbnails', true, 5242880" in normalized_sql
    assert "array['image/jpeg', 'image/png', 'image/webp', 'image/avif']" in normalized_sql
    assert "on conflict (id) do update" in normalized_sql


def test_search_recipe_imports_returns_fallback_video_url():
    function_sql = _search_function_sql()

    # The RPC returns an explicit column list, so a column missing here comes
    # back null on every search hit rather than failing loudly.
    assert "fallback_video_url text" in function_sql
    assert "m.fallback_video_url" in function_sql


def test_search_recipe_imports_matches_only_the_contracted_fields():
    function_sql = _search_function_sql()

    assert "recipes_json->0->>'name'" in function_sql
    assert "r.page_title" in function_sql
    assert "recipe.node->'ingredients'" in function_sql
    assert "recipe.node->'recipecuisine'" in function_sql
    assert "unnest(r.cuisines)" in function_sql
    assert (
        "substring(lower(r.submitted_url) from '^https?://([^/]+)')" in function_sql
    )
    assert "substring(lower(r.final_url) from '^https?://([^/]+)')" in function_sql
    assert "'instructions'" not in function_sql
    assert "'nutrition'" not in function_sql


def test_search_recipe_imports_ranks_exact_prefix_substring_then_other_fields():
    function_sql = _search_function_sql()

    tier_one = function_sql.index("then 1")
    tier_two = function_sql.index("then 2")
    tier_three = function_sql.index("then 3")
    fallback = function_sql.index("else 4")

    assert tier_one < tier_two < tier_three < fallback
    assert "= p.exact_term" in function_sql[:tier_one]


def test_search_recipe_imports_tier_two_is_prefix_and_tier_three_is_substring():
    function_sql = _search_function_sql()

    tier_one = function_sql.index("then 1")
    tier_two = function_sql.index("then 2")
    tier_three = function_sql.index("then 3")

    prefix_pattern = "ilike p.escaped_term || '%'"
    substring_pattern = "ilike '%' || p.escaped_term || '%'"
    tier_two_clause = function_sql[tier_one:tier_two]
    tier_three_clause = function_sql[tier_two:tier_three]

    assert prefix_pattern in tier_two_clause
    assert substring_pattern not in tier_two_clause
    assert substring_pattern in tier_three_clause


def test_search_recipe_imports_matches_case_insensitively():
    function_sql = _search_function_sql()

    assert "ilike" in function_sql
    assert " like " not in function_sql


def test_search_recipe_imports_escapes_ilike_wildcards():
    function_sql = _search_function_sql()

    assert (
        r"replace(replace(replace(btrim(coalesce(p_term, '')), '\', '\\'), '%', '\%'), '_', '\_')"
        in function_sql
    )


def test_search_recipe_imports_composes_filters_in_where():
    function_sql = _search_function_sql()

    assert "and (p_cuisine is null or r.cuisines @> array[p_cuisine])" in function_sql
    assert "and (p_favorite is not true or r.is_favorite)" in function_sql


def test_search_recipe_imports_orders_by_rank_then_requested_sort():
    function_sql = _search_function_sql()

    assert "order by m.match_rank," in function_sql
    assert "case when p_sort = 'times_cooked' then m.times_cooked end desc" in function_sql
    assert "case when p_sort = 'favorites' then m.is_favorite end desc" in function_sql
    assert "case when p_sort = 'az' then m.page_title end asc" in function_sql
    assert "case when p_sort = 'za' then m.page_title end desc" in function_sql
    assert "case when p_sort = 'za' then m.created_at end asc" in function_sql
    assert "m.created_at desc, m.id" in function_sql


def test_search_recipe_imports_grants_execute():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert (
        "grant execute on function public.search_recipe_imports"
        "(text, text, boolean, text, integer, integer) to anon, authenticated"
        in normalized_sql
    )


# --- U4: linked_recipe_url provenance ---------------------------------------


def test_recipe_imports_has_nullable_linked_recipe_url_with_no_unique_constraint():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert (
        "alter table public.recipe_imports add column if not exists linked_recipe_url text"
        in normalized_sql
    )
    assert "linked_recipe_url text unique" not in normalized_sql
    assert "unique (linked_recipe_url)" not in normalized_sql


def test_recipe_imports_submitted_and_final_url_unique_constraints_still_present():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert (
        "add constraint recipe_imports_submitted_url_key unique (submitted_url)"
        in normalized_sql
    )
    assert (
        "add constraint recipe_imports_final_url_key unique (final_url)"
        in normalized_sql
    )


def test_search_recipe_imports_returns_linked_recipe_url():
    function_sql = _search_function_sql()

    assert "linked_recipe_url text" in function_sql
    assert "r.linked_recipe_url" in function_sql
    assert "m.linked_recipe_url" in function_sql


# --- U9: Instagram import job and provider admission schema ----------------


def test_instagram_import_jobs_table_has_bounded_ktd15_columns():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert "create table if not exists public.instagram_import_jobs" in normalized_sql
    for column in (
        "owner_email text not null",
        "canonical_reel_url text not null",
        "state text not null",
        "version integer not null default 0",
        "lease_token uuid",
        "lease_expires_at timestamptz",
        "next_advance_at timestamptz not null",
        "stale_deadline timestamptz not null",
        "reel_run_id text",
        "reel_dataset_id text",
        "profile_run_id text",
        "profile_dataset_id text",
        "candidate_name text",
        "normalized_result_json jsonb",
        "linked_recipe_url text",
        "recipe_id uuid references public.recipe_imports (id)",
        "error_code text",
    ):
        assert column in normalized_sql, column

    # KTD15 explicitly excludes these from persistence.
    for forbidden in ("caption text", "profile_links", "owner_handle", "cdn_url", "bearer_token"):
        assert forbidden not in normalized_sql


def test_instagram_import_jobs_has_one_active_job_per_owner_and_reel():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert (
        "create unique index if not exists instagram_import_jobs_active_owner_reel_idx "
        "on public.instagram_import_jobs (owner_email, canonical_reel_url) "
        "where state not in ('succeeded', 'not_recipe', 'failed')"
    ) in normalized_sql


def test_instagram_import_jobs_rls_enabled_and_browser_roles_revoked():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert "alter table public.instagram_import_jobs enable row level security" in normalized_sql
    assert (
        "revoke all on table public.instagram_import_jobs from anon, authenticated, public"
        in normalized_sql
    )


def test_instagram_provider_admission_is_a_seeded_singleton_with_rls_revoked():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert "create table if not exists public.instagram_provider_admission" in normalized_sql
    assert "id boolean primary key default true" in normalized_sql
    assert "constraint instagram_provider_admission_singleton check (id)" in normalized_sql
    assert "insert into public.instagram_provider_admission (id) values (true)" in normalized_sql
    assert "on conflict (id) do nothing" in normalized_sql
    assert (
        "alter table public.instagram_provider_admission enable row level security"
        in normalized_sql
    )
    assert (
        "revoke all on table public.instagram_provider_admission from anon, authenticated, public"
        in normalized_sql
    )


def test_create_or_reuse_instagram_import_job_reuses_before_enforcing_ceilings():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    start = normalized_sql.index(
        "create or replace function public.create_or_reuse_instagram_import_job"
    )
    end = normalized_sql.index(
        "revoke execute on function public.create_or_reuse_instagram_import_job"
    )
    function_sql = normalized_sql[start:end]

    reuse_index = function_sql.index("'reused'::text")
    owner_ceiling_index = function_sql.index("raise exception 'owner_active_job_ceiling'")
    global_ceiling_index = function_sql.index("raise exception 'global_active_job_ceiling'")

    assert reuse_index < owner_ceiling_index < global_ceiling_index
    assert "on unique_violation" in function_sql or "when unique_violation" in function_sql
    assert "'created'::text" in function_sql


def test_claim_instagram_import_job_lease_is_a_version_and_owner_gated_cas():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    start = normalized_sql.index(
        "create or replace function public.claim_instagram_import_job_lease"
    )
    end = normalized_sql.index(
        "revoke execute on function public.claim_instagram_import_job_lease"
    )
    function_sql = normalized_sql[start:end]

    assert "j.owner_email = p_owner_email" in function_sql
    assert "j.version = p_expected_version" in function_sql
    assert "j.state not in ('succeeded', 'not_recipe', 'failed')" in function_sql
    assert "j.lease_expires_at is null or j.lease_expires_at <= timezone('utc', now())" in function_sql
    assert "version = j.version + 1" in function_sql


def test_checkpoint_instagram_import_job_is_lease_and_version_gated():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    start = normalized_sql.index(
        "create or replace function public.checkpoint_instagram_import_job"
    )
    end = normalized_sql.index(
        "revoke execute on function public.checkpoint_instagram_import_job"
    )
    function_sql = normalized_sql[start:end]

    assert "j.lease_token = p_lease_token" in function_sql
    assert "j.version = p_expected_version" in function_sql
    assert "coalesce(p_reel_run_id, j.reel_run_id)" in function_sql
    assert "coalesce(p_normalized_result_json, j.normalized_result_json)" in function_sql
    assert "case when p_release_lease then null else j.lease_token end" in function_sql


def test_provider_admission_reserve_and_release_are_singleton_scoped():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    reserve_start = normalized_sql.index(
        "create or replace function public.reserve_instagram_provider_admission"
    )
    reserve_end = normalized_sql.index(
        "revoke execute on function public.reserve_instagram_provider_admission"
    )
    reserve_sql = normalized_sql[reserve_start:reserve_end]
    assert "a.id = true" in reserve_sql
    assert "a.active_job_id is null or a.active_job_id = p_job_id" in reserve_sql

    release_start = normalized_sql.index(
        "create or replace function public.release_instagram_provider_admission"
    )
    release_end = normalized_sql.index(
        "revoke execute on function public.release_instagram_provider_admission"
    )
    release_sql = normalized_sql[release_start:release_end]
    assert "a.id = true" in release_sql
    assert "a.active_job_id = p_job_id" in release_sql


def test_stale_and_retention_cleanup_functions_default_to_dry_run_shape():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert "create or replace function public.terminalize_stale_instagram_import_jobs" in normalized_sql
    assert "create or replace function public.delete_expired_instagram_import_jobs" in normalized_sql
    assert "create or replace function public.reconcile_instagram_provider_admission" in normalized_sql

    terminalize_start = normalized_sql.index(
        "create or replace function public.terminalize_stale_instagram_import_jobs"
    )
    terminalize_end = normalized_sql.index(
        "revoke execute on function public.terminalize_stale_instagram_import_jobs"
    )
    terminalize_sql = normalized_sql[terminalize_start:terminalize_end]
    assert "if p_dry_run then" in terminalize_sql
    assert "stale_deadline < timezone('utc', now())" in terminalize_sql

    delete_start = normalized_sql.index(
        "create or replace function public.delete_expired_instagram_import_jobs"
    )
    delete_end = normalized_sql.index(
        "revoke execute on function public.delete_expired_instagram_import_jobs"
    )
    delete_sql = normalized_sql[delete_start:delete_end]
    assert "if p_dry_run then" in delete_sql
    assert "delete from public.instagram_import_jobs" in delete_sql


def test_instagram_job_rpcs_revoke_execute_from_browser_roles():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    for fragment in (
        "revoke execute on function public.create_or_reuse_instagram_import_job",
        "revoke execute on function public.claim_instagram_import_job_lease",
        "revoke execute on function public.checkpoint_instagram_import_job",
        "revoke execute on function public.reserve_instagram_provider_admission",
        "revoke execute on function public.release_instagram_provider_admission",
        "revoke execute on function public.reconcile_instagram_provider_admission",
        "revoke execute on function public.terminalize_stale_instagram_import_jobs",
        "revoke execute on function public.delete_expired_instagram_import_jobs",
    ):
        assert fragment in normalized_sql
        assert "from anon, authenticated, public" in normalized_sql[normalized_sql.index(fragment):normalized_sql.index(fragment) + 400]
