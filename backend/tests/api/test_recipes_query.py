from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from app.schemas.extract import PaginatedRecipeImportsResponse


client = TestClient(app)


def test_recipes_query_passes_favorite_and_limit_to_repository():
    response_payload = PaginatedRecipeImportsResponse(
        items=[],
        page=1,
        page_size=4,
        total_count=0,
        total_pages=1,
    )

    with patch(
        "backend.app.api.routes.recipes.list_recipe_imports",
        return_value=response_payload,
    ) as list_recipe_imports:
        response = client.get("/api/recipes?favorite=true&limit=4&sort=times_cooked")

    assert response.status_code == 200
    list_recipe_imports.assert_called_once()
    assert list_recipe_imports.call_args.kwargs["favorite"] is True
    assert list_recipe_imports.call_args.kwargs["page_size"] == 4


def test_recipes_query_accepts_favorites_sort_option():
    response_payload = PaginatedRecipeImportsResponse(
        items=[],
        page=1,
        page_size=20,
        total_count=0,
        total_pages=1,
    )

    with patch(
        "backend.app.api.routes.recipes.list_recipe_imports",
        return_value=response_payload,
    ) as list_recipe_imports:
        response = client.get("/api/recipes?sort=favorites")

    assert response.status_code == 200
    list_recipe_imports.assert_called_once()
    assert list_recipe_imports.call_args.kwargs["sort"].value == "favorites"
