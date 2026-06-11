from unittest.mock import patch

from app.repositories.recipe_imports import list_highlighted_recipes
from app.schemas.extract import PaginatedRecipeImportsResponse, RecipeSortOption


def _page(total_count: int) -> PaginatedRecipeImportsResponse:
    return PaginatedRecipeImportsResponse(
        items=[],
        page=1,
        page_size=5,
        total_count=total_count,
        total_pages=1,
    )


def test_list_highlighted_recipes_combines_recent_and_favorites():
    with patch(
        "app.repositories.recipe_imports.list_recipe_imports",
        side_effect=[_page(20), _page(6)],
    ) as list_recipe_imports:
        result = list_highlighted_recipes(recent_limit=5, favorite_limit=4)

    assert result.total_count == 20
    assert result.favorite_count == 6
    assert result.recent == []
    assert result.favorites == []

    first_call, second_call = list_recipe_imports.call_args_list
    assert first_call.kwargs["page_size"] == 5
    assert first_call.kwargs["sort"] == RecipeSortOption.recent
    assert "favorite" not in first_call.kwargs
    assert second_call.kwargs["page_size"] == 4
    assert second_call.kwargs["favorite"] is True
