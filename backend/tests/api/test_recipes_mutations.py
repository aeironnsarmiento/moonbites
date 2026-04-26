from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.api.auth import AuthenticatedAdmin, require_admin_user
from backend.app.repositories.recipe_imports import RecipeWriteDeniedError
from app.schemas.extract import RecipeImportRecord


client = TestClient(app)


@pytest.fixture(autouse=True)
def admin_override():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com",
        access_token="admin-token",
    )
    yield
    app.dependency_overrides.clear()


def _make_record(
    *,
    is_favorite: bool = False,
    servings: int | None = None,
    image_url: str | None = None,
) -> RecipeImportRecord:
    return RecipeImportRecord(
        id="abc",
        submitted_url="https://x.test",
        final_url="https://x.test",
        page_title="Test Recipe",
        recipe_count=1,
        times_cooked=0,
        recipes_json=[],
        recipe_overrides_json={},
        image_url=image_url,
        is_favorite=is_favorite,
        servings=servings,
        created_at=datetime.now(timezone.utc),
    )


def test_toggle_favorite_returns_updated_record():
    with patch(
        "backend.app.api.routes.recipes.toggle_favorite",
        return_value=_make_record(is_favorite=True),
    ):
        response = client.patch("/api/recipes/abc/favorite")

    assert response.status_code == 200
    assert response.json()["is_favorite"] is True


def test_toggle_favorite_returns_404_when_missing():
    with patch("backend.app.api.routes.recipes.toggle_favorite", return_value=None):
        response = client.patch("/api/recipes/missing/favorite")

    assert response.status_code == 404


def test_toggle_favorite_returns_403_when_supabase_write_is_denied():
    with patch(
        "backend.app.api.routes.recipes.toggle_favorite",
        side_effect=RecipeWriteDeniedError(
            "Recipe update denied. Confirm admin email exists in public.recipe_admins."
        ),
    ):
        response = client.patch("/api/recipes/abc/favorite")

    assert response.status_code == 403
    assert "public.recipe_admins" in response.json()["detail"]


def test_update_servings_accepts_positive_integer():
    with patch(
        "backend.app.api.routes.recipes.update_servings",
        return_value=_make_record(servings=4),
    ) as update_servings:
        response = client.patch("/api/recipes/abc/servings", json={"servings": 4})

    assert response.status_code == 200
    assert response.json()["servings"] == 4
    update_servings.assert_called_once_with("abc", 4, access_token="admin-token")


def test_update_servings_rejects_zero():
    response = client.patch("/api/recipes/abc/servings", json={"servings": 0})

    assert response.status_code == 422


def test_update_image_accepts_url_string():
    image_url = "https://example.com/recipe.jpg"
    with patch(
        "backend.app.api.routes.recipes.update_image_url",
        return_value=_make_record(image_url=image_url),
    ) as update_image_url:
        response = client.patch("/api/recipes/abc/image", json={"image_url": image_url})

    assert response.status_code == 200
    assert response.json()["image_url"] == image_url
    update_image_url.assert_called_once_with(
        "abc",
        image_url,
        access_token="admin-token",
    )
