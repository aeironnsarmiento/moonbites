import asyncio
import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.schemas.extract import IngredientSection
from app.core.config import Settings
from app.services.extractor import extract_recipes_from_url
from app.services.gemini.normalizer import GeminiNormalizationResult
from app.services.normalizer import collect_recipe_nodes, normalize_recipe


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
        gemini_api_key=None,
        gemini_normalization_enabled=False,
        gemini_model="gemini-3-flash-preview",
        gemini_timeout_seconds=8.0,
        gemini_rate_limit_per_minute=3,
    )


def _gemini_recipe(name: str = "Gemini Recipe"):
    from app.schemas.extract import NormalizedRecipe

    return NormalizedRecipe(
        name=name,
        ingredients=["1 cup gemini flour"],
        instructions=["Bake with Gemini."],
    )


class _AsyncClientContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Response:
    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url
        self.extensions: dict = {}

    def raise_for_status(self) -> None:
        return None

    async def aread(self) -> bytes:
        return self.text.encode()

    async def aclose(self) -> None:
        return None


def test_collect_recipe_nodes_matches_lowercase_recipe_type():
    payload = {
        "@context": "https://schema.org",
        "@type": "recipe",
        "name": "Test Recipe",
    }

    recipes = collect_recipe_nodes(payload)

    assert len(recipes) == 1
    assert recipes[0]["name"] == "Test Recipe"


def test_extract_recipes_from_url_uses_html_fallback_for_partial_recipe_schema():
    html = """
    <html>
      <head>
        <title>Panda Express Honey Walnut Shrimp Copycat | Moribyan</title>
        <script type="application/ld+json">
          {"@context":"https://schema.org","@graph":[{"@type":"Article","headline":"Ignore me"}]}
        </script>
        <script type="application/ld+json">
          {
            "@context":"https://schema.org/",
            "@type":"recipe",
            "name":"Panda Express Honey Walnut Shrimp Copycat",
            "image":"https://example.com/shrimp.jpg"
          }
        </script>
      </head>
      <body>
        <article>
          <div class="recipe-card-details">
            <div class="recipe-ingredient">
              <h4>Ingredients</h4>
              <h5>Honey Sauce</h5>
              <ul>
                <li>1/2 cup mayonnaise</li>
                <li>1/4 cup honey</li>
              </ul>
              <h5>Shrimp</h5>
              <ul>
                <li>1 pound shrimp</li>
              </ul>
            </div>
            <div class="recipe-instruction">
              <h4>Instructions</h4>
              <h5>TO MAKE THE SAUCE</h5>
              <ol>
                <li>Mix the sauce ingredients.</li>
              </ol>
              <h5>TO COOK</h5>
              <ol>
                <li>Fry the shrimp until golden brown.</li>
              </ol>
            </div>
          </div>
        </article>
      </body>
    </html>
    """
    response = _Response(
        html,
        "https://moribyan.com/panda-express-honey-walnut-shrimp-copycat/",
    )

    with (
        patch("app.services.blog.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.blog.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(),
        ),
        patch(
            "app.services.blog.extractor._get_with_403_retry",
            new=AsyncMock(return_value=response),
        ),
    ):
        result = asyncio.run(
            extract_recipes_from_url(
                "https://moribyan.com/panda-express-honey-walnut-shrimp-copycat/"
            )
        )

    assert result.recipe_node_count == 1
    assert len(result.recipes) == 1
    assert result.recipes[0].name == "Panda Express Honey Walnut Shrimp Copycat"
    assert result.recipes[0].ingredients == [
        "1/2 cup mayonnaise",
        "1/4 cup honey",
        "1 pound shrimp",
    ]
    assert result.recipes[0].instructions == [
        "Mix the sauce ingredients.",
        "Fry the shrimp until golden brown.",
    ]


def test_normalize_recipe_prefers_flat_json_ld_ingredients_over_html_fallback():
    recipe = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Korean Cream Cheese Garlic Bread",
        "recipeIngredient": [
            "1 cup bread flour",
            "2 tablespoons garlic",
        ],
        "recipeInstructions": ["Mix the dough.", "Bake until golden."],
    }

    result = normalize_recipe(
        recipe,
        fallback_ingredient_sections=[
            IngredientSection(title="Wrong section", items=["1 cup mayonnaise"])
        ],
    )

    assert result is not None
    assert result.ingredients == ["1 cup bread flour", "2 tablespoons garlic"]
    assert result.ingredientSections is None


def test_normalize_recipe_uses_matching_html_sections_for_flat_json_ld_ingredients():
    recipe = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Layered Bread",
        "recipeIngredient": [
            "1 cup bread flour",
            "1/4 cup sugar",
            "1/4 cup sugar",
            "2 eggs",
        ],
        "recipeInstructions": ["Mix the dough.", "Bake until golden."],
    }

    sections = [
        IngredientSection(
            title="For the bread",
            items=["1 cup bread flour", "1/4 cup sugar"],
        ),
        IngredientSection(
            title="For the filling",
            items=["1/4 cup sugar", "2 eggs"],
        ),
    ]

    result = normalize_recipe(
        recipe,
        fallback_ingredient_sections=sections,
    )

    assert result is not None
    assert result.ingredients == [
        "1 cup bread flour",
        "1/4 cup sugar",
        "1/4 cup sugar",
        "2 eggs",
    ]
    assert result.ingredientSections == sections


def test_extract_recipes_from_url_prefers_json_ld_ingredients_over_html_fallback():
    html = """
    <html>
      <head>
        <title>Korean Cream Cheese Garlic Bread | Two Plaid Aprons</title>
        <script type="application/ld+json" class="yoast-schema-graph">
          {
            "@context":"https://schema.org",
            "@graph":[
              {
                "@type":"Recipe",
                "name":"Korean Cream Cheese Garlic Bread",
                "recipeIngredient":[
                  "1 cup bread flour",
                  "2 tablespoons garlic"
                ],
                "recipeInstructions":[
                  {"@type":"HowToStep","text":"Mix the dough."},
                  {"@type":"HowToStep","text":"Bake until golden."}
                ]
              }
            ]
          }
        </script>
      </head>
      <body>
        <article>
          <h2>Ingredients</h2>
          <ul>
            <li>1 cup mayonnaise</li>
            <li>1/4 cup honey</li>
          </ul>
          <h2>Instructions</h2>
          <ol>
            <li>Whisk the sauce.</li>
          </ol>
        </article>
      </body>
    </html>
    """
    response = _Response(
        html,
        "https://twoplaidaprons.com/korean-cream-cheese-garlic-bread/",
    )

    with (
        patch("app.services.blog.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.blog.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(),
        ),
        patch(
            "app.services.blog.extractor._get_with_403_retry",
            new=AsyncMock(return_value=response),
        ),
    ):
        result = asyncio.run(
            extract_recipes_from_url(
                "https://twoplaidaprons.com/korean-cream-cheese-garlic-bread/"
            )
        )

    assert result.recipe_node_count == 1
    assert len(result.recipes) == 1
    assert result.recipes[0].name == "Korean Cream Cheese Garlic Bread"
    assert result.recipes[0].ingredients == [
        "1 cup bread flour",
        "2 tablespoons garlic",
    ]
    assert result.recipes[0].ingredientSections is None
    assert result.recipes[0].instructions == [
        "Mix the dough.",
        "Bake until golden.",
    ]


def test_extract_recipes_from_url_uses_matching_wprm_headers_for_flat_json_ld_ingredients():
    html = """
    <html>
      <head>
        <title>Layered Bread</title>
        <script type="application/ld+json" class="yoast-schema-graph">
          {
            "@context":"https://schema.org",
            "@graph":[
              {
                "@type":"Recipe",
                "name":"Layered Bread",
                "recipeIngredient":[
                  "1 cup bread flour",
                  "1/4 cup sugar",
                  "1/4 cup sugar",
                  "2 eggs"
                ],
                "recipeInstructions":[
                  {"@type":"HowToStep","text":"Mix the dough."},
                  {"@type":"HowToStep","text":"Bake until golden."}
                ]
              }
            ]
          }
        </script>
      </head>
      <body>
        <div class="wprm-recipe-ingredients-container">
          <h3 class="wprm-recipe-ingredients-header">Ingredients</h3>
          <div class="wprm-recipe-ingredient-group">
            <h4 class="wprm-recipe-ingredient-group-name">For the bread:</h4>
            <ul class="wprm-recipe-ingredients">
              <li class="wprm-recipe-ingredient">1 cup bread flour</li>
              <li class="wprm-recipe-ingredient">1/4 cup sugar</li>
            </ul>
          </div>
          <div class="wprm-recipe-ingredient-group">
            <h4 class="wprm-recipe-ingredient-group-name">For the filling:</h4>
            <ul class="wprm-recipe-ingredients">
              <li class="wprm-recipe-ingredient">1/4 cup sugar</li>
              <li class="wprm-recipe-ingredient">2 eggs</li>
            </ul>
          </div>
        </div>
      </body>
    </html>
    """
    response = _Response(html, "https://example.com/layered-bread")

    with (
        patch("app.services.blog.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.blog.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(),
        ),
        patch(
            "app.services.blog.extractor._get_with_403_retry",
            new=AsyncMock(return_value=response),
        ),
    ):
        result = asyncio.run(
            extract_recipes_from_url("https://example.com/layered-bread")
        )

    assert result.recipe_node_count == 1
    assert len(result.recipes) == 1
    assert result.recipes[0].ingredients == [
        "1 cup bread flour",
        "1/4 cup sugar",
        "1/4 cup sugar",
        "2 eggs",
    ]
    assert result.recipes[0].ingredientSections == [
        IngredientSection(
            title="For the bread:",
            items=["1 cup bread flour", "1/4 cup sugar"],
        ),
        IngredientSection(
            title="For the filling:",
            items=["1/4 cup sugar", "2 eggs"],
        ),
    ]


def test_extract_recipes_from_url_returns_gemini_recipe_when_accepted():
    html = """
    <html>
      <head>
        <title>Legacy Title</title>
        <script type="application/ld+json">
          {
            "@context":"https://schema.org",
            "@type":"Recipe",
            "name":"Legacy Recipe",
            "recipeIngredient":["1 cup legacy flour"],
            "recipeInstructions":["Bake the legacy recipe."]
          }
        </script>
      </head>
      <body></body>
    </html>
    """
    response = _Response(html, "https://example.com/recipe")
    gemini_result = GeminiNormalizationResult(
        accepted=True,
        recipes=[_gemini_recipe()],
        warnings=["gemini warning"],
        normalization_model="gemini-test",
    )

    with (
        patch("app.services.blog.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.blog.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(),
        ),
        patch(
            "app.services.blog.extractor._get_with_403_retry",
            new=AsyncMock(return_value=response),
        ),
        patch(
            "app.services.blog.extractor.normalize_with_gemini",
            new=AsyncMock(return_value=gemini_result),
        ) as gemini,
    ):
        result = asyncio.run(
            extract_recipes_from_url(
                "https://example.com/recipe",
                gemini_rate_key="admin@example.com",
            )
        )

    gemini.assert_awaited_once()
    assert result.extraction_method == "gemini"
    assert result.normalization_model == "gemini-test"
    assert result.warnings == ["gemini warning"]
    assert result.recipes == [_gemini_recipe()]
    assert result.recipes[0].name != "Legacy Recipe"


def test_extract_recipes_from_url_gemini_low_confidence_falls_back_to_html_sections(
    caplog: pytest.LogCaptureFixture,
):
    html = """
    <html>
      <head>
        <title>Fallback Title</title>
        <script type="application/ld+json">
          {"@context":"https://schema.org","@type":"Recipe","name":"Fallback Recipe"}
        </script>
      </head>
      <body>
        <article>
          <h2>Ingredients</h2>
          <ul>
            <li>1 cup fallback flour</li>
          </ul>
          <h2>Instructions</h2>
          <ol>
            <li>Mix the fallback batter.</li>
          </ol>
        </article>
      </body>
    </html>
    """
    response = _Response(html, "https://example.com/fallback")
    gemini_result = GeminiNormalizationResult(
        accepted=False,
        fallback_reason="low_confidence",
        warnings=["low confidence"],
        normalization_model="gemini-test",
    )

    with caplog.at_level(logging.WARNING, logger="app.services.blog.extractor"):
        with (
            patch("app.services.blog.extractor.get_settings", return_value=_settings()),
            patch(
                "app.services.blog.extractor.httpx.AsyncClient",
                return_value=_AsyncClientContext(),
            ),
            patch(
                "app.services.blog.extractor._get_with_403_retry",
                new=AsyncMock(return_value=response),
            ) as fetch,
            patch(
                "app.services.blog.extractor.normalize_with_gemini",
                new=AsyncMock(return_value=gemini_result),
            ),
        ):
            result = asyncio.run(
                extract_recipes_from_url(
                    "https://example.com/fallback",
                    gemini_rate_key="admin@example.com",
                )
            )

    fetch.assert_awaited_once()
    assert result.extraction_method == "manual_fallback"
    assert result.fallback_reason == "low_confidence"
    assert result.normalization_model == "gemini-test"
    assert result.warnings == ["low confidence"]
    assert result.recipe_node_count == 1
    assert result.recipes[0].ingredients == ["1 cup fallback flour"]
    assert result.recipes[0].instructions == ["Mix the fallback batter."]
    assert "Recipe extraction fell back to legacy parser" in caplog.text
    assert "fallback_reason=low_confidence" in caplog.text
    assert "https://example.com/fallback" in caplog.text


def test_extract_recipes_from_url_without_gemini_rate_key_keeps_legacy_flow():
    html = """
    <html>
      <head>
        <title>Legacy Only</title>
        <script type="application/ld+json">
          {
            "@context":"https://schema.org",
            "@type":"Recipe",
            "name":"Legacy Only Recipe",
            "recipeIngredient":["1 cup rice"],
            "recipeInstructions":["Cook rice."]
          }
        </script>
      </head>
      <body></body>
    </html>
    """
    response = _Response(html, "https://example.com/legacy")

    with (
        patch("app.services.blog.extractor.get_settings", return_value=_settings()),
        patch(
            "app.services.blog.extractor.httpx.AsyncClient",
            return_value=_AsyncClientContext(),
        ),
        patch(
            "app.services.blog.extractor._get_with_403_retry",
            new=AsyncMock(return_value=response),
        ),
        patch(
            "app.services.blog.extractor.normalize_with_gemini",
            new=AsyncMock(),
        ) as gemini,
    ):
        result = asyncio.run(extract_recipes_from_url("https://example.com/legacy"))

    gemini.assert_not_called()
    assert result.extraction_method is None
    assert result.fallback_reason is None
    assert result.recipes[0].name == "Legacy Only Recipe"


def test_extract_recipes_from_url_rejects_redirect_to_private_url():
    class RedirectingClient:
        def __init__(self, **kwargs):
            self.follow_redirects = kwargs.get("follow_redirects", False)
            self.requested_urls: list[str] = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def build_request(self, method: str, url: str, **kwargs):
            return httpx.Request(method, str(url), **kwargs)

        async def send(self, request: httpx.Request, **kwargs):
            url = str(request.url)
            self.requested_urls.append(url)
            if url == "https://example.com/recipe":
                return httpx.Response(
                    status_code=302,
                    headers={"Location": "http://127.0.0.1/private"},
                    request=request,
                )

            return httpx.Response(
                status_code=200,
                text="<html></html>",
                request=request,
            )

    client = RedirectingClient()

    def client_factory(**kwargs):
        nonlocal client
        client = RedirectingClient(**kwargs)
        return client

    with (
        patch("app.services.blog.extractor.get_settings", return_value=_settings()),
        patch(
            "app.utils.url_safety.socket.getaddrinfo",
            return_value=[(None, None, None, "", ("93.184.216.34", 443))],
        ),
        patch(
            "app.services.blog.extractor.httpx.AsyncClient",
            side_effect=client_factory,
        ),
    ):
        with pytest.raises(HTTPException) as error:
            asyncio.run(extract_recipes_from_url("https://example.com/recipe"))

    assert error.value.status_code == 400
    assert error.value.detail == "Private or localhost URLs are not supported"
    assert client.requested_urls == ["https://example.com/recipe"]


def test_extract_recipes_from_url_rejects_non_http_url_with_public_url_detail():
    with pytest.raises(HTTPException) as error:
        asyncio.run(extract_recipes_from_url("file://x"))

    assert error.value.status_code == 400
    assert error.value.detail == "Enter a public http(s) URL"


def test_extract_recipes_from_url_rejects_dns_rebinding_to_private_peer():
    class _PrivatePeerStream:
        def get_extra_info(self, name):
            if name == "server_addr":
                return ("127.0.0.1", 443)
            return None

    class PrivatePeerClient:
        def __init__(self, **kwargs):
            self.closed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def build_request(self, method, url, **kwargs):
            return httpx.Request(method, str(url), **kwargs)

        async def send(self, request, **kwargs):
            response = httpx.Response(
                status_code=200,
                text="<html></html>",
                request=request,
            )
            response.extensions["network_stream"] = _PrivatePeerStream()
            return response

    with (
        patch("app.services.blog.extractor.get_settings", return_value=_settings()),
        patch(
            "app.utils.url_safety.socket.getaddrinfo",
            return_value=[(None, None, None, "", ("93.184.216.34", 443))],
        ),
        patch(
            "app.services.blog.extractor.httpx.AsyncClient",
            side_effect=lambda **kwargs: PrivatePeerClient(**kwargs),
        ),
    ):
        with pytest.raises(HTTPException) as error:
            asyncio.run(extract_recipes_from_url("https://example.com/recipe"))

    assert error.value.status_code == 400
    assert error.value.detail == "Private or localhost URLs are not supported"
