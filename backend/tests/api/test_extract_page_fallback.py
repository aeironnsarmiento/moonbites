"""Pasted blog URLs that fall back to Gemini when JSON-LD yields no recipe.

The page fetch and the Gemini HTTP call are both mocked; everything between
them -- page-text extraction, prompt, fabrication check, normalization and the
route's save decision -- runs for real.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.api.auth import AuthenticatedAdmin, require_admin_user
from backend.app.core.config import Settings
from backend.app.core.rate_limit import limiter
from backend.app.repositories.recipe_imports import SaveRecipeImportResult
from backend.app.services.gemini import recipe_parser
from backend.tests.fixtures.gathering_page import (
    GATHERING_DISH,
    GATHERING_SECTION_TITLES,
    GATHERING_URL,
    gathering_html,
    gathering_payload_verbatim,
    gemini_body,
    not_recipe_payload,
)


client = TestClient(app)

FALLBACK_LOGGER = "backend.app.services.blog.page_fallback"
NO_RECIPE_OBJECTS_MESSAGE = (
    "Nothing was saved because no Recipe objects were found on that page."
)


def _settings(*, api_key: str | None = "gemini-key", rate_limit_per_minute: int = 10) -> Settings:
    return Settings(
        request_timeout_seconds=15.0,
        supabase_url=None,
        supabase_publishable_key=None,
        supabase_service_role_key=None,
        supabase_table_name="recipe_imports",
        admin_emails=(),
        cors_origins=("http://localhost:5173",),
        user_agent="test-agent",
        accept_header="text/html",
        accept_language_header="en-US",
        youtube_api_key=None,
        gemini_api_key=api_key,
        gemini_model="gemini-test",
        gemini_timeout_seconds=30.0,
        gemini_rate_limit_per_minute=rate_limit_per_minute,
    )


class _Page:
    def __init__(self, html: str, url: str):
        self.text = html
        self.url = url


class _GeminiResponse:
    def __init__(self, payload: dict):
        self._body = gemini_body(payload)

    def json(self) -> dict:
        return self._body


@pytest.fixture(autouse=True)
def _admin_and_clean_limits():
    limiter.reset()
    recipe_parser.reset_gemini_rate_limiter()
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com", access_token="admin-token"
    )
    yield
    app.dependency_overrides.clear()
    recipe_parser.reset_gemini_rate_limiter()


def _paste(
    url: str,
    html: str,
    *,
    gemini_payload: dict | None = None,
    settings: Settings | None = None,
):
    gemini = AsyncMock(
        return_value=_GeminiResponse(gemini_payload or gathering_payload_verbatim())
    )
    save = AsyncMock(
        return_value=SaveRecipeImportResult(
            saved=True, message="Recipe saved to your collection.", image_url=None
        )
    )
    with (
        patch(
            "backend.app.services.blog.extractor.get_page",
            new=AsyncMock(return_value=_Page(html, url)),
        ),
        patch(
            "backend.app.services.gemini.recipe_parser.get_settings",
            return_value=settings or _settings(),
        ),
        patch(
            "backend.app.services.gemini.recipe_parser._post_generate_content",
            new=gemini,
        ),
        patch("backend.app.api.routes.extract.save_recipe_import", new=save),
    ):
        response = client.post("/api/extract", json={"url": url})
    return response, gemini, save


def _json_ld_page(recipe: dict, *, body: str = "") -> str:
    return (
        "<html><head><title>Lemon Bars</title>"
        f'<script type="application/ld+json">{json.dumps(recipe)}</script>'
        f"</head><body><main>{body}</main></body></html>"
    )


def _fallback_records(caplog) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == FALLBACK_LOGGER]


def test_ae1_gathering_page_saves_with_both_sections_and_eight_steps():
    """Covers AE1 (R1, R3, R6, R9)."""
    response, gemini, save = _paste(GATHERING_URL, gathering_html())

    assert response.status_code == 200
    body = response.json()
    assert body["database_saved"] is True
    assert body["parse_status"] == "recipe"
    gemini.assert_awaited_once()
    save.assert_awaited_once()

    (recipe,) = save.await_args.kwargs["recipes"]
    assert recipe.name == GATHERING_DISH
    assert [section.title for section in recipe.ingredientSections] == GATHERING_SECTION_TITLES
    assert len(recipe.ingredientSections[0].items) == 7
    assert len(recipe.ingredientSections[1].items) == 8
    assert len(recipe.instructions) == 8
    assert save.await_args.kwargs["final_url"] == GATHERING_URL
    # The page's own image is chosen exactly as for a JSON-LD page (R8).
    assert "the-gathering-page-creamy-tuscan-chicken" in save.await_args.kwargs["image_url"]


def test_ae2_complete_json_ld_saves_without_calling_gemini():
    """Covers AE2 (R2)."""
    html = _json_ld_page(
        {
            "@type": "Recipe",
            "name": "Lemon Bars",
            "recipeIngredient": ["1 cup flour", "2 lemons"],
            "recipeInstructions": ["Bake it."],
        }
    )

    response, gemini, save = _paste("https://bars.test/lemon", html)

    assert response.json()["database_saved"] is True
    gemini.assert_not_called()
    (recipe,) = save.await_args.kwargs["recipes"]
    assert recipe.name == "Lemon Bars"


def test_ae3_blog_homepage_calls_gemini_once_and_saves_nothing():
    """Covers AE3 (R1, R7)."""
    html = (
        "<html><head><title>Bakes Blog</title></head><body><main>"
        "<h2>Latest posts</h2><a>Lemon Bars</a><a>Brownies</a>"
        "</main></body></html>"
    )

    response, gemini, save = _paste(
        "https://bakes.test/",
        html,
        gemini_payload=not_recipe_payload("This is a blog homepage listing posts."),
    )

    body = response.json()
    gemini.assert_awaited_once()
    save.assert_not_called()
    assert body["database_saved"] is False
    assert body["parse_status"] == "not_recipe"
    assert body["parse_reason"] == "This is a blog homepage listing posts."
    assert body["recipes"] == []


def test_ae4_incomplete_json_ld_is_replaced_by_the_gemini_recipe():
    """Covers AE4 (R1)."""
    html = _json_ld_page(
        {
            "@type": "Recipe",
            "name": "Lemon Bars",
            "recipeIngredient": ["JSON-LD flour", "JSON-LD lemons"],
        },
        body=(
            "<h1>Lemon Bars</h1><p>2 cups flour</p><p>4 lemons, juiced</p>"
            "<p>Press the crust into the pan.</p><p>Bake the lemon filling.</p>"
        ),
    )
    payload = {
        "is_recipe": True,
        "name": "Lemon Bars",
        "ingredients": ["2 cups flour", "4 lemons, juiced"],
        "instructions": ["Press the crust into the pan.", "Bake the lemon filling."],
        "ingredient_sections": None,
        "recipe_yield": None,
        "recipe_cuisine": None,
        "reason": None,
    }

    response, gemini, save = _paste("https://bars.test/lemon", html, gemini_payload=payload)

    assert response.json()["database_saved"] is True
    gemini.assert_awaited_once()
    (recipe,) = save.await_args.kwargs["recipes"]
    assert recipe.ingredients == ["2 cups flour", "4 lemons, juiced"]
    assert recipe.instructions == ["Press the crust into the pan.", "Bake the lemon filling."]


def test_ae7_exhausted_gemini_limit_ends_with_todays_outcome_and_logs_it(caplog):
    """Covers AE7 (R11, R12)."""
    settings = _settings(rate_limit_per_minute=1)
    assert recipe_parser._rate_limiter.try_acquire(1)

    with caplog.at_level(logging.INFO, logger=FALLBACK_LOGGER):
        response, gemini, save = _paste(GATHERING_URL, gathering_html(), settings=settings)

    body = response.json()
    assert response.status_code == 200
    assert body["database_saved"] is False
    assert body["parse_status"] == "recipe"
    assert body["database_message"] == NO_RECIPE_OBJECTS_MESSAGE
    gemini.assert_not_called()
    save.assert_not_called()

    (record,) = _fallback_records(caplog)
    assert record.fallback_host == "thegatheringpage.com"
    assert record.fallback_trigger == "missing_json_ld"
    assert record.fallback_outcome == "gemini_unavailable"


def test_unconfigured_gemini_keeps_todays_incomplete_recipe_message():
    """R11: an incomplete JSON-LD page keeps today's message when Gemini is off."""
    html = _json_ld_page(
        {"@type": "Recipe", "name": "Lemon Bars", "recipeIngredient": ["1 cup flour"]},
        body="<p>1 cup flour</p><p>Bake the bars.</p>",
    )

    response, gemini, save = _paste(
        "https://bars.test/lemon", html, settings=_settings(api_key=None)
    )

    assert response.status_code == 200
    assert response.json()["database_message"] == (
        "Nothing was saved because recipe objects were found on that page, "
        "but they did not include enough data to extract a complete recipe."
    )
    gemini.assert_not_called()
    save.assert_not_called()


def test_page_with_no_readable_text_skips_the_fallback_and_keeps_todays_message():
    html = _json_ld_page(
        {"@type": "Recipe", "name": "Lemon Bars", "recipeIngredient": ["1 cup flour"]}
    )

    response, gemini, save = _paste("https://bars.test/lemon", html)

    assert response.json()["parse_status"] == "recipe"
    assert response.json()["database_message"].startswith(
        "Nothing was saved because recipe objects were found on that page"
    )
    gemini.assert_not_called()
    save.assert_not_called()
