from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.api.auth import AuthenticatedAdmin, require_admin_user
from app.repositories.recipe_imports import _build_metadata_update_payload
from app.schemas.extract import (
    DisplayTitleSource,
    NormalizedRecipe,
    RecipeImportRecord,
    UpdateRecipeMetadataRequest,
)


client = TestClient(app)


@pytest.fixture(autouse=True)
def admin_override():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com",
        access_token="admin-token",
    )
    yield
    app.dependency_overrides.clear()


def _record() -> RecipeImportRecord:
    return RecipeImportRecord(
        id="abc",
        submitted_url="https://old.test/source",
        final_url="https://old.test/source",
        page_title="Old Title",
        times_cooked=0,
        recipes_json=[
            NormalizedRecipe(
                name="Old Title",
                recipeYield="2 servings",
                ingredients=["1 cup rice"],
                instructions=["Cook."],
            )
        ],
        recipe_overrides_json={},
        image_url="https://old.test/image.jpg",
        is_favorite=False,
        servings=2,
        created_at=datetime.now(timezone.utc),
    )


def test_update_metadata_returns_updated_record():
    updated = _record().model_copy(
        update={
            "display_title": "New Title",
            "display_title_source": DisplayTitleSource.user,
            "submitted_url": "https://new.test/source",
            "final_url": "https://new.test/source",
            "image_url": None,
            "servings": 6,
        }
    )
    updated.recipes_json[0] = updated.recipes_json[0].model_copy(
        update={"recipeYield": "6 servings"}
    )

    with patch(
        "backend.app.api.routes.recipes.update_recipe_metadata",
        return_value=updated,
    ) as update_recipe_metadata:
        response = client.patch(
            "/api/recipes/abc/metadata",
            json={
                "title": "New Title",
                "recipe_yield": "6 servings",
                "image_url": None,
                "source_url": "https://new.test/source",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["display_title"] == "New Title"
    assert body["display_title_source"] == "user"
    # The original source title and the extraction's recipe name survive.
    assert body["page_title"] == "Old Title"
    assert body["recipes_json"][0]["name"] == "Old Title"
    assert body["submitted_url"] == "https://new.test/source"
    assert body["final_url"] == "https://new.test/source"
    assert body["recipes_json"][0]["recipeYield"] == "6 servings"
    assert body["servings"] == 6
    update_recipe_metadata.assert_called_once()


def test_update_metadata_accepts_manual_source_url():
    updated = _record().model_copy(
        update={
            "submitted_url": "manual://abc",
            "final_url": "manual://abc",
        }
    )

    with patch(
        "backend.app.api.routes.recipes.update_recipe_metadata",
        return_value=updated,
    ) as update_recipe_metadata:
        response = client.patch(
            "/api/recipes/abc/metadata",
            json={
                "title": "New Title",
                "recipe_yield": "6 servings",
                "image_url": "https://example.com/recipe.jpg",
                "source_url": "manual://abc",
            },
        )

    assert response.status_code == 200
    assert response.json()["submitted_url"] == "manual://abc"
    update_recipe_metadata.assert_called_once()


def test_update_metadata_rejects_invalid_source_url():
    response = client.patch(
        "/api/recipes/abc/metadata",
        json={
            "title": "New Title",
            "recipe_yield": "6 servings",
            "image_url": None,
            "source_url": "recipe://abc",
        },
    )

    assert response.status_code == 422


def test_update_metadata_returns_404_when_missing():
    with patch(
        "backend.app.api.routes.recipes.update_recipe_metadata",
        return_value=None,
    ):
        response = client.patch(
            "/api/recipes/missing/metadata",
            json={
                "title": "New Title",
                "recipe_yield": "6 servings",
                "image_url": None,
                "source_url": "https://new.test/source",
            },
        )

    assert response.status_code == 404


def test_build_metadata_update_payload_recalculates_servings_from_yield():
    payload = _build_metadata_update_payload(
        _record(),
        UpdateRecipeMetadataRequest(
            title="Party Rice",
            recipe_yield="Makes 12 bowls",
            image_url="",
            source_url="https://new.test/source",
        ),
    )

    assert payload["submitted_url"] == "https://new.test/source"
    assert payload["final_url"] == "https://new.test/source"
    assert payload["image_url"] is None
    assert payload["servings"] == 12
    assert payload["recipes_json"][0]["recipeYield"] == "Makes 12 bowls"


def test_build_metadata_update_payload_writes_the_title_to_the_display_title():
    payload = _build_metadata_update_payload(
        _record(),
        UpdateRecipeMetadataRequest(
            title="Party Rice",
            recipe_yield="Makes 12 bowls",
            image_url="",
            source_url="https://new.test/source",
        ),
    )

    assert payload["display_title"] == "Party Rice"
    assert payload["display_title_source"] == "user"


def test_build_metadata_update_payload_leaves_the_original_titles_alone():
    # R7: page_title carries attribution and stays searchable. R8/KTD1: the
    # recipe name is the extraction output and a dedup fingerprint input, so a
    # title edit must not churn it. This replaces the pre-feature assertions
    # that expected the edit to overwrite both.
    payload = _build_metadata_update_payload(
        _record(),
        UpdateRecipeMetadataRequest(
            title="Party Rice",
            recipe_yield="Makes 12 bowls",
            image_url="",
            source_url="https://new.test/source",
        ),
    )

    assert "page_title" not in payload
    assert payload["recipes_json"][0]["name"] == "Old Title"
