from typing import Optional
from uuid import uuid4

from ..clients.supabase_client import get_supabase_client
from ..core.config import get_settings
from ..schemas.extract import (
    NormalizedRecipe,
    PaginatedRecipeImportsResponse,
    RecipeImportRecord,
    RecipeTextOverrides,
)
from ..services.normalizer import dedupe_normalized_recipes
from ..utils.urls import canonicalize_url


RECIPE_IMPORT_SELECT = "id, submitted_url, final_url, page_title, recipe_count, times_cooked, recipes_json, recipe_overrides_json, created_at"


def _sanitize_override_rows(rows: object) -> dict[str, str]:
    if not isinstance(rows, dict):
        return {}

    sanitized_rows: dict[str, str] = {}
    for row_index, value in rows.items():
        try:
            normalized_index = str(int(str(row_index)))
        except (TypeError, ValueError):
            continue

        if value is None:
            continue

        sanitized_rows[normalized_index] = str(value)

    return sanitized_rows


def _sanitize_recipe_overrides(overrides: object) -> dict[str, dict[str, dict[str, str]]]:
    if not isinstance(overrides, dict):
        return {}

    sanitized_overrides: dict[str, dict[str, dict[str, str]]] = {}
    for recipe_index, sections in overrides.items():
        try:
            normalized_recipe_index = str(int(str(recipe_index)))
        except (TypeError, ValueError):
            continue

        if not isinstance(sections, dict):
            sections = {}

        validated_sections = RecipeTextOverrides.model_validate(
            {
                "ingredients": _sanitize_override_rows(sections.get("ingredients")),
                "instructions": _sanitize_override_rows(sections.get("instructions")),
            }
        )
        normalized_sections = validated_sections.model_dump()

        if normalized_sections["ingredients"] or normalized_sections["instructions"]:
            sanitized_overrides[normalized_recipe_index] = normalized_sections

    return sanitized_overrides


def _sanitize_record(record: dict) -> RecipeImportRecord:
    recipes = [
        NormalizedRecipe.model_validate(item)
        for item in record.get("recipes_json") or []
    ]
    unique_recipes = dedupe_normalized_recipes(recipes)

    normalized_record = {
        **record,
        "recipe_count": len(unique_recipes),
        "times_cooked": record.get("times_cooked", 0),
        "recipes_json": [recipe.model_dump() for recipe in unique_recipes],
        "recipe_overrides_json": _sanitize_recipe_overrides(
            record.get("recipe_overrides_json") or {}
        ),
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


def is_manual_recipe_url(value: str) -> bool:
    return value.strip().lower().startswith("manual://")


def _build_manual_recipe_url(manual_id: str) -> str:
    return f"manual://{manual_id}"


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
        "times_cooked": 0,
        "recipes_json": [recipe.model_dump() for recipe in unique_recipes],
        "recipe_overrides_json": {},
    }

    try:
        client.table(settings.supabase_table_name).insert(payload).execute()
    except Exception as error:
        return False, f"Supabase save failed: {error}"

    return True, f"Saved to Supabase table '{settings.supabase_table_name}'."


def save_manual_recipe(
    recipe: NormalizedRecipe,
    title: Optional[str] = None,
) -> RecipeImportRecord:
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable saving recipes."
        )

    manual_id = str(uuid4())
    manual_url = _build_manual_recipe_url(manual_id)
    page_title = title or f"Manual recipe: {recipe.name}"

    payload = {
        "id": manual_id,
        "submitted_url": manual_url,
        "final_url": manual_url,
        "page_title": page_title,
        "recipe_count": 1,
        "times_cooked": 0,
        "recipes_json": [recipe.model_dump()],
        "recipe_overrides_json": {},
    }

    try:
        client.table(settings.supabase_table_name).insert(payload).execute()
    except Exception as error:
        raise RuntimeError(f"Supabase save failed: {error}") from error

    created_record = get_recipe_import(manual_id)
    if created_record is None:
        raise RuntimeError("Manual recipe was saved but could not be read back.")

    return created_record


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


def update_times_cooked(
    recipe_import_id: str, delta: int
) -> Optional[RecipeImportRecord]:
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable updating saved recipes."
        )

    existing_record = get_recipe_import(recipe_import_id)
    if existing_record is None:
        return None

    next_times_cooked = max(0, existing_record.times_cooked + delta)

    try:
        (
            client.table(settings.supabase_table_name)
            .update({"times_cooked": next_times_cooked})
            .eq("id", recipe_import_id)
            .execute()
        )
    except Exception as error:
        raise RuntimeError(f"Supabase update failed: {error}") from error

    return get_recipe_import(recipe_import_id)


def update_recipe_overrides(
    recipe_import_id: str,
    recipe_index: int,
    overrides: RecipeTextOverrides,
) -> Optional[RecipeImportRecord]:
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable updating saved recipes."
        )

    existing_record = get_recipe_import(recipe_import_id)
    if existing_record is None:
        return None

    if recipe_index >= len(existing_record.recipes_json):
        raise ValueError("recipe_index is out of range")

    next_overrides = _sanitize_recipe_overrides(existing_record.recipe_overrides_json)
    recipe_key = str(recipe_index)
    sanitized_override_entry = RecipeTextOverrides.model_validate(
        {
            "ingredients": _sanitize_override_rows(overrides.ingredients),
            "instructions": _sanitize_override_rows(overrides.instructions),
        }
    ).model_dump()

    if sanitized_override_entry["ingredients"] or sanitized_override_entry["instructions"]:
        next_overrides[recipe_key] = sanitized_override_entry
    else:
        next_overrides.pop(recipe_key, None)

    try:
        (
            client.table(settings.supabase_table_name)
            .update({"recipe_overrides_json": next_overrides})
            .eq("id", recipe_import_id)
            .execute()
        )
    except Exception as error:
        raise RuntimeError(f"Supabase update failed: {error}") from error

    return get_recipe_import(recipe_import_id)
