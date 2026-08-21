from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.schemas.extract import NormalizedRecipe
from app.services.extraction_types import ExtractionResult, ParseStatus
from app.services.gemini.recipe_parser import ParsedCaption
from app.services.tiktok.extractor import (
    extract_recipe_from_tiktok_url,
    is_tiktok_url,
    parse_tiktok_page,
)


CAPTION = "Garlic noodles!\n8 oz noodles\n2 tbsp butter\nBoil and toss. #recipes"


def _settings() -> Settings:
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
        gemini_api_key="gemini-key",
    )


def _item(
    caption: str = CAPTION,
    item_id: str = "7448335796416843051",
    author: str = "emma.recify",
    cover: str | None = "https://cdn.tiktokcdn.com/cover.jpg",
    image_post: dict | None = None,
) -> dict:
    item: dict = {
        "id": item_id,
        "desc": caption,
        "author": {"uniqueId": author},
        "video": {"cover": cover} if cover else {},
    }
    if image_post is not None:
        item["imagePost"] = image_post
    return item


def _hydration_html(item: dict, status_code: int = 0) -> str:
    data = {
        "__DEFAULT_SCOPE__": {
            "webapp.video-detail": {
                "statusCode": status_code,
                "itemInfo": {"itemStruct": item},
            }
        }
    }
    return (
        "<html><head><script id=\"__UNIVERSAL_DATA_FOR_REHYDRATION__\" "
        "type=\"application/json\">"
        + json.dumps(data)
        + "</script></head><body></body></html>"
    )


class _PageResponse:
    def __init__(self, text: str = "", status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://www.tiktok.com")
            response = httpx.Response(status_code=self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "page error", request=request, response=response
            )


class _OembedResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://www.tiktok.com/oembed")
            response = httpx.Response(status_code=self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "oembed error", request=request, response=response
            )

    def json(self) -> dict:
        return self.payload


class _ClientContext:
    def __init__(self, responses: list | None = None, error: Exception | None = None):
        self.responses = list(responses or [])
        self.error = error
        self.requests: list[tuple[str, dict | None]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None, headers=None):
        self.requests.append((url, params))
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)


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


def _not_recipe(
    reason: str = "The caption does not contain a recipe.",
    candidate_name: str | None = None,
) -> ParsedCaption:
    return ParsedCaption(
        raw_recipe={},
        ingredients=[],
        instructions=[],
        is_complete=False,
        parse_status="not_recipe",
        parse_reason=reason,
        candidate_name=candidate_name,
    )


def _run(url: str, *clients, gemini, blog=None):
    client_factory = Mock(side_effect=list(clients))
    patches = [
        patch("app.services.tiktok.extractor.get_settings", return_value=_settings()),
        patch("app.services.tiktok.extractor.httpx.AsyncClient", client_factory),
        patch(
            "app.services.social.caption_recipe.parse_caption_with_gemini",
            new=gemini,
        ),
        patch(
            "app.services.social.caption_recipe.extract_blog_recipes_from_safe_url",
            new=blog or AsyncMock(),
        ),
    ]
    with patches[0], patches[1], patches[2], patches[3]:
        return asyncio.run(extract_recipe_from_tiktok_url(url))


@pytest.mark.parametrize(
    "url",
    [
        "https://www.tiktok.com/@emma.recify/video/7448335796416843051",
        "https://m.tiktok.com/@emma.recify/video/7448335796416843051",
        "https://vm.tiktok.com/ZTabc123/",
        "https://vt.tiktok.com/ZTabc123/",
        "https://www.tiktok.com/t/ZTabc123/",
    ],
)
def test_is_tiktok_url_accepts_known_hosts(url):
    assert is_tiktok_url(url) is True


def test_is_tiktok_url_rejects_other_hosts():
    assert is_tiktok_url("https://example.com/@user/video/1") is False
    assert is_tiktok_url("https://youtu.be/abc") is False


def test_parse_tiktok_page_returns_none_for_shell_page():
    assert parse_tiktok_page("<html><body>verify you are human</body></html>") is None


def test_parse_tiktok_page_returns_none_for_unavailable_status():
    html = _hydration_html(_item(), status_code=10204)
    assert parse_tiktok_page(html) is None


def test_happy_scrape_builds_canonical_url_and_cover_image():
    page = _ClientContext([_PageResponse(_hydration_html(_item()))])
    gemini = AsyncMock(return_value=_parsed_recipe())

    result = _run(
        "https://www.tiktok.com/@emma.recify/video/7448335796416843051?_t=8abc&_r=1",
        page,
        gemini=gemini,
    )

    assert result.parse_status == ParseStatus.RECIPE
    assert result.recipe_node_count == 1
    assert result.recipes[0].name == "Garlic Noodles"
    assert (
        result.source_url
        == "https://www.tiktok.com/@emma.recify/video/7448335796416843051?_t=8abc&_r=1"
    )
    assert (
        result.final_url
        == "https://www.tiktok.com/@emma.recify/video/7448335796416843051"
    )
    assert result.image_url == "https://cdn.tiktokcdn.com/cover.jpg"


def test_shell_page_falls_back_to_oembed_with_canonical_url():
    page = _ClientContext([_PageResponse("<html><body>bot wall</body></html>")])
    oembed = _ClientContext(
        [
            _OembedResponse(
                {
                    "title": CAPTION,
                    "thumbnail_url": "https://cdn.tiktokcdn.com/thumb.jpg",
                    "author_unique_id": "emma.recify",
                    "author_url": "https://www.tiktok.com/@emma.recify",
                    "embed_product_id": "7448335796416843051",
                }
            )
        ]
    )
    gemini = AsyncMock(return_value=_parsed_recipe())

    result = _run("https://vm.tiktok.com/ZTabc123/", page, oembed, gemini=gemini)

    assert result.parse_status == ParseStatus.RECIPE
    assert (
        result.final_url
        == "https://www.tiktok.com/@emma.recify/video/7448335796416843051"
    )
    assert result.image_url == "https://cdn.tiktokcdn.com/thumb.jpg"


def test_scrape_403_twice_falls_back_to_oembed():
    page = _ClientContext([_PageResponse(status_code=403), _PageResponse(status_code=403)])
    oembed = _ClientContext(
        [
            _OembedResponse(
                {
                    "title": CAPTION,
                    "author_unique_id": "emma.recify",
                    "embed_product_id": "7448335796416843051",
                }
            )
        ]
    )
    gemini = AsyncMock(return_value=_parsed_recipe())

    result = _run("https://vm.tiktok.com/ZTabc123/", page, oembed, gemini=gemini)

    assert result.parse_status == ParseStatus.RECIPE
    assert (
        result.final_url
        == "https://www.tiktok.com/@emma.recify/video/7448335796416843051"
    )


def test_caption_with_link_only_uses_blog_link_follow():
    caption = "Full recipe: https://example.com/pasta #recipes"
    page = _ClientContext([_PageResponse(_hydration_html(_item(caption=caption)))])
    gemini = AsyncMock(return_value=_not_recipe(candidate_name="Blog Pasta"))
    blog_result = ExtractionResult(
        source_url="https://example.com/pasta",
        final_url="https://example.com/pasta",
        title="Blog Pasta",
        image_url="https://example.com/pasta.jpg",
        recipe_node_count=1,
        recipes=[
            NormalizedRecipe(
                name="Blog Pasta",
                ingredients=["1 lb pasta"],
                instructions=["Boil pasta."],
            )
        ],
    )
    blog = AsyncMock(return_value=blog_result)

    result = _run(
        "https://www.tiktok.com/@emma.recify/video/7448335796416843051",
        page,
        gemini=gemini,
        blog=blog,
    )

    blog.assert_awaited_once_with("https://example.com/pasta")
    assert result.recipes == blog_result.recipes
    assert result.final_url == "https://example.com/pasta"
    assert (
        result.source_url
        == "https://www.tiktok.com/@emma.recify/video/7448335796416843051"
    )


def test_gemini_429_with_link_in_caption_does_not_follow_it():
    # Was: "still imports via link follow". A Linked Recipe is the one candidate
    # matching the dish the post named, and a failed Gemini call names no dish --
    # so there is nothing to check a candidate against and the link is not
    # followed at all.
    caption = "Full recipe: https://example.com/pasta #recipes"
    page = _ClientContext([_PageResponse(_hydration_html(_item(caption=caption)))])
    gemini = AsyncMock(
        side_effect=HTTPException(status_code=429, detail="parser busy")
    )
    blog = AsyncMock()

    with pytest.raises(HTTPException) as error:
        _run(
            "https://www.tiktok.com/@emma.recify/video/7448335796416843051",
            page,
            gemini=gemini,
            blog=blog,
        )

    assert error.value.status_code == 429
    blog.assert_not_awaited()


def test_gemini_429_without_links_reraises_the_error():
    page = _ClientContext([_PageResponse(_hydration_html(_item()))])
    gemini = AsyncMock(
        side_effect=HTTPException(status_code=429, detail="parser busy")
    )

    with pytest.raises(HTTPException) as error:
        _run(
            "https://www.tiktok.com/@emma.recify/video/7448335796416843051",
            page,
            gemini=gemini,
        )

    assert error.value.status_code == 429


def test_hashtag_only_caption_returns_tiktok_aware_not_recipe():
    caption = "POV: dinner in 10 min #fyp #dinner"
    page = _ClientContext([_PageResponse(_hydration_html(_item(caption=caption)))])
    gemini = AsyncMock(return_value=_not_recipe("The caption does not contain a recipe."))

    result = _run(
        "https://www.tiktok.com/@emma.recify/video/7448335796416843051",
        page,
        gemini=gemini,
    )

    assert result.parse_status == ParseStatus.NOT_RECIPE
    assert result.parse_reason == "The caption does not contain a recipe."
    assert result.recipes == []
    assert result.recipe_node_count == 0


def test_photo_post_uses_first_carousel_image_and_photo_canonical():
    image_post = {
        "images": [
            {"imageURL": {"urlList": ["https://cdn.tiktokcdn.com/carousel-1.jpg"]}},
            {"imageURL": {"urlList": ["https://cdn.tiktokcdn.com/carousel-2.jpg"]}},
        ]
    }
    page = _ClientContext(
        [_PageResponse(_hydration_html(_item(cover=None, image_post=image_post)))]
    )
    gemini = AsyncMock(return_value=_parsed_recipe())

    result = _run(
        "https://www.tiktok.com/@emma.recify/photo/7448335796416843051",
        page,
        gemini=gemini,
    )

    assert result.image_url == "https://cdn.tiktokcdn.com/carousel-1.jpg"
    assert (
        result.final_url
        == "https://www.tiktok.com/@emma.recify/photo/7448335796416843051"
    )


def test_deleted_post_maps_oembed_404_to_not_found():
    page = _ClientContext([_PageResponse("<html></html>")])
    oembed = _ClientContext([_OembedResponse({}, status_code=404)])
    gemini = AsyncMock()

    with pytest.raises(HTTPException) as error:
        _run("https://www.tiktok.com/@gone/video/1", page, oembed, gemini=gemini)

    assert error.value.status_code == 404


def test_both_paths_timing_out_maps_to_504():
    page = _ClientContext(error=httpx.ConnectTimeout("page timeout"))
    oembed = _ClientContext(error=httpx.ConnectTimeout("oembed timeout"))
    gemini = AsyncMock()

    with pytest.raises(HTTPException) as error:
        _run("https://www.tiktok.com/@slow/video/1", page, oembed, gemini=gemini)

    assert error.value.status_code == 504
