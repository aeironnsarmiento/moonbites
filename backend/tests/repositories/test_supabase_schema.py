from pathlib import Path


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
