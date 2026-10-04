from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.main import app
from app.schemas.extract import NormalizedRecipe, RecipeImportRecord

client = TestClient(app)

SHELL = '<html><head><title>moonbites</title></head><body><div id="root"></div></body></html>'
RECIPE_ID = "3768e2ba-6398-490f-b16e-e9b05f62e6e9"


def _record() -> RecipeImportRecord:
    return RecipeImportRecord(
        id=RECIPE_ID,
        submitted_url="manual://abc",
        final_url="manual://abc",
        recipes_json=[
            NormalizedRecipe(name="Toast", ingredients=["bread"], instructions=["Toast it."])
        ],
        created_at=datetime(2026, 9, 21, tzinfo=timezone.utc),
    )


def _patch_shell(**kwargs):
    return patch(
        "backend.app.api.routes.recipe_pages.load_shell",
        new=AsyncMock(**kwargs),
    )


def test_recipe_page_renders_metadata():
    with _patch_shell(return_value=SHELL), patch(
        "backend.app.api.routes.recipe_pages.get_recipe_import",
        return_value=_record(),
    ) as get_recipe_import:
        response = client.get(f"/recipe-pages/{RECIPE_ID}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "s-maxage=300" in response.headers["cache-control"]
    assert "<title>Toast · moonbites</title>" in response.text
    get_recipe_import.assert_called_once_with(RECIPE_ID)


def test_recipe_page_returns_plain_shell_with_404_for_missing_recipe():
    with _patch_shell(return_value=SHELL), patch(
        "backend.app.api.routes.recipe_pages.get_recipe_import",
        return_value=None,
    ):
        response = client.get(f"/recipe-pages/{RECIPE_ID}")

    assert response.status_code == 404
    assert response.text == SHELL


def test_recipe_page_skips_lookup_for_non_uuid_ids():
    with _patch_shell(return_value=SHELL), patch(
        "backend.app.api.routes.recipe_pages.get_recipe_import",
    ) as get_recipe_import:
        response = client.get("/recipe-pages/not-a-uuid")

    assert response.status_code == 404
    get_recipe_import.assert_not_called()


def test_recipe_page_falls_back_to_shell_when_supabase_fails():
    with _patch_shell(return_value=SHELL), patch(
        "backend.app.api.routes.recipe_pages.get_recipe_import",
        side_effect=RuntimeError("Supabase read failed"),
    ):
        response = client.get(f"/recipe-pages/{RECIPE_ID}")

    assert response.status_code == 200
    assert response.text == SHELL


def test_recipe_page_returns_502_when_shell_unavailable():
    with _patch_shell(side_effect=RuntimeError("Could not load page shell")):
        response = client.get(f"/recipe-pages/{RECIPE_ID}")

    assert response.status_code == 502
