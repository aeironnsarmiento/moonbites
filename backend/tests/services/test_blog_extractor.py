from __future__ import annotations

import asyncio

import httpx
import pytest

from app.services.blog.extractor import extract_blog_recipes_from_safe_url
from app.services.public_web import PublicWebError


def _resolver(mapping):
    async def resolve(host, port):
        addresses = mapping[host]
        if isinstance(addresses, Exception):
            raise addresses
        return list(addresses)

    return resolve


def _recipe_page() -> bytes:
    return b"""
    <html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Recipe","name":"Miso Salmon Rice",
      "recipeIngredient":["1 cup rice"],"recipeInstructions":["Cook rice."]}
    </script>
    </head><body></body></html>
    """


def test_fetches_and_parses_a_recipe_page():
    def handler(request: httpx.Request):
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "blog.example"
        return httpx.Response(
            200, content=_recipe_page(), headers={"content-type": "text/html"}
        )

    result = asyncio.run(
        extract_blog_recipes_from_safe_url(
            "https://blog.example/recipe",
            transport=httpx.MockTransport(handler),
            resolver=_resolver({"blog.example": ["93.184.216.34"]}),
        )
    )

    assert result.recipes[0].name == "Miso Salmon Rice"
    assert result.final_url == "https://blog.example/recipe"


def test_rejects_a_private_address():
    # The actual regression this fix exists for: a link found in a TikTok
    # caption or YouTube description is attacker-authorable text, and must
    # not be able to reach an internal address.
    def handler(_request):
        raise AssertionError("network must not be reached")

    with pytest.raises(PublicWebError):
        asyncio.run(
            extract_blog_recipes_from_safe_url(
                "https://blog.example/recipe",
                transport=httpx.MockTransport(handler),
                resolver=_resolver({"blog.example": ["10.0.0.5"]}),
            )
        )


def test_upgrades_a_plain_http_link_before_fetching():
    def handler(request: httpx.Request):
        assert request.url.scheme == "https"
        return httpx.Response(
            200, content=_recipe_page(), headers={"content-type": "text/html"}
        )

    result = asyncio.run(
        extract_blog_recipes_from_safe_url(
            "http://blog.example/recipe",
            transport=httpx.MockTransport(handler),
            resolver=_resolver({"blog.example": ["93.184.216.34"]}),
        )
    )

    assert result.final_url == "https://blog.example/recipe"


def test_malformed_upgrade_target_still_fails_closed():
    def handler(_request):
        raise AssertionError("network must not be reached")

    with pytest.raises(PublicWebError):
        asyncio.run(
            extract_blog_recipes_from_safe_url(
                "ftp://blog.example/recipe",
                transport=httpx.MockTransport(handler),
                resolver=_resolver({}),
            )
        )
