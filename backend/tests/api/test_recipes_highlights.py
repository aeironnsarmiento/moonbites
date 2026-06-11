from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from app.schemas.extract import HighlightedRecipesResponse

client = TestClient(app)


def _highlights_payload() -> HighlightedRecipesResponse:
    return HighlightedRecipesResponse(
        recent=[],
        favorites=[],
        total_count=12,
        favorite_count=3,
    )


def test_recipes_highlights_returns_combined_payload():
    with patch(
        "backend.app.api.routes.recipes.list_highlighted_recipes",
        return_value=_highlights_payload(),
    ) as list_highlighted_recipes:
        response = client.get("/api/recipes/highlights")

    assert response.status_code == 200
    list_highlighted_recipes.assert_called_once_with(
        recent_limit=5,
        favorite_limit=4,
    )
    body = response.json()
    assert body["total_count"] == 12
    assert body["favorite_count"] == 3
    assert body["recent"] == []
    assert body["favorites"] == []


def test_recipes_highlights_passes_custom_limits():
    with patch(
        "backend.app.api.routes.recipes.list_highlighted_recipes",
        return_value=_highlights_payload(),
    ) as list_highlighted_recipes:
        response = client.get(
            "/api/recipes/highlights?recent_limit=8&favorite_limit=2"
        )

    assert response.status_code == 200
    list_highlighted_recipes.assert_called_once_with(
        recent_limit=8,
        favorite_limit=2,
    )


def test_recipes_highlights_returns_503_when_not_configured():
    with patch(
        "backend.app.api.routes.recipes.list_highlighted_recipes",
        side_effect=RuntimeError("Supabase is not configured yet."),
    ):
        response = client.get("/api/recipes/highlights")

    assert response.status_code == 503


def test_recipes_highlights_returns_502_on_read_failure():
    with patch(
        "backend.app.api.routes.recipes.list_highlighted_recipes",
        side_effect=RuntimeError("Supabase read failed: boom"),
    ):
        response = client.get("/api/recipes/highlights")

    assert response.status_code == 502
