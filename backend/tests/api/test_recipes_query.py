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


def _empty_page(page_size: int = 10) -> PaginatedRecipeImportsResponse:
    return PaginatedRecipeImportsResponse(
        items=[],
        page=1,
        page_size=page_size,
        total_count=0,
        total_pages=1,
    )


def test_recipes_query_forwards_search_term():
    with patch(
        "backend.app.api.routes.recipes.list_recipe_imports",
        return_value=_empty_page(),
    ) as list_recipe_imports:
        response = client.get("/api/recipes?search=curry")

    assert response.status_code == 200
    assert list_recipe_imports.call_args.kwargs["search"] == "curry"


def test_recipes_query_rejects_one_character_search():
    response = client.get("/api/recipes?search=a")

    assert response.status_code == 422


def test_recipes_query_rejects_over_length_search():
    response = client.get(f"/api/recipes?search={'a' * 101}")

    assert response.status_code == 422


def test_recipes_query_rejects_page_beyond_upper_bound():
    response = client.get("/api/recipes?page=2000000")

    assert response.status_code == 422


def test_recipes_query_treats_search_under_two_chars_after_strip_as_no_search():
    with patch(
        "backend.app.api.routes.recipes.list_recipe_imports",
        return_value=_empty_page(),
    ) as list_recipe_imports:
        response = client.get("/api/recipes?search=%20a")

    assert response.status_code == 200
    assert list_recipe_imports.call_args.kwargs["search"] is None


def test_recipes_query_treats_whitespace_search_as_no_search():
    with patch(
        "backend.app.api.routes.recipes.list_recipe_imports",
        return_value=_empty_page(),
    ) as list_recipe_imports:
        response = client.get("/api/recipes?search=%20%20")

    assert response.status_code == 200
    assert list_recipe_imports.call_args.kwargs["search"] is None


def test_recipes_query_forwards_search_trimmed():
    with patch(
        "backend.app.api.routes.recipes.list_recipe_imports",
        return_value=_empty_page(),
    ) as list_recipe_imports:
        response = client.get("/api/recipes?search=%20curry%20")

    assert response.status_code == 200
    assert list_recipe_imports.call_args.kwargs["search"] == "curry"


def test_recipes_query_defaults_search_to_none():
    with patch(
        "backend.app.api.routes.recipes.list_recipe_imports",
        return_value=_empty_page(),
    ) as list_recipe_imports:
        response = client.get("/api/recipes")

    assert response.status_code == 200
    assert list_recipe_imports.call_args.kwargs["search"] is None


def test_recipes_query_forwards_search_with_other_filters():
    with patch(
        "backend.app.api.routes.recipes.list_recipe_imports",
        return_value=_empty_page(),
    ) as list_recipe_imports:
        response = client.get(
            "/api/recipes?search=soup&cuisine=Italian&favorite=true&sort=times_cooked"
        )

    assert response.status_code == 200
    kwargs = list_recipe_imports.call_args.kwargs
    assert kwargs["search"] == "soup"
    assert kwargs["cuisine"] == "Italian"
    assert kwargs["favorite"] is True
    assert kwargs["sort"].value == "times_cooked"


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
