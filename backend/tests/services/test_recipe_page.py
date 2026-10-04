import json
import re
from datetime import datetime, timezone

from app.core.config import get_settings
from app.schemas.extract import NormalizedRecipe, RecipeImportRecord, RecipeTextOverrides
from app.services.recipe_page import render_recipe_page

SHELL = """<!doctype html>
<html lang="en">
  <head>
    <title>moonbites</title>
    <script type="module" src="/assets/index-abc.js"></script>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>"""

RECIPE_ID = "3768e2ba-6398-490f-b16e-e9b05f62e6e9"


def _record(**overrides) -> RecipeImportRecord:
    fields = {
        "id": RECIPE_ID,
        "submitted_url": "https://blog.example.com/pancakes",
        "final_url": "https://blog.example.com/pancakes/",
        "page_title": "Best Pancakes | Example Blog",
        "recipes_json": [
            NormalizedRecipe(
                name="Fluffy Pancakes",
                recipeYield="4 servings",
                cookTime="PT20M",
                recipeCuisine=["American"],
                ingredients=["2 cups flour", "2 eggs", "1 cup milk"],
                instructions=["Whisk everything.", "Cook on a griddle."],
            )
        ],
        "image_url": "https://cdn.example.com/pancakes.jpg",
        "created_at": datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),
    }
    fields.update(overrides)
    return RecipeImportRecord(**fields)


def _json_ld(html: str):
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert match
    return json.loads(match.group(1))


def test_injects_title_meta_and_keeps_app_scripts():
    html = render_recipe_page(SHELL, _record(), get_settings())

    assert "<title>Fluffy Pancakes · moonbites</title>" in html
    assert html.count("<title>") == 1
    assert '<meta property="og:title" content="Fluffy Pancakes" />' in html
    assert (
        '<meta property="og:image" content="https://cdn.example.com/pancakes.jpg" />'
        in html
    )
    assert (
        f'<meta property="og:url" content="https://moonbites-blue.vercel.app/recipes/{RECIPE_ID}" />'
        in html
    )
    assert 'content="Fluffy Pancakes recipe with 2 cups flour, 2 eggs, 1 cup milk"' in html
    assert '<script type="module" src="/assets/index-abc.js"></script>' in html
    assert '<div id="root"></div>' in html


def test_imported_recipe_canonicalizes_to_source():
    html = render_recipe_page(SHELL, _record(), get_settings())

    assert '<link rel="canonical" href="https://blog.example.com/pancakes/" />' in html
    assert _json_ld(html)["isBasedOn"] == "https://blog.example.com/pancakes/"


def test_manual_recipe_canonicalizes_to_itself():
    record = _record(submitted_url="manual://abc", final_url="manual://abc")
    html = render_recipe_page(SHELL, record, get_settings())

    assert (
        f'<link rel="canonical" href="https://moonbites-blue.vercel.app/recipes/{RECIPE_ID}" />'
        in html
    )
    assert "isBasedOn" not in _json_ld(html)
    assert "manual://" not in html


def test_json_ld_describes_recipe():
    data = _json_ld(render_recipe_page(SHELL, _record(), get_settings()))

    assert data["@type"] == "Recipe"
    assert data["name"] == "Fluffy Pancakes"
    assert data["recipeIngredient"] == ["2 cups flour", "2 eggs", "1 cup milk"]
    assert data["recipeInstructions"][1] == {
        "@type": "HowToStep",
        "position": 2,
        "text": "Cook on a griddle.",
    }
    assert data["cookTime"] == "PT20M"
    assert data["recipeYield"] == "4 servings"
    assert data["image"] == ["https://cdn.example.com/pancakes.jpg"]


def test_human_readable_cook_time_is_omitted_from_json_ld():
    recipe = _record().recipes_json[0].model_copy(update={"cookTime": "20 mins"})
    data = _json_ld(render_recipe_page(SHELL, _record(recipes_json=[recipe]), get_settings()))

    assert "cookTime" not in data


def test_applies_row_overrides():
    record = _record(
        recipe_overrides_json={
            "0": RecipeTextOverrides(
                ingredients=[
                    {"source": 1, "text": None},
                    {"source": 0, "text": "3 cups flour"},
                    {"source": None, "text": "pinch of salt"},
                ]
            )
        }
    )
    html = render_recipe_page(SHELL, record, get_settings())

    assert _json_ld(html)["recipeIngredient"] == ["2 eggs", "3 cups flour", "pinch of salt"]
    assert "<li>pinch of salt</li>" in html
    assert "1 cup milk" not in html


def test_noscript_copy_precedes_root():
    html = render_recipe_page(SHELL, _record(), get_settings())

    noscript = html.index("<noscript>")
    assert noscript < html.index('<div id="root"></div>')
    assert "<h1>Fluffy Pancakes</h1>" in html
    assert "<li>Whisk everything.</li>" in html


def test_escapes_scraped_text_in_html_and_json_ld():
    hostile = '</script><script>alert(1)</script>"><img src=x>'
    recipe = _record().recipes_json[0].model_copy(
        update={"name": hostile, "ingredients": [hostile]}
    )
    html = render_recipe_page(SHELL, _record(recipes_json=[recipe]), get_settings())

    assert "<script>alert(1)" not in html
    assert "<img src=x>" not in html
    assert _json_ld(html)["name"] == hostile


def test_load_shell_caches_and_serves_stale_on_error():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    import httpx

    from app.services import recipe_page

    recipe_page._shell_cache.clear()
    ok = MagicMock(text=SHELL)
    ok.raise_for_status.return_value = None
    get = AsyncMock(side_effect=[ok, httpx.ConnectError("down")])

    with patch.object(httpx.AsyncClient, "get", get):
        assert asyncio.run(recipe_page.load_shell(get_settings())) == SHELL
        assert asyncio.run(recipe_page.load_shell(get_settings())) == SHELL
        assert get.await_count == 1

        with patch.object(recipe_page, "SHELL_CACHE_SECONDS", 0):
            assert asyncio.run(recipe_page.load_shell(get_settings())) == SHELL
        assert get.await_count == 2

    recipe_page._shell_cache.clear()
