from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

from app.schemas.extract import NormalizedRecipe, RecipeImportRecord
from app.services.recipe_refresher import refetch_recipe_imports


def _recipe(
    name: str = "Old Recipe",
    ingredients: list[str] | None = None,
    instructions: list[str] | None = None,
    recipe_yield: str | None = "2 servings",
) -> NormalizedRecipe:
    return NormalizedRecipe(
        name=name,
        recipeYield=recipe_yield,
        ingredients=ingredients or ["1 cup rice", "1 cup water"],
        instructions=instructions or ["Stir.", "Cook."],
    )


def _record(
    recipe_id: str = "abc",
    *,
    submitted_url: str = "https://old.test/submitted",
    final_url: str = "https://old.test/final",
    overrides: dict | None = None,
) -> RecipeImportRecord:
    return RecipeImportRecord(
        id=recipe_id,
        submitted_url=submitted_url,
        final_url=final_url,
        page_title="Old Title",
        recipe_count=1,
        times_cooked=3,
        recipes_json=[_recipe()],
        recipe_overrides_json=overrides or {},
        image_url="https://old.test/image.jpg",
        is_favorite=True,
        servings=2,
        created_at=datetime.now(timezone.utc),
    )


def _extraction(
    *,
    source_url: str = "https://old.test/final",
    recipes: list[NormalizedRecipe] | None = None,
):
    return Mock(
        source_url=source_url,
        final_url="https://new.test/final",
        title="Fresh Title",
        image_url="https://new.test/image.jpg",
        recipes=recipes if recipes is not None else [_recipe("Fresh Recipe")],
    )


def test_refetch_skips_manual_recipe_imports():
    manual_record = _record(
        submitted_url="manual://abc",
        final_url="manual://abc",
    )

    with (
        patch(
            "app.services.recipe_refresher.list_recipe_import_records_for_refresh",
            return_value=[manual_record],
        ),
        patch("app.services.recipe_refresher.extract_recipes_from_url") as extract,
    ):
        summary = asyncio.run(refetch_recipe_imports())

    assert summary.skipped == 1
    assert summary.updated == 0
    extract.assert_not_called()


def test_refetch_updates_url_recipe_and_preserves_user_fields():
    record = _record(
        overrides={
            "0": {
                "ingredients": {"1": "edited rice"},
                "instructions": {"1": "edited cook"},
            }
        }
    )
    extraction = _extraction(
        recipes=[
            _recipe(
                "Fresh Recipe",
                ingredients=["fresh rice", "fresh water"],
                instructions=["Fresh stir.", "Fresh cook."],
                recipe_yield="4 servings",
            )
        ]
    )

    with (
        patch(
            "app.services.recipe_refresher.list_recipe_import_records_for_refresh",
            return_value=[record],
        ),
        patch(
            "app.services.recipe_refresher.extract_recipes_from_url",
            new=AsyncMock(return_value=extraction),
        ) as extract,
        patch(
            "app.services.recipe_refresher.update_recipe_import_from_extraction",
            return_value=record,
        ) as update,
    ):
        summary = asyncio.run(refetch_recipe_imports())

    assert summary.updated == 1
    extract.assert_awaited_once_with("https://old.test/final")
    update.assert_called_once_with("abc", extraction)


def test_refetch_falls_back_to_submitted_url_when_final_url_fails():
    record = _record()
    extraction = _extraction(source_url="https://old.test/submitted")
    extract = AsyncMock(
        side_effect=[
            HTTPException(status_code=502, detail="Target site returned HTTP 500"),
            extraction,
        ]
    )

    with (
        patch(
            "app.services.recipe_refresher.list_recipe_import_records_for_refresh",
            return_value=[record],
        ),
        patch("app.services.recipe_refresher.extract_recipes_from_url", new=extract),
        patch(
            "app.services.recipe_refresher.update_recipe_import_from_extraction",
            return_value=record,
        ),
    ):
        summary = asyncio.run(refetch_recipe_imports())

    assert summary.updated == 1
    assert [call.args[0] for call in extract.await_args_list] == [
        "https://old.test/final",
        "https://old.test/submitted",
    ]


def test_refetch_records_no_recipe_found_without_update():
    record = _record()

    with (
        patch(
            "app.services.recipe_refresher.list_recipe_import_records_for_refresh",
            return_value=[record],
        ),
        patch(
            "app.services.recipe_refresher.extract_recipes_from_url",
            new=AsyncMock(return_value=_extraction(recipes=[])),
        ),
        patch("app.services.recipe_refresher.update_recipe_import_from_extraction") as update,
    ):
        summary = asyncio.run(refetch_recipe_imports())

    assert summary.no_recipe_found == 1
    update.assert_not_called()


def test_refetch_records_failed_when_all_urls_fail():
    record = _record()

    with (
        patch(
            "app.services.recipe_refresher.list_recipe_import_records_for_refresh",
            return_value=[record],
        ),
        patch(
            "app.services.recipe_refresher.extract_recipes_from_url",
            new=AsyncMock(side_effect=HTTPException(status_code=502, detail="bad")),
        ),
    ):
        summary = asyncio.run(refetch_recipe_imports())

    assert summary.failed == 1
