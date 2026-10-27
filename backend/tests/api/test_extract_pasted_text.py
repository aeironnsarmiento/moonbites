"""Pasted page text for a blog URL whose site blocks the backend's fetch.

The Gemini HTTP call and the save are mocked; the URL must never be fetched.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.api.auth import AuthenticatedAdmin, require_admin_user
from backend.app.core.config import Settings
from backend.app.core.rate_limit import limiter
from backend.app.repositories.recipe_imports import SaveRecipeImportResult
from backend.app.services.blog.page_text import extract_main_text
from backend.app.services.gemini import recipe_parser
from backend.tests.fixtures.gathering_page import (
    GATHERING_DISH,
    GATHERING_URL,
    gathering_html,
    gathering_payload_verbatim,
    gemini_body,
    not_recipe_payload,
)


client = TestClient(app)


def _settings(*, api_key: str | None = "gemini-key") -> Settings:
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
        gemini_rate_limit_per_minute=10,
    )


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


def _gathering_text() -> str:
    # What an admin gets by copying the page's main content in a browser.
    return extract_main_text(BeautifulSoup(gathering_html(), "html.parser"))


def _paste_text(
    url: str,
    page_text: str,
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
    get_page = AsyncMock(side_effect=AssertionError("pasted text must not fetch"))
    with (
        patch("backend.app.services.blog.extractor.get_page", new=get_page),
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
        response = client.post(
            "/api/extract", json={"url": url, "page_text": page_text}
        )
    return response, gemini, save, get_page


def test_pasted_text_saves_the_recipe_under_the_url_without_fetching_it():
    response, gemini, save, get_page = _paste_text(GATHERING_URL, _gathering_text())

    assert response.status_code == 200
    body = response.json()
    assert body["database_saved"] is True
    assert body["parse_status"] == "recipe"
    get_page.assert_not_called()
    gemini.assert_awaited_once()
    kwargs = save.await_args.kwargs
    assert kwargs["submitted_url"] == GATHERING_URL
    assert kwargs["final_url"] == GATHERING_URL
    # With no page title to keep, the record is named after the dish.
    assert kwargs["title"] == GATHERING_DISH
    (recipe,) = kwargs["recipes"]
    assert recipe.name == GATHERING_DISH
    assert len(recipe.instructions) == 8


def test_pasted_text_without_a_recipe_saves_nothing():
    response, _gemini, save, _get_page = _paste_text(
        GATHERING_URL,
        "Latest posts: Lemon Bars, Brownies",
        gemini_payload=not_recipe_payload("This is a list of posts."),
    )

    body = response.json()
    save.assert_not_called()
    assert body["database_saved"] is False
    assert body["parse_status"] == "not_recipe"
    assert body["parse_reason"] == "This is a list of posts."


def test_pasted_text_with_gemini_unavailable_is_a_503_not_a_silent_miss():
    response, gemini, save, _get_page = _paste_text(
        GATHERING_URL, _gathering_text(), settings=_settings(api_key=None)
    )

    assert response.status_code == 503
    assert "recipe parser is unavailable" in response.json()["detail"]
    gemini.assert_not_called()
    save.assert_not_called()


def test_blank_pasted_text_is_rejected():
    response, gemini, _save, _get_page = _paste_text(GATHERING_URL, "   \n ")

    assert response.status_code == 400
    gemini.assert_not_called()


def test_pasted_text_is_refused_for_a_social_video_url():
    response, gemini, _save, _get_page = _paste_text(
        "https://www.youtube.com/watch?v=abc123", _gathering_text()
    )

    assert response.status_code == 400
    gemini.assert_not_called()
