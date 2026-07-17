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


def test_recipe_imports_has_display_title_columns():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert (
        "add column if not exists display_title text" in normalized_sql
    )
    assert (
        "add column if not exists display_title_source text not null default 'fallback'"
        in normalized_sql
    )


def test_recipe_imports_display_title_sort_mirrors_card_title_precedence():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()
    match = re.search(
        r"add column if not exists display_title_sort text generated always as \((.*?)\) stored",
        normalized_sql,
    )

    assert match is not None
    expression = match.group(1).strip()
    # Same precedence as the frontend card mapper, so A-Z sorts by what users see.
    assert (
        expression
        == "lower(coalesce(display_title, recipes_json->0->>'name', page_title, ''))"
    )
    assert "select " not in expression
    assert (
        "create index if not exists recipe_imports_display_title_sort_idx "
        "on public.recipe_imports (display_title_sort)"
    ) in normalized_sql


def test_display_title_columns_are_added_before_the_search_function():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    column_index = normalized_sql.index("add column if not exists display_title text")
    create_index = normalized_sql.index(
        "create function public.search_recipe_imports"
    )

    assert column_index < create_index


def test_search_recipe_imports_returns_display_title_columns():
    function_sql = _search_function_sql()

    assert "display_title text," in function_sql
    assert "display_title_source text," in function_sql


def test_search_recipe_imports_matches_only_the_contracted_fields():
    function_sql = _search_function_sql()

    assert "r.display_title" in function_sql
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


def test_search_recipe_imports_ranks_display_title_alongside_the_original_titles():
    function_sql = _search_function_sql()

    tier_one = function_sql.index("then 1")
    tier_two = function_sql.index("then 2")
    tier_three = function_sql.index("then 3")

    # The display title is the name users see, so it ranks in every title tier;
    # page_title stays matched so the original source title remains searchable (R7).
    for clause in (
        function_sql[:tier_one],
        function_sql[tier_one:tier_two],
        function_sql[tier_two:tier_three],
    ):
        assert "r.display_title" in clause
        assert "r.page_title" in clause


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
    assert "case when p_sort = 'az' then m.display_title_sort end asc" in function_sql
    assert "case when p_sort = 'za' then m.display_title_sort end desc" in function_sql
    assert "case when p_sort = 'za' then m.created_at end asc" in function_sql
    assert "m.created_at desc, m.id" in function_sql


def test_search_recipe_imports_grants_execute():
    normalized_sql = " ".join(SCHEMA_SQL.split()).casefold()

    assert (
        "grant execute on function public.search_recipe_imports"
        "(text, text, boolean, text, integer, integer) to anon, authenticated"
        in normalized_sql
    )
