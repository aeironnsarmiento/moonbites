from backend.app.clients.supabase_client import get_supabase_client
from backend.app.core.config import get_settings
from backend.app.schemas.extract import (
    NormalizedRecipe,
    PaginatedRecipeImportsResponse,
    RecipeImportRecord,
)


def save_recipe_import(
    submitted_url: str,
    final_url: str,
    title: str | None,
    recipes: list[NormalizedRecipe],
) -> tuple[bool, str | None]:
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        return False, "Supabase is not configured yet. Add backend env vars to enable saving."

    payload = {
        "submitted_url": submitted_url,
        "final_url": final_url,
        "page_title": title,
        "recipe_count": len(recipes),
        "recipes_json": [recipe.model_dump() for recipe in recipes],
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

    offset = (page - 1) * page_size
    limit_end = offset + page_size - 1

    try:
        response = (
            client.table(settings.supabase_table_name)
            .select(
                "id, submitted_url, final_url, page_title, recipe_count, recipes_json, created_at",
                count="exact",
            )
            .order("created_at", desc=True)
            .range(offset, limit_end)
            .execute()
        )
    except Exception as error:
        raise RuntimeError(f"Supabase read failed: {error}") from error

    records = response.data or []
    total_count = response.count or 0
    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count else 1

    return PaginatedRecipeImportsResponse(
        items=[RecipeImportRecord.model_validate(record) for record in records],
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=total_pages,
    )


def get_recipe_import(recipe_import_id: str) -> RecipeImportRecord | None:
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable reading saved recipes."
        )

    try:
        response = (
            client.table(settings.supabase_table_name)
            .select("id, submitted_url, final_url, page_title, recipe_count, recipes_json, created_at")
            .eq("id", recipe_import_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise RuntimeError(f"Supabase read failed: {error}") from error

    records = response.data or []
    if not records:
        return None

    return RecipeImportRecord.model_validate(records[0])