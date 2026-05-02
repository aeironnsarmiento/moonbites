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
