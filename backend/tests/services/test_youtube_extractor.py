from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
import httpx
from fastapi import HTTPException

from app.core.config import Settings
from app.schemas.extract import NormalizedRecipe
from app.services.extraction_types import ExtractionResult, ParseStatus
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
            request = Mock()
            response = Mock(status_code=self.status_code)
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


def test_extract_recipe_from_youtube_url_normalizes_complete_description():
    response = _Response(
        {
            "items": [
                {
                    "id": "abc123XYZ09",
                    "snippet": {
                        "title": "Garlic Noodles",
                        "description": """
Ingredients
- 8 oz noodles
- 2 tbsp butter

Instructions
1. Boil noodles for 8 minutes.
2. Toss noodles with butter.
""",
                        "thumbnails": {
                            "high": {"url": "https://img.youtube.com/high.jpg"}
                        },
                    },
                }
            ]
        }
    )

    with (
        patch("app.services.youtube.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.youtube.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(response),
        ),
        patch("app.services.youtube.extractor.extract_blog_recipes_from_url") as blog,
    ):
        result = asyncio.run(
            extract_recipe_from_youtube_url("https://youtu.be/abc123XYZ09")
        )

    blog.assert_not_called()
    assert result.source_url == "https://youtu.be/abc123XYZ09"
    assert result.final_url == "https://youtu.be/abc123XYZ09"
    assert result.title == "Garlic Noodles"
    assert result.image_url == "https://img.youtube.com/high.jpg"
    assert result.recipe_node_count == 1
    assert result.recipes[0].name == "Garlic Noodles"


def test_extract_recipe_from_youtube_url_uses_video_url_when_instructions_missing():
    response = _Response(
        {
            "items": [
                {
                    "id": "abc123XYZ09",
                    "snippet": {
                        "title": "Rice Bowl",
                        "description": """
Ingredients
Rice -
1 cup rice
2 tbsp soy sauce
""",
                        "thumbnails": {},
                    },
                }
            ]
        }
    )

    with (
        patch("app.services.youtube.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.youtube.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(response),
        ),
        patch("app.services.youtube.extractor.extract_blog_recipes_from_url") as blog,
    ):
        result = asyncio.run(
            extract_recipe_from_youtube_url("https://youtu.be/abc123XYZ09")
        )

    blog.assert_not_called()
    assert result.recipe_node_count == 1
    assert result.recipes[0].ingredients == ["1 cup rice", "2 tbsp soy sauce"]
    assert result.recipes[0].instructions == ["https://youtu.be/abc123XYZ09"]


def test_extract_recipe_from_youtube_url_falls_back_to_ranked_recipe_link():
    response = _Response(
        {
            "items": [
                {
                    "id": "abc123XYZ09",
                    "snippet": {
                        "title": "Video Soup",
                        "description": "Full recipe: https://example.com/soup",
                        "thumbnails": {
                            "default": {"url": "https://img.youtube.com/default.jpg"}
                        },
                    },
                }
            ]
        }
    )
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

    with (
        patch("app.services.youtube.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.youtube.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(response),
        ),
        patch(
            "app.services.youtube.extractor.extract_blog_recipes_from_url",
            new=AsyncMock(return_value=blog_result),
        ) as blog,
    ):
        result = asyncio.run(
            extract_recipe_from_youtube_url("https://youtu.be/abc123XYZ09")
        )

    blog.assert_awaited_once_with("https://example.com/soup")
    assert result.source_url == "https://youtu.be/abc123XYZ09"
    assert result.final_url == "https://example.com/soup/"
    assert result.title == "Blog Soup"
    assert result.image_url == "https://example.com/soup.jpg"
    assert result.recipes == blog_result.recipes


def test_extract_recipe_from_youtube_url_returns_not_recipe_for_gaming_video():
    response = _Response(
        {
            "items": [
                {
                    "id": "shroud123",
                    "snippet": {
                        "title": "Shroud CS LAN",
                        "description": """
Shroud competes in his first CS LAN Tournament in nearly a DECADE.

SECRET PROMO CODE ON ALL LOGITECH PRODUCTS: shroud
https://www.logitechg.com

THE PERFECT PC - https://maingear.com/shroud-ref

► Follow me!
TWITTER →   / shroud
TWITCH →   / shroud

#shroud #gaming #cs2
""",
                        "thumbnails": {
                            "high": {"url": "https://img.youtube.com/shroud.jpg"}
                        },
                    },
                }
            ]
        }
    )

    with (
        patch("app.services.youtube.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.youtube.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(response),
        ),
        patch(
            "app.services.youtube.extractor.extract_blog_recipes_from_url",
            new=AsyncMock(),
        ) as blog,
    ):
        result = asyncio.run(
            extract_recipe_from_youtube_url("https://youtu.be/shroud123")
        )

    blog.assert_not_called()
    assert result.parse_status == ParseStatus.NOT_RECIPE
    assert result.parse_reason is not None
    assert result.recipes == []
    assert result.recipe_node_count == 0
    assert result.title == "Shroud CS LAN"


def test_extract_recipe_from_youtube_url_returns_partial_metadata_without_recipe():
    response = _Response(
        {
            "items": [
                {
                    "id": "abc123XYZ09",
                    "snippet": {
                        "title": "Video Soup",
                        "description": "No recipe here",
                        "thumbnails": {
                            "medium": {"url": "https://img.youtube.com/medium.jpg"}
                        },
                    },
                }
            ]
        }
    )

    with (
        patch("app.services.youtube.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.youtube.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(response),
        ),
    ):
        result = asyncio.run(
            extract_recipe_from_youtube_url("https://youtu.be/abc123XYZ09")
        )

    assert result.title == "Video Soup"
    assert result.image_url == "https://img.youtube.com/medium.jpg"
    assert result.recipe_node_count == 0
    assert result.recipes == []


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
