from typing import Optional

from backend.app.clients.supabase_client import get_supabase_client
from backend.app.core.config import get_settings
from backend.app.schemas.extract import (
    NormalizedRecipe,
    PaginatedRecipeImportsResponse,
    RecipeImportRecord,
)
from backend.app.services.normalizer import dedupe_normalized_recipes
from backend.app.utils.urls import canonicalize_url


RECIPE_IMPORT_SELECT = (
    "id, submitted_url, final_url, page_title, recipe_count, recipes_json, created_at"
)


def _sanitize_record(record: dict) -> RecipeImportRecord:
    recipes = [
        NormalizedRecipe.model_validate(item)
        for item in record.get("recipes_json") or []
    ]
    unique_recipes = dedupe_normalized_recipes(recipes)

    normalized_record = {
        **record,
        "recipe_count": len(unique_recipes),
        "recipes_json": [recipe.model_dump() for recipe in unique_recipes],
    }

    return RecipeImportRecord.model_validate(normalized_record)


def _fetch_all_recipe_import_records(
    client, table_name: str
) -> list[RecipeImportRecord]:
    response = (
        client.table(table_name)
        .select(RECIPE_IMPORT_SELECT)
        .order("created_at", desc=True)
        .execute()
    )

    records = response.data or []
    return [_sanitize_record(record) for record in records]


def _record_url_keys(record: RecipeImportRecord) -> set[str]:
    return {
        canonicalize_url(record.submitted_url),
        canonicalize_url(record.final_url),
    }


def _dedupe_recipe_import_records(
    records: list[RecipeImportRecord],
) -> list[RecipeImportRecord]:
    seen: set[str] = set()
    unique_records: list[RecipeImportRecord] = []

    for record in records:
        keys = _record_url_keys(record)
        if seen.intersection(keys):
            continue

        seen.update(keys)
        unique_records.append(record)

    return unique_records


def save_recipe_import(
    submitted_url: str,
    final_url: str,
    title: Optional[str],
    recipes: list[NormalizedRecipe],
) -> tuple[bool, Optional[str]]:
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        return (
            False,
            "Supabase is not configured yet. Add backend env vars to enable saving.",
        )

    unique_recipes = dedupe_normalized_recipes(recipes)
    submitted_url_key = canonicalize_url(submitted_url)
    final_url_key = canonicalize_url(final_url)

    try:
        existing_records = _fetch_all_recipe_import_records(
            client, settings.supabase_table_name
        )
    except Exception as error:
        return False, f"Supabase duplicate check failed: {error}"

    for existing_record in existing_records:
        existing_keys = _record_url_keys(existing_record)
        if submitted_url_key in existing_keys or final_url_key in existing_keys:
            return (
                True,
                "Recipe import already exists, so the duplicate save was skipped.",
            )

    payload = {
        "submitted_url": submitted_url,
        "final_url": final_url,
        "page_title": title,
        "recipe_count": len(unique_recipes),
        "recipes_json": [recipe.model_dump() for recipe in unique_recipes],
    }

    try:
        client.table(settings.supabase_table_name).insert(payload).execute()
    except Exception as error:
        return False, f"Supabase save failed: {error}"

    return True, f"Saved to Supabase table '{settings.supabase_table_name}'."


def list_recipe_imports(page: int, page_size: int) -> PaginatedRecipeImportsResponse:
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable reading saved recipes."
        )

    try:
        records = _fetch_all_recipe_import_records(client, settings.supabase_table_name)
    except Exception as error:
        raise RuntimeError(f"Supabase read failed: {error}") from error

    unique_records = _dedupe_recipe_import_records(records)
    total_count = len(unique_records)
    total_pages = (
        max(1, (total_count + page_size - 1) // page_size) if total_count else 1
    )
    offset = (page - 1) * page_size
    paginated_records = unique_records[offset : offset + page_size]

    return PaginatedRecipeImportsResponse(
        items=paginated_records,
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=total_pages,
    )


def get_recipe_import(recipe_import_id: str) -> Optional[RecipeImportRecord]:
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable reading saved recipes."
        )

    try:
        response = (
            client.table(settings.supabase_table_name)
            .select(RECIPE_IMPORT_SELECT)
            .eq("id", recipe_import_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise RuntimeError(f"Supabase read failed: {error}") from error

    records = response.data or []
    if not records:
        return None

    return _sanitize_record(records[0])
