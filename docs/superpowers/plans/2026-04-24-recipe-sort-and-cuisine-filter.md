# Recipe Sort & Cuisine Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add server-side sorting (A–Z, most-cooked, recently-added) and a smart cuisine filter (canonicalizing aliases like "American" / "North America" / "United States" to a single category) to the saved-recipe list, surfaced as two dropdowns next to the existing search input on `/recipes`.

**Architecture:**
- Backend: a new `cuisine_catalog` module normalizes free-text cuisine strings via an alias map. The `list_recipe_imports` repository gains a pure `_apply_sort_and_filter` step run after URL-dedup but before pagination, keeping the existing "fetch-all, sanitize, dedupe, slice" flow. A new `GET /api/recipes/cuisines` route returns canonical cuisine facets with counts so the frontend can populate its dropdown.
- Frontend: `RecipeList` grows two Chakra `<Select>` controls next to the search input. `useRecipeList` forwards `sort` / `cuisine` params through controller → service → backend. A new `useCuisineFacets` hook hydrates the cuisine dropdown.
- No DB schema changes — cuisine is derived from the existing `recipes_json` JSONB.

**Tech Stack:** FastAPI, pydantic, Supabase (Postgres), pytest (new), Vite + React 19, Chakra UI v2, React Query, TypeScript.

---

## File Structure

**Create:**
- `backend/requirements-dev.txt` — pytest dependency pin
- `pytest.ini` — test discovery / pythonpath
- `backend/tests/__init__.py`
- `backend/tests/conftest.py`
- `backend/tests/services/__init__.py`
- `backend/tests/services/test_cuisine_catalog.py`
- `backend/tests/repositories/__init__.py`
- `backend/tests/repositories/test_recipe_list_filtering.py`
- `backend/tests/repositories/test_cuisine_facets.py`
- `backend/app/services/cuisine_catalog.py` — alias map + canonicalizer + facet builder
- `src/hooks/useCuisineFacets.ts` — React Query hook for facets

**Modify:**
- `backend/app/schemas/extract.py` — add `CuisineFacet`, `CuisineFacetsResponse`, `RecipeSortOption` enum
- `backend/app/repositories/recipe_imports.py` — sort + filter pure function, updated `list_recipe_imports` signature, new `list_cuisine_facets` function
- `backend/app/api/routes/recipes.py` — accept `sort` / `cuisine` query params, add `GET /api/recipes/cuisines`
- `src/types/api.ts` — `RecipeSortOption`, `CuisineFacet`, `CuisineFacetsResponse`, `RecipeListQuery`
- `src/services/recipeService.ts` — `fetchRecipeImports` accepts `RecipeListQuery`; add `fetchCuisineFacets`
- `src/controllers/recipeController.ts` — `getRecipeListPage` signature, add `getCuisineFacets`
- `src/hooks/useRecipeList.ts` — accept sort / cuisine params in query key + call
- `src/components/RecipeList/RecipeList.tsx` — two new `<Select>` controls and props
- `src/components/RecipeList/RecipeList.scss` — row layout for search + selects
- `src/pages/RecipeListPage/RecipeListPage.tsx` — sort / cuisine state, facets hook, page reset on change

**Unchanged on purpose:** `backend/supabase_schema.sql` (no schema change — cuisine lives inside `recipes_json` JSONB).

---

## Task 1: Bootstrap pytest for the backend

**Files:**
- Create: `backend/requirements-dev.txt`
- Create: `pytest.ini`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/services/__init__.py`
- Create: `backend/tests/services/test_smoke.py`

- [ ] **Step 1: Create the dev requirements file**

Create `backend/requirements-dev.txt`:

```
-r requirements.txt
pytest==8.3.4
```

- [ ] **Step 2: Create the pytest config**

Create `pytest.ini` at repo root:

```ini
[pytest]
testpaths = backend/tests
pythonpath = backend
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 3: Create the test package init files**

Create `backend/tests/__init__.py` (empty).
Create `backend/tests/services/__init__.py` (empty).

- [ ] **Step 4: Create the conftest**

Create `backend/tests/conftest.py`:

```python
import os

# Prevent the application settings cache from picking up any Supabase creds
# during test runs. Individual tests that need settings will patch explicitly.
os.environ.setdefault("SUPABASE_URL", "")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "")
```

- [ ] **Step 5: Write a smoke test that runs**

Create `backend/tests/services/test_smoke.py`:

```python
def test_pytest_runs():
    assert 1 + 1 == 2
```

- [ ] **Step 6: Install dev deps and run the smoke test**

Run from repo root:

```bash
python3 -m pip install -r backend/requirements-dev.txt
python3 -m pytest
```

Expected: `1 passed` and no import errors.

- [ ] **Step 7: Commit**

```bash
git add backend/requirements-dev.txt pytest.ini backend/tests
git commit -m "chore: bootstrap pytest for backend"
```

---

## Task 2: Build the cuisine canonicalizer

**Files:**
- Create: `backend/app/services/cuisine_catalog.py`
- Create: `backend/tests/services/test_cuisine_catalog.py`

- [ ] **Step 1: Write failing tests for the canonicalizer**

Create `backend/tests/services/test_cuisine_catalog.py`:

```python
from app.services.cuisine_catalog import (
    CANONICAL_CUISINES,
    OTHER_CUISINE_LABEL,
    canonical_cuisine,
    collect_canonical_cuisines,
)


def test_canonical_cuisine_direct_match_returns_canonical_label():
    assert canonical_cuisine("American") == "American"


def test_canonical_cuisine_is_case_insensitive():
    assert canonical_cuisine("AMERICAN") == "American"
    assert canonical_cuisine("american") == "American"


def test_canonical_cuisine_trims_whitespace_and_punctuation():
    assert canonical_cuisine("  Italian.  ") == "Italian"
    assert canonical_cuisine("Italian,") == "Italian"


def test_canonical_cuisine_maps_us_aliases_to_american():
    for alias in ("United States", "USA", "U.S.", "North America", "north american"):
        assert canonical_cuisine(alias) == "American", alias


def test_canonical_cuisine_maps_uk_aliases_to_british():
    for alias in ("English", "UK", "United Kingdom", "Scottish", "Welsh", "Irish"):
        assert canonical_cuisine(alias) == "British", alias


def test_canonical_cuisine_maps_asian_country_aliases():
    assert canonical_cuisine("Japan") == "Japanese"
    assert canonical_cuisine("China") == "Chinese"
    assert canonical_cuisine("South Korea") == "Korean"
    assert canonical_cuisine("Thailand") == "Thai"
    assert canonical_cuisine("Vietnam") == "Vietnamese"


def test_canonical_cuisine_returns_none_for_unknown_value():
    assert canonical_cuisine("Klingon") is None


def test_canonical_cuisine_returns_none_for_empty_and_none():
    assert canonical_cuisine("") is None
    assert canonical_cuisine("   ") is None
    assert canonical_cuisine(None) is None  # type: ignore[arg-type]


def test_collect_canonical_cuisines_dedupes_across_aliases():
    recipe_cuisines = [["American", "USA"], ["North America"], ["Italian"]]
    assert collect_canonical_cuisines(recipe_cuisines) == {"American", "Italian"}


def test_collect_canonical_cuisines_handles_none_entries():
    recipe_cuisines = [None, ["Japanese"], []]
    assert collect_canonical_cuisines(recipe_cuisines) == {"Japanese"}


def test_collect_canonical_cuisines_returns_empty_for_no_known_values():
    recipe_cuisines = [["Klingon"], None]
    assert collect_canonical_cuisines(recipe_cuisines) == set()


def test_canonical_cuisines_list_is_sorted_and_nonempty():
    assert CANONICAL_CUISINES, "expected at least one canonical cuisine"
    assert CANONICAL_CUISINES == sorted(CANONICAL_CUISINES)
    assert OTHER_CUISINE_LABEL == "Other"
    assert OTHER_CUISINE_LABEL not in CANONICAL_CUISINES
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `python3 -m pytest backend/tests/services/test_cuisine_catalog.py -v`
Expected: `ModuleNotFoundError: No module named 'app.services.cuisine_catalog'` or equivalent import error / 12 failures.

- [ ] **Step 3: Implement the catalog module**

Create `backend/app/services/cuisine_catalog.py`:

```python
import re
from typing import Iterable, Optional


OTHER_CUISINE_LABEL = "Other"


_CUISINE_ALIASES: dict[str, tuple[str, ...]] = {
    "American": (
        "american",
        "north american",
        "north america",
        "united states",
        "united states of america",
        "usa",
        "us",
        "u s",
        "u s a",
        "southern",
        "southern us",
        "southern united states",
        "cajun",
        "creole",
        "tex mex",
        "tex-mex",
        "new england",
        "southwestern",
    ),
    "British": (
        "british",
        "english",
        "england",
        "uk",
        "u k",
        "united kingdom",
        "great britain",
        "scottish",
        "scotland",
        "welsh",
        "wales",
        "irish",
        "ireland",
    ),
    "Caribbean": (
        "caribbean",
        "jamaican",
        "jamaica",
        "cuban",
        "cuba",
        "puerto rican",
        "puerto rico",
        "dominican",
        "dominican republic",
        "haitian",
        "haiti",
        "trinidadian",
        "bahamian",
    ),
    "Chinese": (
        "chinese",
        "china",
        "cantonese",
        "sichuan",
        "szechuan",
        "szechwan",
        "hunan",
        "shanghainese",
        "taiwanese",
        "taiwan",
        "hong kong",
    ),
    "Filipino": (
        "filipino",
        "philippine",
        "philippines",
        "pinoy",
    ),
    "French": (
        "french",
        "france",
        "provencal",
        "parisian",
    ),
    "German": (
        "german",
        "germany",
        "bavarian",
        "austrian",
        "austria",
    ),
    "Greek": (
        "greek",
        "greece",
    ),
    "Indian": (
        "indian",
        "india",
        "north indian",
        "south indian",
        "punjabi",
        "bengali",
        "gujarati",
    ),
    "Italian": (
        "italian",
        "italy",
        "sicilian",
        "tuscan",
        "roman",
        "neapolitan",
    ),
    "Japanese": (
        "japanese",
        "japan",
    ),
    "Korean": (
        "korean",
        "korea",
        "south korean",
        "south korea",
        "north korean",
        "north korea",
    ),
    "Latin American": (
        "latin american",
        "latin america",
        "south american",
        "south america",
        "central american",
        "central america",
        "peruvian",
        "peru",
        "argentinian",
        "argentine",
        "argentina",
        "brazilian",
        "brazil",
        "chilean",
        "chile",
        "colombian",
        "colombia",
        "venezuelan",
        "venezuela",
        "ecuadorian",
        "ecuador",
    ),
    "Mediterranean": (
        "mediterranean",
    ),
    "Mexican": (
        "mexican",
        "mexico",
    ),
    "Middle Eastern": (
        "middle eastern",
        "middle east",
        "lebanese",
        "lebanon",
        "turkish",
        "turkey",
        "persian",
        "iranian",
        "iran",
        "israeli",
        "israel",
        "syrian",
        "syria",
        "jordanian",
        "jordan",
        "arabic",
        "arab",
    ),
    "North African": (
        "north african",
        "moroccan",
        "morocco",
        "tunisian",
        "tunisia",
        "algerian",
        "algeria",
        "egyptian",
        "egypt",
    ),
    "Russian": (
        "russian",
        "russia",
        "eastern european",
        "polish",
        "poland",
        "ukrainian",
        "ukraine",
        "czech",
        "hungarian",
        "hungary",
    ),
    "Spanish": (
        "spanish",
        "spain",
        "catalan",
        "basque",
    ),
    "Sub-Saharan African": (
        "african",
        "sub saharan",
        "sub-saharan",
        "sub saharan african",
        "nigerian",
        "nigeria",
        "ethiopian",
        "ethiopia",
        "ghanaian",
        "ghana",
        "kenyan",
        "kenya",
        "south african",
        "south africa",
    ),
    "Thai": (
        "thai",
        "thailand",
    ),
    "Vietnamese": (
        "vietnamese",
        "vietnam",
    ),
}


def _build_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, aliases in _CUISINE_ALIASES.items():
        lookup[_normalize_key(canonical)] = canonical
        for alias in aliases:
            lookup[_normalize_key(alias)] = canonical
    return lookup


_PUNCTUATION_RE = re.compile(r"[\.\,\;\:\!\?\(\)\[\]\{\}\"']+")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_key(value: str) -> str:
    stripped = _PUNCTUATION_RE.sub(" ", value.strip().lower())
    return _WHITESPACE_RE.sub(" ", stripped).strip()


_LOOKUP: dict[str, str] = _build_lookup()

CANONICAL_CUISINES: list[str] = sorted(_CUISINE_ALIASES.keys())


def canonical_cuisine(value: Optional[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None

    key = _normalize_key(value)
    if not key:
        return None

    return _LOOKUP.get(key)


def collect_canonical_cuisines(
    recipe_cuisines: Iterable[Optional[Iterable[str]]],
) -> set[str]:
    canonical: set[str] = set()

    for entry in recipe_cuisines:
        if not entry:
            continue

        for raw in entry:
            mapped = canonical_cuisine(raw)
            if mapped is not None:
                canonical.add(mapped)

    return canonical
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest backend/tests/services/test_cuisine_catalog.py -v`
Expected: all 12 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cuisine_catalog.py backend/tests/services/test_cuisine_catalog.py
git commit -m "feat(backend): add cuisine canonicalizer with alias map"
```

---

## Task 3: Add sort + cuisine filter to the list repository

**Files:**
- Modify: `backend/app/schemas/extract.py`
- Modify: `backend/app/repositories/recipe_imports.py`
- Create: `backend/tests/repositories/__init__.py`
- Create: `backend/tests/repositories/test_recipe_list_filtering.py`

- [ ] **Step 1: Add sort enum + response schemas**

Create `backend/tests/repositories/__init__.py` (empty).

Edit `backend/app/schemas/extract.py`. Add these imports / symbols near the top (after the existing `from pydantic ...` import):

```python
from enum import Enum
```

Append to the end of `backend/app/schemas/extract.py`:

```python
class RecipeSortOption(str, Enum):
    RECENT = "recent"
    AZ = "az"
    TIMES_COOKED = "times_cooked"


class CuisineFacet(BaseModel):
    label: str
    count: int


class CuisineFacetsResponse(BaseModel):
    items: list[CuisineFacet]
```

- [ ] **Step 2: Write failing tests for the pure sort/filter function**

Create `backend/tests/repositories/test_recipe_list_filtering.py`:

```python
from datetime import datetime, timezone

from app.repositories.recipe_imports import apply_sort_and_cuisine_filter
from app.schemas.extract import NormalizedRecipe, RecipeImportRecord, RecipeSortOption


def _record(
    *,
    record_id: str,
    primary_name: str,
    cuisines: list[str] | None,
    times_cooked: int,
    created_at: datetime,
) -> RecipeImportRecord:
    recipe = NormalizedRecipe(
        name=primary_name,
        ingredients=["salt"],
        instructions=["mix"],
        recipeCuisine=cuisines,
    )
    return RecipeImportRecord(
        id=record_id,
        submitted_url=f"https://example.com/{record_id}",
        final_url=f"https://example.com/{record_id}",
        page_title=primary_name,
        recipe_count=1,
        times_cooked=times_cooked,
        recipes_json=[recipe],
        recipe_overrides_json={},
        created_at=created_at,
    )


def _fixture_records() -> list[RecipeImportRecord]:
    return [
        _record(
            record_id="a",
            primary_name="Zucchini Fritters",
            cuisines=["Italian"],
            times_cooked=2,
            created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        ),
        _record(
            record_id="b",
            primary_name="apple pie",
            cuisines=["United States"],
            times_cooked=5,
            created_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        ),
        _record(
            record_id="c",
            primary_name="Bibimbap",
            cuisines=["Korean"],
            times_cooked=5,
            created_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        ),
        _record(
            record_id="d",
            primary_name="Beef Tacos",
            cuisines=["North America"],
            times_cooked=0,
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        ),
    ]


def test_sort_recent_orders_by_created_at_desc():
    result = apply_sort_and_cuisine_filter(
        _fixture_records(),
        sort=RecipeSortOption.RECENT,
        cuisine=None,
    )
    assert [record.id for record in result] == ["c", "a", "b", "d"]


def test_sort_az_orders_by_primary_recipe_name_case_insensitive():
    result = apply_sort_and_cuisine_filter(
        _fixture_records(),
        sort=RecipeSortOption.AZ,
        cuisine=None,
    )
    assert [record.id for record in result] == ["b", "d", "c", "a"]


def test_sort_times_cooked_desc_tiebreaks_by_created_at_desc():
    result = apply_sort_and_cuisine_filter(
        _fixture_records(),
        sort=RecipeSortOption.TIMES_COOKED,
        cuisine=None,
    )
    assert [record.id for record in result] == ["c", "b", "a", "d"]


def test_filter_by_american_includes_us_and_north_america_records():
    result = apply_sort_and_cuisine_filter(
        _fixture_records(),
        sort=RecipeSortOption.RECENT,
        cuisine="American",
    )
    assert sorted(record.id for record in result) == ["b", "d"]


def test_filter_by_unknown_cuisine_returns_empty_list():
    result = apply_sort_and_cuisine_filter(
        _fixture_records(),
        sort=RecipeSortOption.RECENT,
        cuisine="Klingon",
    )
    assert result == []


def test_filter_by_none_keeps_all_records():
    result = apply_sort_and_cuisine_filter(
        _fixture_records(),
        sort=RecipeSortOption.RECENT,
        cuisine=None,
    )
    assert len(result) == 4


def test_filter_by_other_matches_records_with_no_canonical_cuisine():
    records = _fixture_records() + [
        _record(
            record_id="e",
            primary_name="Weird Dish",
            cuisines=["Klingon"],
            times_cooked=1,
            created_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
        ),
        _record(
            record_id="f",
            primary_name="No Cuisine",
            cuisines=None,
            times_cooked=0,
            created_at=datetime(2026, 4, 14, tzinfo=timezone.utc),
        ),
    ]

    result = apply_sort_and_cuisine_filter(
        records,
        sort=RecipeSortOption.RECENT,
        cuisine="Other",
    )
    assert sorted(record.id for record in result) == ["e", "f"]
```

- [ ] **Step 3: Run the tests to confirm they fail**

Run: `python3 -m pytest backend/tests/repositories/test_recipe_list_filtering.py -v`
Expected: ImportError on `apply_sort_and_cuisine_filter` — it does not yet exist.

- [ ] **Step 4: Implement the pure sort/filter function**

Edit `backend/app/repositories/recipe_imports.py`.

Update the top-of-file imports so they read:

```python
from typing import Optional
from uuid import uuid4

from ..clients.supabase_client import get_supabase_client
from ..core.config import get_settings
from ..schemas.extract import (
    CuisineFacet,
    CuisineFacetsResponse,
    NormalizedRecipe,
    PaginatedRecipeImportsResponse,
    RecipeImportRecord,
    RecipeSortOption,
    RecipeTextOverrides,
)
from ..services.cuisine_catalog import (
    CANONICAL_CUISINES,
    OTHER_CUISINE_LABEL,
    collect_canonical_cuisines,
)
from ..services.normalizer import dedupe_normalized_recipes
from ..utils.urls import canonicalize_url
```

Then add these helpers immediately after the existing `_dedupe_recipe_import_records` function (around line 131) and **before** `save_recipe_import`:

```python
def _record_canonical_cuisines(record: RecipeImportRecord) -> set[str]:
    return collect_canonical_cuisines(
        recipe.recipeCuisine for recipe in record.recipes_json
    )


def _record_primary_name(record: RecipeImportRecord) -> str:
    for recipe in record.recipes_json:
        if recipe.name:
            return recipe.name
    return record.page_title or ""


def _sort_key_az(record: RecipeImportRecord) -> str:
    return _record_primary_name(record).casefold()


def _sort_key_times_cooked(record: RecipeImportRecord) -> tuple[int, float]:
    # Negate so Python's ascending sort produces desc on cooked count, then
    # desc on created_at for ties.
    return (-record.times_cooked, -record.created_at.timestamp())


def _sort_key_recent(record: RecipeImportRecord) -> float:
    return -record.created_at.timestamp()


_SORT_KEY_FUNCTIONS = {
    RecipeSortOption.AZ: _sort_key_az,
    RecipeSortOption.TIMES_COOKED: _sort_key_times_cooked,
    RecipeSortOption.RECENT: _sort_key_recent,
}


def apply_sort_and_cuisine_filter(
    records: list[RecipeImportRecord],
    *,
    sort: RecipeSortOption,
    cuisine: Optional[str],
) -> list[RecipeImportRecord]:
    if cuisine:
        if cuisine == OTHER_CUISINE_LABEL:
            filtered = [
                record
                for record in records
                if not _record_canonical_cuisines(record)
            ]
        elif cuisine in CANONICAL_CUISINES:
            filtered = [
                record
                for record in records
                if cuisine in _record_canonical_cuisines(record)
            ]
        else:
            filtered = []
    else:
        filtered = list(records)

    sort_key = _SORT_KEY_FUNCTIONS[sort]
    return sorted(filtered, key=sort_key)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest backend/tests/repositories/test_recipe_list_filtering.py -v`
Expected: all 7 tests pass.

- [ ] **Step 6: Wire the function into `list_recipe_imports`**

In `backend/app/repositories/recipe_imports.py`, replace the existing `list_recipe_imports` function with:

```python
def list_recipe_imports(
    page: int,
    page_size: int,
    sort: RecipeSortOption = RecipeSortOption.RECENT,
    cuisine: Optional[str] = None,
) -> PaginatedRecipeImportsResponse:
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
    filtered_records = apply_sort_and_cuisine_filter(
        unique_records, sort=sort, cuisine=cuisine
    )

    total_count = len(filtered_records)
    total_pages = (
        max(1, (total_count + page_size - 1) // page_size) if total_count else 1
    )
    offset = (page - 1) * page_size
    paginated_records = filtered_records[offset : offset + page_size]

    return PaginatedRecipeImportsResponse(
        items=paginated_records,
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=total_pages,
    )
```

- [ ] **Step 7: Re-run the whole test suite**

Run: `python3 -m pytest`
Expected: all existing tests still pass (smoke + canonicalizer + filtering).

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/extract.py backend/app/repositories/recipe_imports.py backend/tests/repositories
git commit -m "feat(backend): sort and cuisine-filter saved recipe list"
```

---

## Task 4: Add cuisine facets function + tests

**Files:**
- Modify: `backend/app/repositories/recipe_imports.py`
- Create: `backend/tests/repositories/test_cuisine_facets.py`

- [ ] **Step 1: Write failing tests for the facet builder**

Create `backend/tests/repositories/test_cuisine_facets.py`:

```python
from datetime import datetime, timezone

from app.repositories.recipe_imports import build_cuisine_facets
from app.schemas.extract import NormalizedRecipe, RecipeImportRecord


def _record(
    record_id: str,
    cuisines: list[str] | None,
) -> RecipeImportRecord:
    recipe = NormalizedRecipe(
        name=f"Recipe {record_id}",
        ingredients=["salt"],
        instructions=["mix"],
        recipeCuisine=cuisines,
    )
    return RecipeImportRecord(
        id=record_id,
        submitted_url=f"https://example.com/{record_id}",
        final_url=f"https://example.com/{record_id}",
        page_title=None,
        recipe_count=1,
        times_cooked=0,
        recipes_json=[recipe],
        recipe_overrides_json={},
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )


def test_facets_return_canonical_labels_with_counts():
    records = [
        _record("a", ["American"]),
        _record("b", ["United States"]),
        _record("c", ["Italian"]),
        _record("d", ["Italy"]),
        _record("e", ["Japanese"]),
    ]

    facets = {item.label: item.count for item in build_cuisine_facets(records)}
    assert facets == {"American": 2, "Italian": 2, "Japanese": 1}


def test_facets_omit_zero_count_categories():
    records = [_record("a", ["Italian"])]
    labels = [item.label for item in build_cuisine_facets(records)]
    assert labels == ["Italian"]


def test_facets_include_other_bucket_when_records_have_no_canonical_cuisine():
    records = [
        _record("a", ["Italian"]),
        _record("b", ["Klingon"]),
        _record("c", None),
    ]
    facets = {item.label: item.count for item in build_cuisine_facets(records)}
    assert facets == {"Italian": 1, "Other": 2}


def test_facets_are_sorted_alphabetically_with_other_last():
    records = [
        _record("a", ["Thai"]),
        _record("b", ["American"]),
        _record("c", ["Klingon"]),
    ]
    labels = [item.label for item in build_cuisine_facets(records)]
    assert labels == ["American", "Thai", "Other"]
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `python3 -m pytest backend/tests/repositories/test_cuisine_facets.py -v`
Expected: ImportError on `build_cuisine_facets`.

- [ ] **Step 3: Implement `build_cuisine_facets` and `list_cuisine_facets`**

In `backend/app/repositories/recipe_imports.py`, add these functions immediately after `apply_sort_and_cuisine_filter`:

```python
def build_cuisine_facets(
    records: list[RecipeImportRecord],
) -> list[CuisineFacet]:
    counts: dict[str, int] = {}
    other_count = 0

    for record in records:
        canonical = _record_canonical_cuisines(record)
        if not canonical:
            other_count += 1
            continue

        for label in canonical:
            counts[label] = counts.get(label, 0) + 1

    facets = [
        CuisineFacet(label=label, count=count)
        for label, count in sorted(counts.items(), key=lambda pair: pair[0])
    ]

    if other_count > 0:
        facets.append(CuisineFacet(label=OTHER_CUISINE_LABEL, count=other_count))

    return facets


def list_cuisine_facets() -> CuisineFacetsResponse:
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
    return CuisineFacetsResponse(items=build_cuisine_facets(unique_records))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest backend/tests/repositories/test_cuisine_facets.py -v`
Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/recipe_imports.py backend/tests/repositories/test_cuisine_facets.py
git commit -m "feat(backend): build cuisine facets from saved recipe imports"
```

---

## Task 5: Expose sort/filter query params + facets route

**Files:**
- Modify: `backend/app/api/routes/recipes.py`

- [ ] **Step 1: Update the recipes router**

Replace the entire contents of `backend/app/api/routes/recipes.py` with:

```python
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ...repositories.recipe_imports import (
    get_recipe_import,
    list_cuisine_facets,
    list_recipe_imports,
    save_manual_recipe,
    update_recipe_overrides,
    update_times_cooked,
)
from ...schemas.extract import (
    CreateManualRecipeRequest,
    CuisineFacetsResponse,
    PaginatedRecipeImportsResponse,
    RecipeImportRecord,
    RecipeSortOption,
    UpdateRecipeOverridesRequest,
    UpdateTimesCookedRequest,
)


router = APIRouter(prefix="/api", tags=["recipes"])


@router.post("/recipes/manual", response_model=RecipeImportRecord)
async def create_manual_recipe(
    payload: CreateManualRecipeRequest,
) -> RecipeImportRecord:
    try:
        return save_manual_recipe(payload.recipe, title=payload.title)
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error


@router.get("/recipes", response_model=PaginatedRecipeImportsResponse)
async def get_saved_recipes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    sort: RecipeSortOption = Query(default=RecipeSortOption.RECENT),
    cuisine: Optional[str] = Query(default=None, max_length=64),
) -> PaginatedRecipeImportsResponse:
    normalized_cuisine = cuisine.strip() if isinstance(cuisine, str) else None
    if normalized_cuisine == "":
        normalized_cuisine = None

    try:
        return list_recipe_imports(
            page=page,
            page_size=page_size,
            sort=sort,
            cuisine=normalized_cuisine,
        )
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error


@router.get("/recipes/cuisines", response_model=CuisineFacetsResponse)
async def get_cuisine_facets() -> CuisineFacetsResponse:
    try:
        return list_cuisine_facets()
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error


@router.get("/recipes/{recipe_import_id}", response_model=RecipeImportRecord)
async def get_saved_recipe(recipe_import_id: str) -> RecipeImportRecord:
    try:
        record = get_recipe_import(recipe_import_id)
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch(
    "/recipes/{recipe_import_id}/times-cooked", response_model=RecipeImportRecord
)
async def patch_times_cooked(
    recipe_import_id: str, payload: UpdateTimesCookedRequest
) -> RecipeImportRecord:
    if payload.delta not in {-1, 1}:
        raise HTTPException(status_code=400, detail="delta must be -1 or 1")

    try:
        record = update_times_cooked(recipe_import_id, payload.delta)
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch(
    "/recipes/{recipe_import_id}/overrides", response_model=RecipeImportRecord
)
async def patch_recipe_overrides(
    recipe_import_id: str, payload: UpdateRecipeOverridesRequest
) -> RecipeImportRecord:
    try:
        record = update_recipe_overrides(
            recipe_import_id,
            payload.recipe_index,
            payload.overrides,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record
```

Note: `GET /recipes/cuisines` is defined **before** `GET /recipes/{recipe_import_id}` so that the literal path wins over the path parameter.

- [ ] **Step 2: Start the backend and smoke-test the new endpoints**

In one terminal:

```bash
npm run dev:backend:mac
```

In another terminal:

```bash
curl -s 'http://127.0.0.1:8000/api/recipes?sort=az&page=1&page_size=5' | head -c 500
curl -s 'http://127.0.0.1:8000/api/recipes?sort=times_cooked&page=1&page_size=5' | head -c 500
curl -s 'http://127.0.0.1:8000/api/recipes/cuisines' | head -c 500
```

Expected: JSON responses, the cuisines response is shaped `{"items": [{"label": "...", "count": N}, ...]}`, and recipes responses contain paginated items.

- [ ] **Step 3: Confirm the full test suite still passes**

Run: `python3 -m pytest`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routes/recipes.py
git commit -m "feat(backend): expose sort/cuisine query params and facets endpoint"
```

---

## Task 6: Add frontend types for sort + cuisine

**Files:**
- Modify: `src/types/api.ts`

- [ ] **Step 1: Extend `src/types/api.ts`**

Replace the contents of `src/types/api.ts` with:

```typescript
import type { NormalizedRecipe, RecipeImportRecord } from "./recipe";

export type ExtractResponse = {
  source_url: string;
  final_url: string;
  title: string | null;
  recipe_count: number;
  recipes: NormalizedRecipe[];
  database_saved: boolean;
  database_message: string | null;
};

export type PaginatedRecipeImportsResponse = {
  items: RecipeImportRecord[];
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
};

export type ApiErrorResponse = {
  detail?: string;
};

export type RecipeSortOption = "recent" | "az" | "times_cooked";

export const RECIPE_SORT_OPTIONS: ReadonlyArray<{
  value: RecipeSortOption;
  label: string;
}> = [
  { value: "recent", label: "Recently added" },
  { value: "az", label: "A – Z" },
  { value: "times_cooked", label: "Most cooked" },
];

export type RecipeListQuery = {
  page: number;
  pageSize: number;
  sort: RecipeSortOption;
  cuisine: string | null;
};

export type CuisineFacet = {
  label: string;
  count: number;
};

export type CuisineFacetsResponse = {
  items: CuisineFacet[];
};
```

- [ ] **Step 2: Typecheck**

Run: `npm run build`
Expected: build succeeds. (It will still succeed because nothing depends on the new types yet.)

- [ ] **Step 3: Commit**

```bash
git add src/types/api.ts
git commit -m "feat(frontend): add sort + cuisine facet types"
```

---

## Task 7: Extend the recipe service

**Files:**
- Modify: `src/services/recipeService.ts`

- [ ] **Step 1: Update the service**

Replace the contents of `src/services/recipeService.ts` with:

```typescript
import { apiRequest } from "./apiClient";
import type {
  CuisineFacetsResponse,
  PaginatedRecipeImportsResponse,
  RecipeListQuery,
} from "../types/api";
import type {
  NormalizedRecipe,
  RecipeImportRecord,
  UpdateRecipeOverridesPayload,
} from "../types/recipe";

export function fetchRecipeImports(
  query: RecipeListQuery,
): Promise<PaginatedRecipeImportsResponse> {
  const searchParams = new URLSearchParams({
    page: String(query.page),
    page_size: String(query.pageSize),
    sort: query.sort,
  });

  if (query.cuisine) {
    searchParams.set("cuisine", query.cuisine);
  }

  return apiRequest<PaginatedRecipeImportsResponse>(
    `/api/recipes?${searchParams.toString()}`,
  );
}

export function fetchCuisineFacets(): Promise<CuisineFacetsResponse> {
  return apiRequest<CuisineFacetsResponse>("/api/recipes/cuisines");
}

export function fetchRecipeImportById(
  recipeImportId: string,
): Promise<RecipeImportRecord> {
  return apiRequest<RecipeImportRecord>(`/api/recipes/${recipeImportId}`);
}

export function createManualRecipeImport(
  recipe: NormalizedRecipe,
  title?: string,
): Promise<RecipeImportRecord> {
  return apiRequest<RecipeImportRecord>("/api/recipes/manual", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      recipe,
      title: title?.trim() || null,
    }),
  });
}

export function updateRecipeImportTimesCooked(
  recipeImportId: string,
  delta: -1 | 1,
): Promise<RecipeImportRecord> {
  return apiRequest<RecipeImportRecord>(
    `/api/recipes/${recipeImportId}/times-cooked`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ delta }),
    },
  );
}

export function patchRecipeImportOverrides(
  recipeImportId: string,
  payload: UpdateRecipeOverridesPayload,
): Promise<RecipeImportRecord> {
  return apiRequest<RecipeImportRecord>(
    `/api/recipes/${recipeImportId}/overrides`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        recipe_index: payload.recipeIndex,
        overrides: payload.overrides,
      }),
    },
  );
}
```

- [ ] **Step 2: Confirm the project still compiles**

Run: `npm run build`
Expected: the call site `fetchRecipeImports(page, pageSize)` inside `src/controllers/recipeController.ts` now fails typecheck because the signature changed. That failure is expected — it is fixed in Task 8.

You may continue to the next task without committing yet; or you can comment out the controller call site temporarily if you need a green build mid-task. Since the next task patches the controller immediately, **do not commit yet** — the two changes ship together.

---

## Task 8: Update the controller to pass sort + cuisine through

**Files:**
- Modify: `src/controllers/recipeController.ts`

- [ ] **Step 1: Update the controller**

Replace the contents of `src/controllers/recipeController.ts` with:

```typescript
import {
  createManualRecipeImport,
  fetchCuisineFacets,
  fetchRecipeImportById,
  fetchRecipeImports,
  patchRecipeImportOverrides,
  updateRecipeImportTimesCooked,
} from "../services/recipeService";
import type {
  CuisineFacetsResponse,
  PaginatedRecipeImportsResponse,
  RecipeListQuery,
} from "../types/api";
import type {
  NormalizedRecipe,
  RecipeCardItem,
  RecipeImportRecord,
  UpdateRecipeOverridesPayload,
} from "../types/recipe";
import {
  dedupeRecipeImportRecord,
  dedupeRecipeImports,
} from "../utils/recipeDedup";

function isManualRecipeUrl(value: string) {
  return value.trim().toLowerCase().startsWith("manual://");
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function mapRecipeImportToCard(record: RecipeImportRecord): RecipeCardItem {
  const primaryRecipe = record.recipes_json[0] ?? null;
  const manualRecord = isManualRecipeUrl(record.submitted_url);

  return {
    id: record.id,
    title: primaryRecipe?.name ?? record.page_title ?? "Untitled recipe import",
    pageTitle: manualRecord ? record.page_title ?? "Manual recipe" : record.page_title,
    submittedUrl: manualRecord ? "Manual recipe" : record.submitted_url,
    createdAtLabel: formatDate(record.created_at),
    recipeCount: record.recipe_count,
    timesCooked: record.times_cooked,
    primaryRecipe,
  };
}

export async function getRecipeListPage(query: RecipeListQuery) {
  const response = await fetchRecipeImports(query);
  if (!response || !Array.isArray(response.items)) {
    throw new Error("Recipes API returned an invalid list response.");
  }

  const items = dedupeRecipeImports(response.items);

  return {
    ...response,
    items: items.map(mapRecipeImportToCard),
  };
}

export async function getCuisineFacets(): Promise<CuisineFacetsResponse> {
  const response = await fetchCuisineFacets();
  if (!response || !Array.isArray(response.items)) {
    throw new Error("Cuisines API returned an invalid response.");
  }
  return response;
}

export async function getRecipeImportDetail(recipeImportId: string) {
  const record = await fetchRecipeImportById(recipeImportId);

  if (!record || !Array.isArray(record.recipes_json)) {
    throw new Error("Recipes API returned an invalid detail response.");
  }

  return dedupeRecipeImportRecord(record);
}

export async function createManualRecipe(
  recipe: NormalizedRecipe,
  title?: string,
) {
  const record = await createManualRecipeImport(recipe, title);

  if (!record || !Array.isArray(record.recipes_json)) {
    throw new Error("Recipes API returned an invalid create response.");
  }

  return dedupeRecipeImportRecord(record);
}

export async function adjustRecipeImportTimesCooked(
  recipeImportId: string,
  delta: -1 | 1,
) {
  const record = await updateRecipeImportTimesCooked(recipeImportId, delta);

  if (!record || !Array.isArray(record.recipes_json)) {
    throw new Error("Recipes API returned an invalid update response.");
  }

  return dedupeRecipeImportRecord(record);
}

export async function updateRecipeImportOverrides(
  recipeImportId: string,
  payload: UpdateRecipeOverridesPayload,
) {
  const record = await patchRecipeImportOverrides(recipeImportId, payload);

  if (!record || !Array.isArray(record.recipes_json)) {
    throw new Error("Recipes API returned an invalid update response.");
  }

  return dedupeRecipeImportRecord(record);
}

export type RecipeListPageData = Omit<
  PaginatedRecipeImportsResponse,
  "items"
> & {
  items: RecipeCardItem[];
};
```

- [ ] **Step 2: Confirm compile**

Run: `npm run build`
Expected: the build fails inside `src/hooks/useRecipeList.ts` because `getRecipeListPage` now takes a query object. That is expected — fixed in Task 9.

Do not commit yet — pair this with the hook update.

---

## Task 9: Update `useRecipeList` and add `useCuisineFacets`

**Files:**
- Modify: `src/hooks/useRecipeList.ts`
- Create: `src/hooks/useCuisineFacets.ts`

- [ ] **Step 1: Update `useRecipeList`**

Replace the contents of `src/hooks/useRecipeList.ts` with:

```typescript
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect } from "react";

import {
  getRecipeListPage,
  type RecipeListPageData,
} from "../controllers/recipeController";
import type { RecipeSortOption } from "../types/api";

type UseRecipeListArgs = {
  page: number;
  pageSize: number;
  sort: RecipeSortOption;
  cuisine: string | null;
};

export function useRecipeList({
  page,
  pageSize,
  sort,
  cuisine,
}: UseRecipeListArgs) {
  const queryClient = useQueryClient();
  const normalizedCuisine = cuisine && cuisine.length > 0 ? cuisine : null;

  const query = useQuery<RecipeListPageData>({
    queryKey: ["recipe-list", page, pageSize, sort, normalizedCuisine],
    queryFn: () =>
      getRecipeListPage({
        page,
        pageSize,
        sort,
        cuisine: normalizedCuisine,
      }),
    placeholderData: keepPreviousData,
  });

  const totalPages = query.data?.total_pages ?? 0;
  const nextPage = page + 1;

  useEffect(() => {
    if (nextPage > totalPages) {
      return;
    }

    void queryClient.prefetchQuery({
      queryKey: ["recipe-list", nextPage, pageSize, sort, normalizedCuisine],
      queryFn: () =>
        getRecipeListPage({
          page: nextPage,
          pageSize,
          sort,
          cuisine: normalizedCuisine,
        }),
      staleTime: 1000 * 60 * 5,
    });
  }, [nextPage, pageSize, queryClient, totalPages, sort, normalizedCuisine]);

  let error = "";
  if (query.error) {
    error =
      query.error instanceof Error
        ? query.error.message
        : "Unable to load recipes.";
  }

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error,
    refresh: async () => {
      await query.refetch();
    },
  };
}
```

- [ ] **Step 2: Create the facets hook**

Create `src/hooks/useCuisineFacets.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";

import { getCuisineFacets } from "../controllers/recipeController";
import type { CuisineFacet } from "../types/api";

export function useCuisineFacets() {
  const query = useQuery<CuisineFacet[]>({
    queryKey: ["cuisine-facets"],
    queryFn: async () => {
      const response = await getCuisineFacets();
      return response.items;
    },
    staleTime: 1000 * 60 * 5,
  });

  return {
    facets: query.data ?? [],
    isLoading: query.isLoading,
    error:
      query.error instanceof Error
        ? query.error.message
        : query.error
          ? "Unable to load cuisine filters."
          : "",
  };
}
```

- [ ] **Step 3: Confirm compile**

Run: `npm run build`
Expected: the build fails inside `src/pages/RecipeListPage/RecipeListPage.tsx` because `useRecipeList` now takes an options object. Expected — fixed in Task 11. Do not commit yet.

---

## Task 10: Extend the `RecipeList` component with sort + cuisine selects

**Files:**
- Modify: `src/components/RecipeList/RecipeList.tsx`
- Modify: `src/components/RecipeList/RecipeList.scss`

- [ ] **Step 1: Update the component**

Replace the contents of `src/components/RecipeList/RecipeList.tsx` with:

```typescript
import {
  Alert,
  AlertDescription,
  AlertIcon,
  Box,
  Input,
  InputGroup,
  InputLeftElement,
  Select,
  SimpleGrid,
  Spinner,
  Stack,
  Text,
} from "@chakra-ui/react";

import type { CuisineFacet, RecipeSortOption } from "../../types/api";
import { RECIPE_SORT_OPTIONS } from "../../types/api";
import type { RecipeCardItem } from "../../types/recipe";
import { RecipeCard } from "../RecipeCard/RecipeCard";
import "./RecipeList.scss";

type RecipeListProps = {
  items: RecipeCardItem[];
  searchTerm: string;
  onSearchTermChange: (value: string) => void;
  sort: RecipeSortOption;
  onSortChange: (value: RecipeSortOption) => void;
  cuisine: string;
  onCuisineChange: (value: string) => void;
  cuisineFacets: CuisineFacet[];
  isLoading: boolean;
  error: string;
};

export function RecipeList({
  items,
  searchTerm,
  onSearchTermChange,
  sort,
  onSortChange,
  cuisine,
  onCuisineChange,
  cuisineFacets,
  isLoading,
  error,
}: RecipeListProps) {
  return (
    <Stack spacing={5} className="recipeList">
      <Stack
        direction={{ base: "column", md: "row" }}
        spacing={3}
        align={{ base: "stretch", md: "center" }}
        className="recipeList__controls"
      >
        <InputGroup className="recipeList__search">
          <InputLeftElement pointerEvents="none">⌕</InputLeftElement>
          <Input
            placeholder="Filter recipes on this page"
            value={searchTerm}
            onChange={(event) => onSearchTermChange(event.target.value)}
          />
        </InputGroup>

        <Select
          aria-label="Sort recipes"
          value={sort}
          onChange={(event) =>
            onSortChange(event.target.value as RecipeSortOption)
          }
          className="recipeList__select"
        >
          {RECIPE_SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>

        <Select
          aria-label="Filter by cuisine"
          value={cuisine}
          onChange={(event) => onCuisineChange(event.target.value)}
          className="recipeList__select"
        >
          <option value="">All cuisines</option>
          {cuisineFacets.map((facet) => (
            <option key={facet.label} value={facet.label}>
              {facet.label} ({facet.count})
            </option>
          ))}
        </Select>
      </Stack>

      {isLoading ? (
        <Stack align="center" justify="center" py={16}>
          <Spinner size="xl" color="brand.600" />
          <Text color="gray.500">Loading saved recipes…</Text>
        </Stack>
      ) : null}

      {!isLoading && error ? (
        <Alert status="error" borderRadius="18px">
          <AlertIcon />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {!isLoading && !error && items.length === 0 ? (
        <Box className="recipeList__empty">
          <Text fontWeight="600">No recipes match these filters.</Text>
          <Text color="gray.500">
            Try a different search term, sort, or cuisine.
          </Text>
        </Box>
      ) : null}

      {!isLoading && !error && items.length > 0 ? (
        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={5}>
          {items.map((item) => (
            <RecipeCard key={item.id} item={item} />
          ))}
        </SimpleGrid>
      ) : null}
    </Stack>
  );
}
```

- [ ] **Step 2: Update the SCSS to accommodate the selects**

Replace the contents of `src/components/RecipeList/RecipeList.scss` with:

```scss
.recipeList {
  width: 100%;

  &__controls {
    width: 100%;
  }

  &__search {
    flex: 1 1 auto;
    min-width: 0;
  }

  &__select {
    flex: 0 0 auto;
    min-width: 160px;
    max-width: 220px;
  }

  &__empty {
    padding: 2rem;
    border-radius: 20px;
    border: 1px dashed rgba(148, 163, 184, 0.35);
    background: rgba(255, 255, 255, 0.65);
    text-align: center;
  }
}
```

---

## Task 11: Wire sort + cuisine state into `RecipeListPage`

**Files:**
- Modify: `src/pages/RecipeListPage/RecipeListPage.tsx`

- [ ] **Step 1: Update the page**

Replace the contents of `src/pages/RecipeListPage/RecipeListPage.tsx` with:

```typescript
import { useEffect, useMemo, useState } from "react";

import { Heading, Stack, Text } from "@chakra-ui/react";

import { PaginationControls } from "../../components/PaginationControls/PaginationControls";
import { RecipeList } from "../../components/RecipeList/RecipeList";
import { useCuisineFacets } from "../../hooks/useCuisineFacets";
import { useRecipeList } from "../../hooks/useRecipeList";
import type { RecipeSortOption } from "../../types/api";
import "./RecipeListPage.scss";

const PAGE_SIZE = 10;
const DEFAULT_SORT: RecipeSortOption = "recent";

export function RecipeListPage() {
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const [sort, setSort] = useState<RecipeSortOption>(DEFAULT_SORT);
  const [cuisine, setCuisine] = useState<string>("");

  const { data, error, isLoading } = useRecipeList({
    page,
    pageSize: PAGE_SIZE,
    sort,
    cuisine: cuisine || null,
  });
  const { facets: cuisineFacets } = useCuisineFacets();

  useEffect(() => {
    setPage(1);
  }, [sort, cuisine]);

  const filteredItems = useMemo(() => {
    if (!data) {
      return [];
    }

    const normalizedQuery = searchTerm.trim().toLowerCase();
    if (!normalizedQuery) {
      return data.items;
    }

    return data.items.filter((item) => {
      const haystacks = [
        item.title,
        item.pageTitle ?? "",
        item.submittedUrl,
        item.primaryRecipe?.cookTime ?? "",
        item.primaryRecipe?.recipeYield ?? "",
      ];

      return haystacks.some((value) =>
        value.toLowerCase().includes(normalizedQuery),
      );
    });
  }, [data, searchTerm]);

  return (
    <Stack spacing={8} className="recipeListPage">
      <Stack spacing={2}>
        <Text color="brand.600" fontWeight="700" fontSize="sm">
          Saved recipes
        </Text>
        <Heading size="xl">Recipe list</Heading>
        <Text color="gray.600">
          Browse saved recipe imports, sort and filter them, and open a recipe
          page for the full normalized JSON.
        </Text>
      </Stack>

      <RecipeList
        items={filteredItems}
        searchTerm={searchTerm}
        onSearchTermChange={setSearchTerm}
        sort={sort}
        onSortChange={setSort}
        cuisine={cuisine}
        onCuisineChange={setCuisine}
        cuisineFacets={cuisineFacets}
        isLoading={isLoading}
        error={error}
      />

      <PaginationControls
        page={data?.page ?? page}
        totalPages={data?.total_pages ?? 1}
        totalCount={data?.total_count ?? 0}
        onPageChange={setPage}
        isDisabled={isLoading}
      />
    </Stack>
  );
}
```

- [ ] **Step 2: Confirm the frontend builds**

Run: `npm run build`
Expected: `tsc -b` passes and Vite build succeeds.

- [ ] **Step 3: Lint**

Run: `npm run lint`
Expected: no new errors introduced.

- [ ] **Step 4: Commit the frontend changes together**

```bash
git add src/types/api.ts src/services/recipeService.ts src/controllers/recipeController.ts src/hooks/useRecipeList.ts src/hooks/useCuisineFacets.ts src/components/RecipeList/RecipeList.tsx src/components/RecipeList/RecipeList.scss src/pages/RecipeListPage/RecipeListPage.tsx
git commit -m "feat(frontend): sort dropdown and cuisine filter on recipe list"
```

---

## Task 12: End-to-end smoke verification

**Files:** none — manual verification only.

- [ ] **Step 1: Start the backend**

```bash
npm run dev:backend:mac
```

Leave this terminal running.

- [ ] **Step 2: Start the frontend**

In another terminal:

```bash
npm run dev
```

Open `http://localhost:5173/recipes`.

- [ ] **Step 3: Verify the sort dropdown**

- Select "Recently added" — confirm the list order matches `created_at` desc.
- Select "A – Z" — confirm the list is alphabetical by the primary recipe name (case insensitive).
- Select "Most cooked" — confirm records with the highest `timesCooked` float to the top.

Expected: the URL query key in the React Query devtools (or via network tab) shows `sort=az` / `sort=times_cooked` / `sort=recent` being sent.

- [ ] **Step 4: Verify the cuisine filter**

- Open the "Filter by cuisine" dropdown. Confirm the options include canonical labels (e.g. "American", "Italian") with counts like `American (3)`.
- Pick "American" — confirm the list includes records whose underlying `recipeCuisine` is one of `American`, `USA`, `United States`, or `North America` (whichever exist in your Supabase data). The cuisine dedup happens in the backend; you should not see any record whose recipes are purely non-American.
- Pick "All cuisines" — confirm everything returns.
- If your data contains records with unknown / no cuisine, confirm an "Other" option appears and filters to those records only.

- [ ] **Step 5: Verify filter change resets pagination**

- Go to page 2 (if there is one), then change the sort. Confirm the page snaps back to 1.

- [ ] **Step 6: Commit (docs) if changes made**

If you touched anything while fixing smoke-test issues, commit them with an appropriately scoped message. Otherwise, no commit is needed.

---

## Self-Review Notes (author's pass)

- **Spec coverage:**
  - Sort by A–Z → Task 3 (`_sort_key_az`), Task 10 dropdown, Task 11 state.
  - Sort by times cooked → Task 3 (`_sort_key_times_cooked`), Task 10 dropdown.
  - Sort by recently added → Task 3 (`_sort_key_recent`), Task 10 dropdown.
  - Smart cuisine grouping (American / North America / United States) → Task 2 alias map (`_CUISINE_ALIASES["American"]` includes `north american`, `north america`, `united states`, `usa`) verified by `test_canonical_cuisine_maps_us_aliases_to_american`.
  - Dropdown next to search bar → Task 10 (`recipeList__controls` row containing the search input + two selects).
  - Backend endpoint / SQL / DB logic → Tasks 3–5. No schema change because `recipes_json` is already JSONB.
- **Placeholder scan:** no TBD / "add validation" / "similar to above" placeholders. Every code step ships real code.
- **Type consistency:** `RecipeSortOption` values (`recent`, `az`, `times_cooked`) match across Python (`RecipeSortOption` enum), TS (`RecipeSortOption` union), and backend query param. `CuisineFacet` has `label` + `count` in both Python and TS. `RecipeListQuery` (TS) shape matches query params constructed in `fetchRecipeImports`. The key literal used to filter the "unknown cuisine" bucket is `OTHER_CUISINE_LABEL = "Other"` in Python and `"Other"` in the UI — consistent.
- **Known caveat for future work:** the backend still fetches all recipe records into memory on every list request (pre-existing behavior). Sort + filter operate on that in-memory set, so this scales linearly with library size. Acceptable for a personal cookbook, but worth revisiting if the dataset grows.
