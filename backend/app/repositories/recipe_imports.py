import logging
from dataclasses import dataclass
from typing import NoReturn, Optional
from uuid import uuid4

from ..clients.supabase_client import (
    get_supabase_client,
    get_supabase_public_client,
    get_supabase_user_client,
)
from ..core.config import get_settings
from ..schemas.extract import (
    DUPLICATE_SAVE_MESSAGE,
    SAVE_SUCCESS_MESSAGE,
    CuisineFacet,
    CuisineFacetsResponse,
    HighlightedRecipesResponse,
    NormalizedRecipe,
    PaginatedRecipeImportsResponse,
    RecipeImportRecord,
    RecipeRowEntry,
    RecipeSortOption,
    UpdateRecipeMetadataRequest,
    RecipeTextOverrides,
)
from ..services.cuisine_catalog import (
    CANONICAL_CUISINES,
    OTHER_CUISINE_LABEL,
    canonical_cuisine,
)
from ..services.instagram.urls import (
    InstagramUrlError,
    is_instagram_url,
    parse_instagram_reel_url,
)
from ..services.recipe_identity import (
    dedupe_by_content,
    dedupe_by_source,
    source_identity,
)
from ..services.social.thumbnail_storage import (
    ThumbnailPlatform,
    delete_social_thumbnail_best_effort,
    mirror_social_thumbnail,
)
from ..services.tiktok.extractor import is_tiktok_url
from ..utils.yield_parser import parse_yield


RECIPE_IMPORT_SELECT = "id, submitted_url, final_url, page_title, times_cooked, recipes_json, recipe_overrides_json, image_url, is_favorite, servings, fallback_video_url, linked_recipe_url, created_at"
logger = logging.getLogger(__name__)


class RecipeWriteDeniedError(RuntimeError):
    pass


@dataclass(frozen=True)
class SaveRecipeImportResult:
    saved: bool
    message: str
    image_url: Optional[str]
    id: Optional[str] = None


def _get_read_client(settings):
    return get_supabase_client(settings) or get_supabase_public_client(settings)


def _get_write_client(settings, access_token: Optional[str] = None):
    if access_token:
        return get_supabase_user_client(settings, access_token)

    return get_supabase_client(settings)


RowLayout = list[dict[str, Optional[int | str]]]


def _legacy_rows_to_layout(rows: dict, original_rows: list[str]) -> RowLayout:
    # Legacy overrides were {row_index: text}; indices past the parsed rows
    # were additions.
    edits: dict[int, str] = {}
    for row_index, value in rows.items():
        try:
            edits[int(str(row_index))] = str(value)
        except (TypeError, ValueError):
            continue

    layout: RowLayout = [
        {"source": index, "text": edits.get(index)}
        for index in range(len(original_rows))
    ]
    layout.extend(
        {"source": None, "text": edits[index]}
        for index in sorted(edits)
        if index >= len(original_rows)
    )
    return layout


def _normalize_row_layout(
    rows: object, original_rows: list[str]
) -> Optional[RowLayout]:
    """Return a clean row layout, or None when it shows the rows as parsed."""
    if isinstance(rows, dict):
        rows = _legacy_rows_to_layout(rows, original_rows)
    if not isinstance(rows, list):
        return None

    layout: RowLayout = []
    seen_sources: set[int] = set()
    for entry in rows:
        if isinstance(entry, RecipeRowEntry):
            entry = entry.model_dump()
        if not isinstance(entry, dict):
            continue

        text = entry.get("text")
        text = None if text is None else str(text)
        if text is not None and not text.strip():
            continue

        source = entry.get("source")
        if source is None:
            if text is not None:
                layout.append({"source": None, "text": text})
            continue

        try:
            source = int(source)
        except (TypeError, ValueError):
            continue
        if not 0 <= source < len(original_rows) or source in seen_sources:
            continue

        seen_sources.add(source)
        if text == original_rows[source]:
            text = None
        layout.append({"source": source, "text": text})

    is_identity = len(layout) == len(original_rows) and all(
        entry["source"] == index and entry["text"] is None
        for index, entry in enumerate(layout)
    )
    return None if is_identity else layout


def _normalize_text_overrides(
    sections: object, recipe: NormalizedRecipe
) -> Optional[dict[str, Optional[RowLayout]]]:
    if isinstance(sections, RecipeTextOverrides):
        sections = sections.model_dump()
    if not isinstance(sections, dict):
        return None

    ingredients = _normalize_row_layout(
        sections.get("ingredients"), recipe.ingredients
    )
    instructions = _normalize_row_layout(
        sections.get("instructions"), recipe.instructions
    )
    if ingredients is None and instructions is None:
        return None

    return {"ingredients": ingredients, "instructions": instructions}


def _sanitize_recipe_overrides(
    overrides: object,
    recipes: list[NormalizedRecipe],
) -> dict[str, dict[str, Optional[RowLayout]]]:
    if not isinstance(overrides, dict):
        return {}

    sanitized_overrides: dict[str, dict[str, Optional[RowLayout]]] = {}
    for recipe_index, sections in overrides.items():
        try:
            index = int(str(recipe_index))
        except (TypeError, ValueError):
            continue
        if not 0 <= index < len(recipes):
            continue

        normalized_sections = _normalize_text_overrides(sections, recipes[index])
        if normalized_sections is not None:
            sanitized_overrides[str(index)] = normalized_sections

    return sanitized_overrides


def _sanitize_record(record: dict) -> RecipeImportRecord:
    recipes = [
        NormalizedRecipe.model_validate(item)
        for item in record.get("recipes_json") or []
    ]
    unique_recipes = dedupe_by_content(recipes)

    normalized_record = {
        **record,
        "times_cooked": record.get("times_cooked", 0),
        "image_url": record.get("image_url"),
        "is_favorite": bool(record.get("is_favorite", False)),
        "servings": record.get("servings"),
        "recipes_json": [recipe.model_dump() for recipe in unique_recipes],
        "recipe_overrides_json": _sanitize_recipe_overrides(
            record.get("recipe_overrides_json") or {},
            unique_recipes,
        ),
    }

    return RecipeImportRecord.model_validate(normalized_record)


def is_manual_recipe_url(value: str) -> bool:
    return value.strip().lower().startswith("manual://")


def _build_manual_recipe_url(manual_id: str) -> str:
    return f"manual://{manual_id}"


def _normalize_cuisine_filter(cuisine: Optional[str]) -> Optional[str]:
    if cuisine is None:
        return None

    stripped_cuisine = cuisine.strip()
    if not stripped_cuisine:
        return None

    if stripped_cuisine.casefold() == OTHER_CUISINE_LABEL.casefold():
        return OTHER_CUISINE_LABEL

    return canonical_cuisine(stripped_cuisine) or stripped_cuisine


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


def _find_existing_records_by_source_identity(
    client, table_name: str, canonical_keys: list[str]
) -> list[dict]:
    records: list[dict] = []
    for column in ("submitted_url_canonical", "final_url_canonical"):
        response = (
            client.table(table_name)
            .select("id")
            .in_(column, canonical_keys)
            .execute()
        )
        records.extend(response.data or [])
    return records


async def save_recipe_import(
    submitted_url: str,
    final_url: str,
    title: Optional[str],
    recipes: list[NormalizedRecipe],
    image_url: Optional[str] = None,
    provider_thumbnail_url: Optional[str] = None,
    linked_recipe_url: Optional[str] = None,
    managed_image_storage_path: Optional[str] = None,
    access_token: Optional[str] = None,
) -> SaveRecipeImportResult:
    settings = get_settings()
    client = _get_write_client(settings, access_token)
    if client is None:
        return SaveRecipeImportResult(
            saved=False,
            message="Supabase is not configured yet. Add backend env vars to enable saving.",
            image_url=image_url,
        )

    unique_recipes = dedupe_by_content(recipes)
    servings = next(
        (
            parsed
            for recipe in unique_recipes
            if (parsed := parse_yield(recipe.recipeYield)) is not None
        ),
        None,
    )
    submitted_url_key = source_identity(submitted_url)
    final_url_key = source_identity(final_url)
    candidate_keys = sorted({submitted_url_key, final_url_key})

    try:
        existing_records = _find_existing_records_by_source_identity(
            client,
            settings.supabase_table_name,
            candidate_keys,
        )
    except Exception as error:
        return SaveRecipeImportResult(
            saved=False,
            message=f"Supabase duplicate check failed: {error}",
            image_url=image_url,
        )

    if existing_records:
        return SaveRecipeImportResult(
            saved=True,
            message=DUPLICATE_SAVE_MESSAGE,
            image_url=image_url,
            id=existing_records[0].get("id"),
        )

    recipe_import_id = str(uuid4())
    effective_image_url = image_url
    image_storage_path: Optional[str] = managed_image_storage_path
    if not managed_image_storage_path and provider_thumbnail_url:
        platform = _thumbnail_platform(submitted_url, final_url)
        if platform is None:
            logger.warning(
                "No thumbnail platform for recipe import %s; keeping the provider URL",
                recipe_import_id,
            )
        else:
            try:
                mirrored = await mirror_social_thumbnail(
                    platform,
                    recipe_import_id,
                    provider_thumbnail_url,
                    deadline_seconds=settings.request_timeout_seconds,
                    settings=settings,
                )
                effective_image_url = mirrored.image_url
                image_storage_path = mirrored.storage_path
            except Exception as error:
                logger.warning(
                    "Thumbnail mirror failed for recipe import %s: %s",
                    recipe_import_id,
                    error,
                )

    payload = {
        "id": recipe_import_id,
        "submitted_url": submitted_url,
        "final_url": final_url,
        "submitted_url_canonical": submitted_url_key,
        "final_url_canonical": final_url_key,
        "page_title": title,
        "times_cooked": 0,
        "recipes_json": [recipe.model_dump() for recipe in unique_recipes],
        "recipe_overrides_json": {},
        "image_url": effective_image_url,
        "image_storage_path": image_storage_path,
        "linked_recipe_url": linked_recipe_url,
        "is_favorite": False,
        "servings": servings,
    }

    try:
        client.table(settings.supabase_table_name).insert(payload).execute()
    except Exception as error:
        message = str(error).lower()
        is_duplicate = (
            "unique" in message or "duplicate" in message or "23505" in message
        )
        if is_duplicate:
            if image_storage_path:
                _delete_managed_thumbnail_best_effort(
                    image_storage_path,
                    recipe_import_id=recipe_import_id,
                )
            return SaveRecipeImportResult(
                saved=True,
                message=DUPLICATE_SAVE_MESSAGE,
                image_url=image_url,
            )

        # The insert's actual outcome is ambiguous (e.g. a lost response), so
        # read back by our own generated id before deciding whether the row
        # committed — deleting a provisional object that a committed row now
        # owns would orphan that row's thumbnail.
        committed_record = get_recipe_import(recipe_import_id)
        if committed_record is not None:
            return SaveRecipeImportResult(
                saved=True,
                message=SAVE_SUCCESS_MESSAGE,
                image_url=committed_record.image_url,
                id=recipe_import_id,
            )

        if image_storage_path:
            _delete_managed_thumbnail_best_effort(
                image_storage_path,
                recipe_import_id=recipe_import_id,
            )
        return SaveRecipeImportResult(
            saved=False,
            message=f"Supabase save failed: {error}",
            image_url=image_url,
        )

    return SaveRecipeImportResult(
        saved=True,
        message=SAVE_SUCCESS_MESSAGE,
        image_url=effective_image_url,
        id=recipe_import_id,
    )


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
        "submitted_url_canonical": source_identity(manual_url),
        "final_url_canonical": source_identity(manual_url),
        "page_title": page_title,
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


def _build_paginated_response(
    raw_records: list[dict],
    page: int,
    page_size: int,
    total_count: Optional[int],
) -> PaginatedRecipeImportsResponse:
    sanitized_records = [_sanitize_record(record) for record in raw_records]
    items = dedupe_by_source(sanitized_records)
    if len(items) != len(sanitized_records):
        # Recipe Source Identity is enforced by a unique constraint at write
        # time (submitted_url_canonical/final_url_canonical), so two rows on
        # one page should never collide -- this dedupe is a safety net, not
        # the normal path (see recipe_identity.py). total_count below is an
        # exact SQL count over the full result set, not just this page, so if
        # dedupe ever removes a row here that count silently stops matching
        # what's returned. That mismatch is a symptom: it means a duplicate
        # reached storage despite the constraint. Surface it instead of
        # quietly shipping a short page with a stale total_pages.
        logger.warning(
            "Recipe Source Identity dedupe removed %d row(s) from a page "
            "that should already be unique at the database level -- the "
            "unique constraint on submitted_url_canonical/final_url_canonical "
            "may have been bypassed or dropped.",
            len(sanitized_records) - len(items),
        )

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


def _execute_search_rpc(
    client,
    search_term: str,
    sort: RecipeSortOption,
    cuisine_key: Optional[str],
    favorite: Optional[bool],
    *,
    limit: int,
    offset: int,
) -> list[dict]:
    try:
        response = client.rpc(
            "search_recipe_imports",
            {
                "p_term": search_term,
                "p_cuisine": cuisine_key,
                "p_favorite": favorite,
                "p_sort": sort.value,
                "p_limit": limit,
                "p_offset": offset,
            },
        ).execute()
    except Exception as error:
        raise RuntimeError(f"Supabase read failed: {error}") from error

    return response.data or []


def _search_recipe_imports(
    client,
    search_term: str,
    page: int,
    page_size: int,
    sort: RecipeSortOption,
    cuisine_key: Optional[str],
    favorite: Optional[bool],
) -> PaginatedRecipeImportsResponse:
    offset = (page - 1) * page_size

    raw_records = _execute_search_rpc(
        client,
        search_term,
        sort,
        cuisine_key,
        favorite,
        limit=page_size,
        offset=offset,
    )

    if raw_records:
        total_count = int(raw_records[0].get("total_count") or 0)
    elif page > 1:
        # The window count only rides on returned rows, so a page beyond the
        # end of the matched set would otherwise misreport a real match total
        # as zero; probe the first row for the true count.
        probe_records = _execute_search_rpc(
            client,
            search_term,
            sort,
            cuisine_key,
            favorite,
            limit=1,
            offset=0,
        )
        total_count = (
            int(probe_records[0].get("total_count") or 0) if probe_records else 0
        )
    else:
        total_count = 0

    return _build_paginated_response(raw_records, page, page_size, total_count)


def list_recipe_imports(
    page: int,
    page_size: int,
    sort: RecipeSortOption = RecipeSortOption.recent,
    cuisine: Optional[str] = None,
    favorite: Optional[bool] = None,
    search: Optional[str] = None,
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

    search_term = (search or "").strip()
    if search_term:
        return _search_recipe_imports(
            client,
            search_term,
            page,
            page_size,
            sort,
            cuisine_key,
            favorite,
        )

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
    total_count = getattr(response, "count", None)
    return _build_paginated_response(raw_records, page, page_size, total_count)


def list_highlighted_recipes(
    recent_limit: int,
    favorite_limit: int,
) -> HighlightedRecipesResponse:
    recent = list_recipe_imports(
        page=1,
        page_size=recent_limit,
        sort=RecipeSortOption.recent,
    )
    favorites = list_recipe_imports(
        page=1,
        page_size=favorite_limit,
        sort=RecipeSortOption.recent,
        favorite=True,
    )

    return HighlightedRecipesResponse(
        recent=recent.items,
        favorites=favorites.items,
        total_count=recent.total_count,
        favorite_count=favorites.total_count,
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


SITEMAP_BATCH_SIZE = 1000


@dataclass(frozen=True)
class SitemapEntry:
    id: str
    created_at: str


def list_recipe_sitemap_entries(
    *,
    batch_size: int = SITEMAP_BATCH_SIZE,
) -> list[SitemapEntry]:
    settings = get_settings()
    client = _get_read_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to enable reading saved recipes."
        )

    entries: list[SitemapEntry] = []
    offset = 0
    while True:
        try:
            response = (
                client.table(settings.supabase_table_name)
                .select("id, created_at")
                .order("created_at", desc=True)
                .range(offset, offset + batch_size - 1)
                .execute()
            )
        except Exception as error:
            raise RuntimeError(f"Supabase read failed: {error}") from error

        rows = response.data or []
        entries.extend(
            SitemapEntry(id=str(row["id"]), created_at=str(row["created_at"]))
            for row in rows
            if row.get("id")
        )
        if len(rows) < batch_size:
            return entries
        offset += batch_size


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


def _get_managed_image_state(
    client,
    table_name: str,
    recipe_import_id: str,
) -> tuple[Optional[str], Optional[str]]:
    try:
        response = (
            client.table(table_name)
            .select("image_url, image_storage_path")
            .eq("id", recipe_import_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise RuntimeError(f"Supabase read failed: {error}") from error

    records = response.data or []
    if not records:
        return None, None

    record = records[0]
    image_url = record.get("image_url")
    storage_path = record.get("image_storage_path")
    return (
        image_url if isinstance(image_url, str) else None,
        storage_path if isinstance(storage_path, str) else None,
    )


def _thumbnail_platform(submitted_url: str, final_url: str) -> Optional[ThumbnailPlatform]:
    """Storage-path platform segment for a provider thumbnail, from the
    recipe's own URLs. Exact host match only, never a substring."""
    if is_tiktok_url(final_url) or is_tiktok_url(submitted_url):
        return "tiktok"
    if is_instagram_url(final_url) or is_instagram_url(submitted_url):
        return "instagram"
    return None


def _delete_managed_thumbnail_best_effort(
    storage_path: str,
    *,
    recipe_import_id: str,
) -> None:
    delete_social_thumbnail_best_effort(
        storage_path, context=f"recipe import {recipe_import_id}"
    )


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
        storage_path = response.data[0].get("image_storage_path")
        if isinstance(storage_path, str) and storage_path:
            _delete_managed_thumbnail_best_effort(
                storage_path,
                recipe_import_id=recipe_import_id,
            )
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

    previous_image_url, storage_path = _get_managed_image_state(
        client,
        settings.supabase_table_name,
        recipe_import_id,
    )
    image_changed = image_url != previous_image_url
    payload = {"image_url": image_url}
    if image_changed:
        payload["image_storage_path"] = None

    updated_record = _update_or_resolve(
        client,
        settings.supabase_table_name,
        recipe_import_id,
        payload,
    )
    if updated_record is not None and image_changed and storage_path:
        _delete_managed_thumbnail_best_effort(
            storage_path,
            recipe_import_id=recipe_import_id,
        )
    return updated_record


def _is_same_source_identity(previous_url: str, next_url: str) -> bool:
    if previous_url == next_url:
        return True

    if is_instagram_url(previous_url) and is_instagram_url(next_url):
        try:
            return (
                parse_instagram_reel_url(previous_url).canonical_url
                == parse_instagram_reel_url(next_url).canonical_url
            )
        except InstagramUrlError:
            return False

    return False


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

    payload = {
        "page_title": metadata.title,
        "submitted_url": metadata.source_url,
        "submitted_url_canonical": source_identity(metadata.source_url),
        "recipes_json": [recipe.model_dump() for recipe in recipes],
        "image_url": metadata.image_url,
        "servings": parse_yield(metadata.recipe_yield),
        "fallback_video_url": metadata.fallback_video_url,
    }

    # Only re-point final_url when the source's canonical identity actually
    # changed. Editing an unrelated field, or resubmitting an equivalent URL
    # form (e.g. an Instagram Reel URL with different query params), must not
    # collapse a resolved final_url back onto the submitted one -- TikTok
    # stores its canonical /@handle/video/<id> form there, and the video
    # embed reads it.
    if not _is_same_source_identity(existing_record.submitted_url, metadata.source_url):
        payload["final_url"] = metadata.source_url
        payload["final_url_canonical"] = source_identity(metadata.source_url)
        payload["linked_recipe_url"] = None

    return payload


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
    _, storage_path = _get_managed_image_state(
        client,
        settings.supabase_table_name,
        recipe_import_id,
    )
    identity_changed = "final_url" in payload
    image_changed = metadata.image_url != existing_record.image_url
    clear_managed_thumbnail = image_changed or identity_changed
    if clear_managed_thumbnail:
        payload["image_storage_path"] = None

    updated_record = _update_recipe_import_record(
        client,
        settings.supabase_table_name,
        recipe_import_id,
        payload,
    )
    if clear_managed_thumbnail and storage_path:
        _delete_managed_thumbnail_best_effort(
            storage_path,
            recipe_import_id=recipe_import_id,
        )
    return updated_record


def _reconcile_row_layout(
    layout: Optional[RowLayout],
    new_rows: list[str],
    *,
    old_row_count: Optional[int] = None,
) -> Optional[RowLayout]:
    """Carry a row layout over to freshly parsed rows: rows that no longer
    exist upstream drop out, added rows stay, and rows that are new upstream
    are slotted in after the last parsed row the layout still shows."""
    if layout is None:
        return None

    kept = [
        entry
        for entry in layout
        if entry["source"] is None or entry["source"] < len(new_rows)
    ]
    if old_row_count is not None and len(new_rows) > old_row_count:
        insert_at = max(
            (
                position + 1
                for position, entry in enumerate(kept)
                if entry["source"] is not None
            ),
            default=0,
        )
        kept[insert_at:insert_at] = [
            {"source": index, "text": None}
            for index in range(old_row_count, len(new_rows))
        ]

    return _normalize_row_layout(kept, new_rows)


def _reconcile_recipe_overrides(
    overrides: dict[str, RecipeTextOverrides],
    old_recipes: list[NormalizedRecipe],
    new_recipes: list[NormalizedRecipe],
) -> dict[str, dict[str, Optional[RowLayout]]]:
    reconciled: dict[str, dict[str, Optional[RowLayout]]] = {}

    for recipe_index, sections in overrides.items():
        index = int(recipe_index)
        if index >= len(new_recipes) or index >= len(old_recipes):
            continue

        old_recipe = old_recipes[index]
        new_recipe = new_recipes[index]
        dumped = sections.model_dump()
        ingredients = _reconcile_row_layout(
            dumped["ingredients"],
            new_recipe.ingredients,
            old_row_count=len(old_recipe.ingredients),
        )
        instructions = _reconcile_row_layout(
            dumped["instructions"],
            new_recipe.instructions,
            old_row_count=len(old_recipe.instructions),
        )

        if ingredients is not None or instructions is not None:
            reconciled[recipe_index] = {
                "ingredients": ingredients,
                "instructions": instructions,
            }

    return reconciled


def _build_refetched_recipe_update_payload(
    existing_record: RecipeImportRecord,
    *,
    title: Optional[str],
    image_url: Optional[str],
    recipes: list[NormalizedRecipe],
) -> dict:
    unique_recipes = dedupe_by_content(recipes)
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
        "recipes_json": [recipe.model_dump() for recipe in unique_recipes],
        "recipe_overrides_json": _reconcile_recipe_overrides(
            existing_record.recipe_overrides_json,
            existing_record.recipes_json,
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
    _, storage_path = _get_managed_image_state(
        client,
        settings.supabase_table_name,
        recipe_import_id,
    )
    image_changed = extraction_result.image_url != existing_record.image_url
    if image_changed:
        payload["image_storage_path"] = None

    updated_record = _update_recipe_import_record(
        client,
        settings.supabase_table_name,
        recipe_import_id,
        payload,
    )
    if image_changed and storage_path:
        _delete_managed_thumbnail_best_effort(
            storage_path,
            recipe_import_id=recipe_import_id,
        )
    return updated_record


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

    rpc_override = (
        _normalize_text_overrides(
            overrides, existing_record.recipes_json[recipe_index]
        )
        or {}
    )

    return _rpc_or_resolve(
        client,
        "set_recipe_override",
        {
            "p_id": recipe_import_id,
            "p_recipe_key": str(recipe_index),
            "p_override": rpc_override,
        },
        recipe_import_id,
    )
