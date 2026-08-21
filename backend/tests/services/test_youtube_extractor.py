from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import httpx
from fastapi import HTTPException

from app.core.config import Settings
from app.schemas.extract import NormalizedRecipe
from app.services.extraction_types import ExtractionResult, ParseStatus
from app.services.gemini.recipe_parser import ParsedCaption
from app.services.youtube.extractor import (
    extract_recipe_from_youtube_url,
    extract_youtube_video_id,
    is_youtube_url,
)


def _settings(api_key: str | None = "youtube-key") -> Settings:
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
        youtube_api_key=api_key,
        gemini_api_key="gemini-key",
    )


class _AsyncClientContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None):
        self.url = url
        self.params = params
        return self.response


class _Response:
    def __init__(self, payload: dict, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPException(status_code=self.status_code, detail="api error")

    def json(self) -> dict:
        return self.payload


class _HttpStatusResponse:
    def raise_for_status(self) -> None:
        request = httpx.Request("GET", "https://www.googleapis.com/youtube/v3/videos")
        response = httpx.Response(status_code=500, request=request)
        raise httpx.HTTPStatusError(
            "server error",
            request=request,
            response=response,
        )


def _snippet_response(
    description: str,
    title: str = "Garlic Noodles",
    thumbnails: dict | None = None,
) -> _Response:
    return _Response(
        {
            "items": [
                {
                    "id": "abc123XYZ09",
                    "snippet": {
                        "title": title,
                        "description": description,
                        "thumbnails": thumbnails
                        or {"high": {"url": "https://img.youtube.com/high.jpg"}},
                    },
                }
            ]
        }
    )


def _parsed_recipe() -> ParsedCaption:
    return ParsedCaption(
        raw_recipe={
            "@type": "Recipe",
            "name": "Garlic Noodles",
            "recipeIngredient": ["8 oz noodles", "2 tbsp butter"],
            "recipeInstructions": ["Boil noodles.", "Toss with butter."],
        },
        ingredients=["8 oz noodles", "2 tbsp butter"],
        instructions=["Boil noodles.", "Toss with butter."],
        is_complete=True,
        parse_status="recipe",
        parse_reason=None,
    )


def _not_recipe(reason: str) -> ParsedCaption:
    return ParsedCaption(
        raw_recipe={},
        ingredients=[],
        instructions=[],
        is_complete=False,
        parse_status="not_recipe",
        parse_reason=reason,
    )


def _run(url: str, response, *, gemini, blog=None):
    with (
        patch("app.services.youtube.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.youtube.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(response),
        ),
        patch(
            "app.services.youtube.extractor.parse_caption_with_gemini",
            new=gemini,
        ),
        patch(
            "app.services.youtube.extractor.extract_blog_recipes_from_safe_url",
            new=blog or AsyncMock(),
        ),
    ):
        return asyncio.run(extract_recipe_from_youtube_url(url))


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://www.youtube.com/watch?v=abc123XYZ09", "abc123XYZ09"),
        ("https://youtu.be/abc123XYZ09?t=30", "abc123XYZ09"),
        ("https://www.youtube.com/shorts/abc123XYZ09", "abc123XYZ09"),
        ("https://www.youtube.com/embed/abc123XYZ09", "abc123XYZ09"),
        ("https://www.youtube.com/live/abc123XYZ09?feature=share", "abc123XYZ09"),
    ],
)
def test_extract_youtube_video_id_accepts_common_forms(url, video_id):
    assert is_youtube_url(url) is True
    assert extract_youtube_video_id(url) == video_id


def test_extract_youtube_video_id_rejects_playlist_without_video():
    assert is_youtube_url("https://www.youtube.com/playlist?list=abc") is True
    assert extract_youtube_video_id("https://www.youtube.com/playlist?list=abc") is None


def test_complete_gemini_parse_builds_recipe_result():
    gemini = AsyncMock(return_value=_parsed_recipe())
    response = _snippet_response("Ingredients\n8 oz noodles\n2 tbsp butter\nBoil and toss.")

    result = _run("https://youtu.be/abc123XYZ09", response, gemini=gemini)

    gemini.assert_awaited_once()
    assert result.source_url == "https://youtu.be/abc123XYZ09"
    assert result.final_url == "https://youtu.be/abc123XYZ09"
    assert result.title == "Garlic Noodles"
    assert result.image_url == "https://img.youtube.com/high.jpg"
    assert result.recipe_node_count == 1
    assert result.recipes[0].name == "Garlic Noodles"


def test_not_recipe_with_link_in_description_falls_back_to_link_follow():
    gemini = AsyncMock(return_value=_not_recipe("Recipe lives on a linked page."))
    response = _snippet_response("Full recipe: https://example.com/soup")
    blog_result = ExtractionResult(
        source_url="https://example.com/soup",
        final_url="https://example.com/soup/",
        title="Blog Soup",
        image_url="https://example.com/soup.jpg",
        recipe_node_count=1,
        recipes=[
            NormalizedRecipe(
                name="Blog Soup",
                ingredients=["2 cups stock"],
                instructions=["Warm stock."],
            )
        ],
    )
    blog = AsyncMock(return_value=blog_result)

    result = _run("https://youtu.be/abc123XYZ09", response, gemini=gemini, blog=blog)

    blog.assert_awaited_once_with("https://example.com/soup")
    assert result.source_url == "https://youtu.be/abc123XYZ09"
    assert result.final_url == "https://example.com/soup/"
    assert result.recipes == blog_result.recipes


def test_gemini_unconfigured_with_link_still_imports_via_link_follow():
    gemini = AsyncMock(
        side_effect=HTTPException(
            status_code=503, detail="Caption parsing is not configured"
        )
    )
    response = _snippet_response("Full recipe: https://example.com/soup")
    blog_result = ExtractionResult(
        source_url="https://example.com/soup",
        final_url="https://example.com/soup/",
        title="Blog Soup",
        image_url=None,
        recipe_node_count=1,
        recipes=[
            NormalizedRecipe(
                name="Blog Soup",
                ingredients=["2 cups stock"],
                instructions=["Warm stock."],
            )
        ],
    )
    blog = AsyncMock(return_value=blog_result)

    result = _run("https://youtu.be/abc123XYZ09", response, gemini=gemini, blog=blog)

    assert result.recipes == blog_result.recipes


def test_gemini_unconfigured_without_links_raises_503():
    gemini = AsyncMock(
        side_effect=HTTPException(
            status_code=503, detail="Caption parsing is not configured"
        )
    )
    response = _snippet_response("Just vibes, no links here.")

    with pytest.raises(HTTPException) as error:
        _run("https://youtu.be/abc123XYZ09", response, gemini=gemini)

    assert error.value.status_code == 503


def test_gemini_transient_failure_with_link_still_imports_via_link_follow():
    gemini = AsyncMock(side_effect=HTTPException(status_code=429, detail="busy"))
    response = _snippet_response("Full recipe: https://example.com/soup")
    blog_result = ExtractionResult(
        source_url="https://example.com/soup",
        final_url="https://example.com/soup/",
        title="Blog Soup",
        image_url=None,
        recipe_node_count=1,
        recipes=[
            NormalizedRecipe(
                name="Blog Soup",
                ingredients=["2 cups stock"],
                instructions=["Warm stock."],
            )
        ],
    )
    blog = AsyncMock(return_value=blog_result)

    result = _run("https://youtu.be/abc123XYZ09", response, gemini=gemini, blog=blog)

    assert result.recipes == blog_result.recipes


def test_not_recipe_description_returns_source_aware_status():
    gemini = AsyncMock(return_value=_not_recipe("The description is a gaming video."))
    response = _snippet_response("Shroud competes in his first CS LAN Tournament.")

    result = _run("https://youtu.be/abc123XYZ09", response, gemini=gemini)

    assert result.parse_status == ParseStatus.NOT_RECIPE
    assert result.parse_reason == "The description is a gaming video."
    assert result.recipes == []
    assert result.recipe_node_count == 0


def test_unnormalizable_gemini_output_degrades_to_not_recipe():
    broken = ParsedCaption(
        raw_recipe={"@type": "Recipe", "name": ""},
        ingredients=[],
        instructions=[],
        is_complete=True,
        parse_status="recipe",
        parse_reason=None,
    )
    gemini = AsyncMock(return_value=broken)
    response = _snippet_response("Some description without links.")

    result = _run("https://youtu.be/abc123XYZ09", response, gemini=gemini)

    assert result.parse_status == ParseStatus.NOT_RECIPE
    assert result.recipes == []
    assert result.parse_reason == "No recipe was found in the video description."


def test_extract_recipe_from_youtube_url_requires_api_key():
    with patch(
        "app.services.youtube.extractor.get_settings",
        return_value=_settings(api_key=None),
    ):
        with pytest.raises(HTTPException) as error:
            asyncio.run(extract_recipe_from_youtube_url("https://youtu.be/abc123XYZ09"))

    assert error.value.status_code == 503


def test_extract_recipe_from_youtube_url_maps_youtube_api_error_to_502():
    with (
        patch("app.services.youtube.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.youtube.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(_HttpStatusResponse()),
        ),
    ):
        with pytest.raises(HTTPException) as error:
            asyncio.run(extract_recipe_from_youtube_url("https://youtu.be/abc123XYZ09"))

    assert error.value.status_code == 502
    assert error.value.detail == "YouTube API returned HTTP 500"


def test_extract_recipe_from_youtube_url_raises_404_for_missing_video():
    response = _Response({"items": []})

    with (
        patch("app.services.youtube.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.youtube.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(response),
        ),
    ):
        with pytest.raises(HTTPException) as error:
            asyncio.run(extract_recipe_from_youtube_url("https://youtu.be/abc123XYZ09"))

    assert error.value.status_code == 404
