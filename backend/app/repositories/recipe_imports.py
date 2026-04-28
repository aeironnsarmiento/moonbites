from typing import NoReturn, Optional
from uuid import uuid4

from ..clients.supabase_client import (
    get_supabase_client,
    get_supabase_public_client,
    get_supabase_user_client,
)
from ..core.config import get_settings
from ..schemas.extract import (
    CuisineFacet,
    CuisineFacetsResponse,
    NormalizedRecipe,
    PaginatedRecipeImportsResponse,
    RecipeImportRecord,
    RecipeSortOption,
    UpdateRecipeMetadataRequest,
    RecipeTextOverrides,
)
from ..services.cuisine_catalog import (
    CANONICAL_CUISINES,
    OTHER_CUISINE_LABEL,
    canonical_cuisine,
    collect_canonical_cuisines,
)
from ..services.normalizer import dedupe_normalized_recipes
from ..utils.urls import canonicalize_url
from ..utils.yield_parser import parse_yield


RECIPE_IMPORT_SELECT = "id, submitted_url, final_url, page_title, recipe_count, times_cooked, recipes_json, recipe_overrides_json, image_url, is_favorite, servings, created_at"


class RecipeWriteDeniedError(RuntimeError):
    pass


def _get_read_client(settings):
    return get_supabase_client(settings) or get_supabase_public_client(settings)


def _get_write_client(settings, access_token: Optional[str] = None):
    if access_token:
        return get_supabase_user_client(settings, access_token)

    return get_supabase_client(settings)


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


def _sanitize_recipe_overrides(
    overrides: object,
) -> dict[str, dict[str, dict[str, str]]]:
    if not isinstance(overrides, dict):
        return {}

    sanitized_overrides: dict[str, dict[str, dict[str, str]]] = {}
    for recipe_index, sections in overrides.items():
        try:
            normalized_recipe_index = str(int(str(recipe_index)))
        except (TypeError, ValueError):
            continue

        if isinstance(sections, RecipeTextOverrides):
            sections = sections.model_dump()

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
        "image_url": record.get("image_url"),
        "is_favorite": bool(record.get("is_favorite", False)),
        "servings": record.get("servings"),
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


def _record_cuisines(record: RecipeImportRecord) -> set[str]:
    return collect_canonical_cuisines(
        recipe.recipeCuisine for recipe in record.recipes_json
    )


def _normalize_cuisine_filter(cuisine: Optional[str]) -> Optional[str]:
    if cuisine is None:
        return None

    stripped_cuisine = cuisine.strip()
    if not stripped_cuisine:
        return None

    if stripped_cuisine.casefold() == OTHER_CUISINE_LABEL.casefold():
        return OTHER_CUISINE_LABEL

    return canonical_cuisine(stripped_cuisine) or stripped_cuisine


def _filter_recipe_import_records(
    records: list[RecipeImportRecord], cuisine: Optional[str]
) -> list[RecipeImportRecord]:
    normalized_cuisine = _normalize_cuisine_filter(cuisine)
    if normalized_cuisine is None:
        return records

    return [
        record for record in records if normalized_cuisine in _record_cuisines(record)
    ]


def _primary_recipe_name(record: RecipeImportRecord) -> str:
    primary_recipe = record.recipes_json[0] if record.recipes_json else None
    name = primary_recipe.name if primary_recipe else record.page_title or ""
    return name.casefold()


def _sort_recipe_import_records(
    records: list[RecipeImportRecord], sort: RecipeSortOption
) -> list[RecipeImportRecord]:
    if sort == RecipeSortOption.az:
        return sorted(
            records,
            key=lambda record: (
                _primary_recipe_name(record),
                -record.created_at.timestamp(),
            ),
        )

    if sort == RecipeSortOption.za:
        return sorted(
            records,
            key=lambda record: (
                _primary_recipe_name(record),
                record.created_at.timestamp(),
            ),
            reverse=True,
        )

    if sort == RecipeSortOption.times_cooked:
        return sorted(
            records,
            key=lambda record: (record.times_cooked, record.created_at.timestamp()),
            reverse=True,
        )

    if sort == RecipeSortOption.favorites:
        return sorted(
            records,
            key=lambda record: (
                record.is_favorite,
                record.created_at.timestamp(),
            ),
            reverse=True,
        )

    return sorted(records, key=lambda record: record.created_at, reverse=True)


def _prepare_recipe_import_records(
    records: list[RecipeImportRecord],
    sort: RecipeSortOption,
    cuisine: Optional[str],
    favorite: Optional[bool] = None,
) -> list[RecipeImportRecord]:
    unique_records = _dedupe_recipe_import_records(records)
    filtered_records = _filter_recipe_import_records(unique_records, cuisine)
    if favorite is True:
        filtered_records = [record for record in filtered_records if record.is_favorite]
    return _sort_recipe_import_records(filtered_records, sort)


def _build_cuisine_facets(
    records: list[RecipeImportRecord],
) -> list[CuisineFacet]:
    cuisine_counts: dict[str, int] = {}

    for record in records:
        for cuisine in _record_cuisines(record):
            cuisine_counts[cuisine] = cuisine_counts.get(cuisine, 0) + 1

    return [
        CuisineFacet(label=label, count=count)
        for label, count in sorted(cuisine_counts.items())
    ]


_SORT_CLAUSES: dict[RecipeSortOption, list[tuple[str, bool]]] = {
    RecipeSortOption.recent: [("created_at", True)],
    RecipeSortOption.times_cooked: [("times_cooked", True), ("created_at", True)],
    RecipeSortOption.favorites: [("is_favorite", True), ("created_at", True)],
    RecipeSortOption.az: [("page_title", False), ("created_at", True)],
    RecipeSortOption.za: [("page_title", True), ("created_at", False)],
}


_CUISINE_LABEL_BY_DB_KEY = {
    cuisine.casefold(): cuisine for cuisine in CANONICAL_CUISINES
}
_CUISINE_LABEL_BY_DB_KEY[OTHER_CUISINE_LABEL.casefold()] = OTHER_CUISINE_LABEL


def _apply_sort(query, sort: RecipeSortOption):
    for column, desc in _SORT_CLAUSES.get(sort, [("created_at", True)]):
        query = query.order(column, desc=desc)
    return query


def _cuisine_db_key(cuisine: Optional[str]) -> Optional[str]:
    normalized_cuisine = _normalize_cuisine_filter(cuisine)
    if normalized_cuisine is None:
        return None
    return normalized_cuisine.casefold()


def _cuisine_display_label(label: str) -> str:
    return _CUISINE_LABEL_BY_DB_KEY.get(label.casefold(), label)


def _find_existing_records_by_exact_urls(
    client, table_name: str, urls: list[str]
) -> list[dict]:
    records: list[dict] = []
    for column in ("submitted_url", "final_url"):
        response = (
            client.table(table_name)
            .select("submitted_url, final_url")
            .in_(column, urls)
            .execute()
        )
        records.extend(response.data or [])
    return records


def save_recipe_import(
    submitted_url: str,
    final_url: str,
    title: Optional[str],
    recipes: list[NormalizedRecipe],
    image_url: Optional[str] = None,
    access_token: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    settings = get_settings()
    client = _get_write_client(settings, access_token)
    if client is None:
        return (
            False,
            "Supabase is not configured yet. Add backend env vars to enable saving.",
        )

    unique_recipes = dedupe_normalized_recipes(recipes)
    servings = next(
        (
            parsed
            for recipe in unique_recipes
            if (parsed := parse_yield(recipe.recipeYield)) is not None
        ),
        None,
    )
    submitted_url_key = canonicalize_url(submitted_url)
    final_url_key = canonicalize_url(final_url)
    candidate_urls = sorted({submitted_url, final_url})

    try:
        existing_records = _find_existing_records_by_exact_urls(
            client,
            settings.supabase_table_name,
            candidate_urls,
        )
    except Exception as error:
        return False, f"Supabase duplicate check failed: {error}"

    for existing in existing_records:
        existing_keys = {
            canonicalize_url(existing.get("submitted_url") or ""),
            canonicalize_url(existing.get("final_url") or ""),
        }
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
        "image_url": image_url,
        "is_favorite": False,
        "servings": servings,
    }

    try:
        client.table(settings.supabase_table_name).insert(payload).execute()
    except Exception as error:
        message = str(error).lower()
        if "unique" in message or "duplicate" in message or "23505" in message:
            return (
                True,
                "Recipe import already exists, so the duplicate save was skipped.",
            )
        return False, f"Supabase save failed: {error}"

    return True, "Recipe saved to your collection."


def save_manual_recipe(
    recipe: NormalizedRecipe,
    title: Optional[str] = None,
    access_token: Optional[str] = None,
) -> RecipeImportRecord:
    settings = get_settings()
    client = _get_write_client(settings, access_token)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable saving recipes."
        )

    manual_id = str(uuid4())
    manual_url = _build_manual_recipe_url(manual_id)
    page_title = title or f"Manual recipe: {recipe.name}"
    servings = parse_yield(recipe.recipeYield)

    payload = {
        "id": manual_id,
        "submitted_url": manual_url,
        "final_url": manual_url,
        "page_title": page_title,
        "recipe_count": 1,
        "times_cooked": 0,
        "recipes_json": [recipe.model_dump()],
        "recipe_overrides_json": {},
        "image_url": None,
        "is_favorite": False,
        "servings": servings,
    }

    try:
        client.table(settings.supabase_table_name).insert(payload).execute()
    except Exception as error:
        raise RuntimeError(f"Supabase save failed: {error}") from error

    created_record = get_recipe_import(manual_id)
    if created_record is None:
        raise RuntimeError("Manual recipe was saved but could not be read back.")

    return created_record


def list_recipe_imports(
    page: int,
    page_size: int,
    sort: RecipeSortOption = RecipeSortOption.recent,
    cuisine: Optional[str] = None,
    favorite: Optional[bool] = None,
) -> PaginatedRecipeImportsResponse:
    settings = get_settings()
    client = _get_read_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable reading saved recipes."
        )

    table_name = settings.supabase_table_name
    offset = (page - 1) * page_size

    cuisine_key = _cuisine_db_key(cuisine)

    try:
        query = client.table(table_name).select(
            RECIPE_IMPORT_SELECT, count="exact"
        )
        if favorite is True:
            query = query.eq("is_favorite", True)
        if cuisine_key is not None:
            query = query.contains("cuisines", [cuisine_key])
        query = _apply_sort(query, sort)
        query = query.range(offset, offset + page_size - 1)
        response = query.execute()
    except Exception as error:
        raise RuntimeError(f"Supabase read failed: {error}") from error

    raw_records = response.data or []
    items = [_sanitize_record(record) for record in raw_records]
    items = _dedupe_recipe_import_records(items)

    total_count = getattr(response, "count", None)
    if total_count is None:
        total_count = len(items)
    total_pages = (
        max(1, (total_count + page_size - 1) // page_size) if total_count else 1
    )

    return PaginatedRecipeImportsResponse(
        items=items,
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=total_pages,
    )


def list_cuisine_facets() -> CuisineFacetsResponse:
    settings = get_settings()
    client = _get_read_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable reading saved recipes."
        )

    try:
        response = client.rpc("cuisine_facets", {}).execute()
    except Exception as error:
        raise RuntimeError(f"Supabase read failed: {error}") from error

    facets: list[CuisineFacet] = []
    for row in response.data or []:
        label = str(row.get("label") or "").strip()
        if not label:
            continue
        facets.append(
            CuisineFacet(
                label=_cuisine_display_label(label),
                count=int(row.get("count") or 0),
            )
        )
    return CuisineFacetsResponse(facets=facets)


REFRESH_BATCH_SIZE = 100


def list_recipe_import_records_for_refresh(
    *,
    cursor: Optional[str] = None,
    batch_size: int = REFRESH_BATCH_SIZE,
) -> list[RecipeImportRecord]:
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable reading saved recipes."
        )

    try:
        query = (
            client.table(settings.supabase_table_name)
            .select(RECIPE_IMPORT_SELECT)
            .order("created_at", desc=True)
            .limit(batch_size)
        )
        if cursor:
            query = query.lt("created_at", cursor)
        response = query.execute()
    except Exception as error:
        raise RuntimeError(f"Supabase read failed: {error}") from error

    raw_records = response.data or []
    return [_sanitize_record(record) for record in raw_records]


def iter_recipe_import_records_for_refresh(
    *,
    batch_size: int = REFRESH_BATCH_SIZE,
):
    cursor: Optional[str] = None
    while True:
        page = list_recipe_import_records_for_refresh(
            cursor=cursor, batch_size=batch_size
        )
        if not page:
            return
        for record in page:
            yield record
        cursor = page[-1].created_at.isoformat()
        if len(page) < batch_size:
            return


def get_recipe_import(recipe_import_id: str) -> Optional[RecipeImportRecord]:
    settings = get_settings()
    client = _get_read_client(settings)
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


def _raise_recipe_write_denied(recipe_import_id: str) -> NoReturn:
    raise RecipeWriteDeniedError(
        "Recipe write was denied by Supabase row-level security. "
        "Confirm the admin email returned by /api/auth/me exists in "
        f"public.recipe_admins before changing recipe import {recipe_import_id}."
    )


def _update_recipe_import_record(
    client,
    table_name: str,
    recipe_import_id: str,
    payload: dict,
) -> RecipeImportRecord:
    try:
        response = (
            client.table(table_name)
            .update(payload)
            .eq("id", recipe_import_id)
            .execute()
        )
    except Exception as error:
        raise RuntimeError(f"Supabase update failed: {error}") from error

    records = response.data or []
    if not records:
        _raise_recipe_write_denied(recipe_import_id)

    return _sanitize_record(records[0])


def _resolve_empty_write(recipe_import_id: str) -> Optional[RecipeImportRecord]:
    if get_recipe_import(recipe_import_id) is None:
        return None
    _raise_recipe_write_denied(recipe_import_id)


def _update_or_resolve(
    client,
    table_name: str,
    recipe_import_id: str,
    payload: dict,
) -> Optional[RecipeImportRecord]:
    try:
        response = (
            client.table(table_name)
            .update(payload)
            .eq("id", recipe_import_id)
            .execute()
        )
    except Exception as error:
        raise RuntimeError(f"Supabase update failed: {error}") from error

    records = response.data or []
    if records:
        return _sanitize_record(records[0])
    return _resolve_empty_write(recipe_import_id)


def _rpc_or_resolve(
    client,
    fn_name: str,
    params: dict,
    recipe_import_id: str,
) -> Optional[RecipeImportRecord]:
    try:
        response = client.rpc(fn_name, params).execute()
    except Exception as error:
        raise RuntimeError(f"Supabase update failed: {error}") from error

    records = response.data or []
    if records:
        return _sanitize_record(records[0])
    return _resolve_empty_write(recipe_import_id)


def delete_recipe_import(
    recipe_import_id: str,
    access_token: Optional[str] = None,
) -> bool:
    settings = get_settings()
    client = _get_write_client(settings, access_token)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable deleting saved recipes."
        )

    try:
        response = (
            client.table(settings.supabase_table_name)
            .delete()
            .eq("id", recipe_import_id)
            .execute()
        )
    except Exception as error:
        raise RuntimeError(f"Supabase delete failed: {error}") from error

    if response.data:
        return True

    if get_recipe_import(recipe_import_id) is None:
        return False

    _raise_recipe_write_denied(recipe_import_id)


def update_times_cooked(
    recipe_import_id: str,
    delta: int,
    access_token: Optional[str] = None,
) -> Optional[RecipeImportRecord]:
    settings = get_settings()
    client = _get_write_client(settings, access_token)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable updating saved recipes."
        )

    return _rpc_or_resolve(
        client,
        "increment_times_cooked",
        {"p_id": recipe_import_id, "p_delta": delta},
        recipe_import_id,
    )


def toggle_favorite(
    recipe_import_id: str,
    access_token: Optional[str] = None,
) -> Optional[RecipeImportRecord]:
    settings = get_settings()
    client = _get_write_client(settings, access_token)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable updating saved recipes."
        )

    return _rpc_or_resolve(
        client,
        "toggle_recipe_favorite",
        {"p_id": recipe_import_id},
        recipe_import_id,
    )


def update_servings(
    recipe_import_id: str,
    servings: int,
    access_token: Optional[str] = None,
) -> Optional[RecipeImportRecord]:
    settings = get_settings()
    client = _get_write_client(settings, access_token)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable updating saved recipes."
        )

    return _update_or_resolve(
        client,
        settings.supabase_table_name,
        recipe_import_id,
        {"servings": servings},
    )


def update_image_url(
    recipe_import_id: str,
    image_url: str,
    access_token: Optional[str] = None,
) -> Optional[RecipeImportRecord]:
    settings = get_settings()
    client = _get_write_client(settings, access_token)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable updating saved recipes."
        )

    return _update_or_resolve(
        client,
        settings.supabase_table_name,
        recipe_import_id,
        {"image_url": image_url},
    )


def _build_metadata_update_payload(
    existing_record: RecipeImportRecord,
    metadata: UpdateRecipeMetadataRequest,
) -> dict:
    recipes = [recipe.model_copy(deep=True) for recipe in existing_record.recipes_json]
    if recipes:
        recipes[0] = recipes[0].model_copy(
            update={
                "name": metadata.title,
                "recipeYield": metadata.recipe_yield,
            }
        )

    return {
        "page_title": metadata.title,
        "submitted_url": metadata.source_url,
        "final_url": metadata.source_url,
        "recipes_json": [recipe.model_dump() for recipe in recipes],
        "image_url": metadata.image_url,
        "servings": parse_yield(metadata.recipe_yield),
    }


def update_recipe_metadata(
    recipe_import_id: str,
    metadata: UpdateRecipeMetadataRequest,
    access_token: Optional[str] = None,
) -> Optional[RecipeImportRecord]:
    settings = get_settings()
    client = _get_write_client(settings, access_token)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable updating saved recipes."
        )

    existing_record = get_recipe_import(recipe_import_id)
    if existing_record is None:
        return None

    payload = _build_metadata_update_payload(existing_record, metadata)

    return _update_recipe_import_record(
        client,
        settings.supabase_table_name,
        recipe_import_id,
        payload,
    )


def _prune_override_rows(rows: dict[str, str], row_count: int) -> dict[str, str]:
    pruned_rows: dict[str, str] = {}
    for row_index, value in rows.items():
        if int(row_index) < row_count:
            pruned_rows[row_index] = value
    return pruned_rows


def _prune_recipe_overrides_for_recipes(
    overrides: object,
    recipes: list[NormalizedRecipe],
) -> dict[str, dict[str, dict[str, str]]]:
    sanitized_overrides = _sanitize_recipe_overrides(overrides)
    pruned_overrides: dict[str, dict[str, dict[str, str]]] = {}

    for recipe_index, sections in sanitized_overrides.items():
        index = int(recipe_index)
        if index >= len(recipes):
            continue

        recipe = recipes[index]
        ingredients = _prune_override_rows(
            sections.get("ingredients", {}),
            len(recipe.ingredients),
        )
        instructions = _prune_override_rows(
            sections.get("instructions", {}),
            len(recipe.instructions),
        )

        if ingredients or instructions:
            pruned_overrides[recipe_index] = {
                "ingredients": ingredients,
                "instructions": instructions,
            }

    return pruned_overrides


def _build_refetched_recipe_update_payload(
    existing_record: RecipeImportRecord,
    *,
    title: Optional[str],
    image_url: Optional[str],
    recipes: list[NormalizedRecipe],
) -> dict:
    unique_recipes = dedupe_normalized_recipes(recipes)
    servings = next(
        (
            parsed
            for recipe in unique_recipes
            if (parsed := parse_yield(recipe.recipeYield)) is not None
        ),
        None,
    )

    return {
        "page_title": title,
        "recipe_count": len(unique_recipes),
        "recipes_json": [recipe.model_dump() for recipe in unique_recipes],
        "recipe_overrides_json": _prune_recipe_overrides_for_recipes(
            existing_record.recipe_overrides_json,
            unique_recipes,
        ),
        "image_url": image_url,
        "servings": servings,
    }


def update_recipe_import_from_extraction(
    recipe_import_id: str,
    extraction_result,
    access_token: Optional[str] = None,
) -> Optional[RecipeImportRecord]:
    settings = get_settings()
    client = _get_write_client(settings, access_token)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable updating saved recipes."
        )

    existing_record = get_recipe_import(recipe_import_id)
    if existing_record is None:
        return None

    payload = _build_refetched_recipe_update_payload(
        existing_record,
        title=extraction_result.title,
        image_url=extraction_result.image_url,
        recipes=extraction_result.recipes,
    )

    return _update_recipe_import_record(
        client,
        settings.supabase_table_name,
        recipe_import_id,
        payload,
    )


def update_recipe_overrides(
    recipe_import_id: str,
    recipe_index: int,
    overrides: RecipeTextOverrides,
    access_token: Optional[str] = None,
) -> Optional[RecipeImportRecord]:
    settings = get_settings()
    client = _get_write_client(settings, access_token)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable updating saved recipes."
        )

    existing_record = get_recipe_import(recipe_import_id)
    if existing_record is None:
        return None

    if recipe_index >= len(existing_record.recipes_json):
        raise ValueError("recipe_index is out of range")

    recipe_key = str(recipe_index)
    sanitized_override_entry = RecipeTextOverrides.model_validate(
        {
            "ingredients": _sanitize_override_rows(overrides.ingredients),
            "instructions": _sanitize_override_rows(overrides.instructions),
        }
    ).model_dump()

    has_content = bool(
        sanitized_override_entry["ingredients"]
        or sanitized_override_entry["instructions"]
    )
    rpc_override = sanitized_override_entry if has_content else {}

    return _rpc_or_resolve(
        client,
        "set_recipe_override",
        {
            "p_id": recipe_import_id,
            "p_recipe_key": recipe_key,
            "p_override": rpc_override,
        },
        recipe_import_id,
    )
