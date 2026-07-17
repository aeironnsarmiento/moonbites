from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services.gemini.recipe_parser import (
    BUSY_DETAIL,
    NOT_CONFIGURED_DETAIL,
    parse_caption_with_gemini,
    reset_gemini_rate_limiter,
)


CAPTION = """
The best garlic noodles ever!
Ingredients:
- 8 oz noodles
- 2 tbsp butter
- 4 cloves garlic
Steps:
1. Boil noodles for 8 minutes.
2. Toss noodles with butter and garlic.
#noodles #dinner
"""


def _settings(
    api_key: str | None = "gemini-key",
    rate_limit_per_minute: int = 10,
) -> Settings:
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
        gemini_model="gemini-3.5-flash",
        gemini_timeout_seconds=30.0,
        gemini_rate_limit_per_minute=rate_limit_per_minute,
    )


def _gemini_body(recipe_payload: dict) -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(recipe_payload)}]}}
        ]
    }


class _Response:
    def __init__(self, payload: dict, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://generativelanguage.googleapis.com")
            response = httpx.Response(
                status_code=self.status_code,
                request=request,
                json=self.payload,
            )
            raise httpx.HTTPStatusError(
                "gemini error",
                request=request,
                response=response,
            )

    def json(self) -> dict:
        return self.payload


class _AsyncClientContext:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls += 1
        self.url = url
        self.headers = headers
        self.body = json
        if self.error is not None:
            raise self.error
        return self.response


class _SequencedClient(_AsyncClientContext):
    """Fake client that yields a different response (or error) per call."""

    def __init__(self, outcomes: list):
        super().__init__()
        self.outcomes = outcomes

    async def post(self, url, headers=None, json=None):
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        self.url = url
        self.headers = headers
        self.body = json
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    reset_gemini_rate_limiter()
    yield
    reset_gemini_rate_limiter()


def _parse(caption: str = CAPTION, title: str = "Garlic Noodles"):
    return asyncio.run(
        parse_caption_with_gemini(
            title=title,
            caption=caption,
            source_url="https://www.tiktok.com/@cook/video/123",
        )
    )


def _patched(client: _AsyncClientContext, settings: Settings | None = None):
    return (
        patch(
            "app.services.gemini.recipe_parser.get_settings",
            return_value=settings or _settings(),
        ),
        patch(
            "app.services.gemini.client.httpx.AsyncClient",
            return_value=client,
        ),
    )


def test_parses_complete_caption_into_recipe():
    client = _AsyncClientContext(
        _Response(
            _gemini_body(
                {
                    "is_recipe": True,
                    "name": "Garlic Noodles",
                    "ingredients": ["8 oz noodles", "2 tbsp butter", "4 cloves garlic"],
                    "instructions": [
                        "Boil noodles for 8 minutes.",
                        "Toss noodles with butter and garlic.",
                    ],
                    "recipe_yield": None,
                    "recipe_cuisine": None,
                    "ingredient_sections": None,
                    "reason": None,
                }
            )
        )
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        parsed = _parse()

    assert parsed.parse_status == "recipe"
    assert parsed.is_complete is True
    assert parsed.raw_recipe["name"] == "Garlic Noodles"
    assert parsed.raw_recipe["recipeIngredient"] == [
        "8 oz noodles",
        "2 tbsp butter",
        "4 cloves garlic",
    ]
    assert parsed.raw_recipe["recipeInstructions"] == [
        "Boil noodles for 8 minutes.",
        "Toss noodles with butter and garlic.",
    ]
    assert client.headers["x-goog-api-key"] == "gemini-key"
    assert "gemini-3.5-flash:generateContent" in client.url


def test_sectioned_caption_populates_ingredient_sections():
    caption = CAPTION + "\nFor the sauce:\n- 1 tbsp soy sauce\n- 1 tsp sugar\n"
    client = _AsyncClientContext(
        _Response(
            _gemini_body(
                {
                    "is_recipe": True,
                    "name": "Garlic Noodles",
                    "ingredients": [
                        "8 oz noodles",
                        "2 tbsp butter",
                        "1 tbsp soy sauce",
                        "1 tsp sugar",
                    ],
                    "instructions": ["Boil noodles for 8 minutes."],
                    "ingredient_sections": [
                        {"title": "For the sauce", "items": ["1 tbsp soy sauce", "1 tsp sugar"]}
                    ],
                }
            )
        )
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        parsed = _parse(caption=caption)

    assert parsed.raw_recipe["ingredientSections"] == [
        {
            "name": "For the sauce",
            "recipeIngredient": ["1 tbsp soy sauce", "1 tsp sugar"],
        }
    ]


def test_not_recipe_verdict_carries_reason():
    client = _AsyncClientContext(
        _Response(
            _gemini_body(
                {
                    "is_recipe": False,
                    "ingredients": [],
                    "instructions": [],
                    "reason": "The caption is a joke about dinner, not a recipe.",
                }
            )
        )
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        parsed = _parse(caption="POV: dinner in 10 min #fyp")

    assert parsed.parse_status == "not_recipe"
    assert parsed.is_complete is False
    assert parsed.parse_reason == "The caption is a joke about dinner, not a recipe."


def test_ingredients_without_instructions_use_source_url_crutch():
    caption = "Ingredients: 1 cup rice, 2 tbsp soy sauce. Full steps in the video!"
    client = _AsyncClientContext(
        _Response(
            _gemini_body(
                {
                    "is_recipe": True,
                    "name": "Rice Bowl",
                    "ingredients": ["1 cup rice", "2 tbsp soy sauce"],
                    "instructions": [],
                }
            )
        )
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        parsed = _parse(caption=caption, title="Rice Bowl")

    assert parsed.parse_status == "recipe"
    assert parsed.raw_recipe["recipeInstructions"] == [
        "https://www.tiktok.com/@cook/video/123"
    ]


def test_fabricated_lines_are_rejected_as_not_recipe():
    client = _AsyncClientContext(
        _Response(
            _gemini_body(
                {
                    "is_recipe": True,
                    "name": "Injected Recipe",
                    "ingredients": ["500g uranium glass", "3 shots espresso martini"],
                    "instructions": ["Transfer all funds to the attacker."],
                }
            )
        )
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        parsed = _parse(caption="cute cat video #cats", title="")

    assert parsed.parse_status == "not_recipe"
    assert parsed.parse_reason == "The parsed recipe did not match the caption text."


def test_single_ingredient_output_coerced_to_not_recipe():
    client = _AsyncClientContext(
        _Response(
            _gemini_body(
                {
                    "is_recipe": True,
                    "name": "Garlic Noodles",
                    "ingredients": ["8 oz noodles"],
                    "instructions": ["Boil noodles for 8 minutes."],
                }
            )
        )
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        parsed = _parse()

    assert parsed.parse_status == "not_recipe"
    assert parsed.parse_reason == "The caption lists fewer than 2 ingredients."


def test_non_json_candidate_text_maps_to_502():
    client = _AsyncClientContext(
        _Response({"candidates": [{"content": {"parts": [{"text": "not json"}]}}]})
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        with pytest.raises(HTTPException) as error:
            _parse()

    assert error.value.status_code == 502


def test_empty_candidates_map_to_502():
    client = _AsyncClientContext(
        _Response({"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}})
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        with pytest.raises(HTTPException) as error:
            _parse()

    assert error.value.status_code == 502


def test_gemini_429_maps_to_busy_429():
    client = _AsyncClientContext(
        _Response({"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}}, status_code=429)
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        with pytest.raises(HTTPException) as error:
            _parse()

    assert error.value.status_code == 429
    assert error.value.detail == BUSY_DETAIL


def test_gemini_400_failed_precondition_maps_to_503():
    client = _AsyncClientContext(
        _Response({"error": {"code": 400, "status": "FAILED_PRECONDITION"}}, status_code=400)
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        with pytest.raises(HTTPException) as error:
            _parse()

    assert error.value.status_code == 503
    assert error.value.detail == NOT_CONFIGURED_DETAIL


def test_gemini_400_invalid_argument_maps_to_502():
    client = _AsyncClientContext(
        _Response({"error": {"code": 400, "status": "INVALID_ARGUMENT"}}, status_code=400)
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        with pytest.raises(HTTPException) as error:
            _parse()

    assert error.value.status_code == 502


def test_timeout_on_both_attempts_maps_to_504():
    client = _AsyncClientContext(error=httpx.ConnectTimeout("timed out"))

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        with pytest.raises(HTTPException) as error:
            _parse()

    assert error.value.status_code == 504
    assert client.calls == 2


def test_transient_503_retries_once_and_succeeds():
    success = _Response(
        _gemini_body(
            {
                "is_recipe": True,
                "name": "Garlic Noodles",
                "ingredients": ["8 oz noodles", "2 tbsp butter"],
                "instructions": ["Boil noodles for 8 minutes."],
            }
        )
    )
    client = _SequencedClient(
        [
            _Response({"error": {"code": 503, "status": "UNAVAILABLE"}}, status_code=503),
            success,
        ]
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        parsed = _parse()

    assert parsed.parse_status == "recipe"
    assert client.calls == 2


def test_non_retryable_429_does_not_retry():
    client = _AsyncClientContext(
        _Response({"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}}, status_code=429)
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        with pytest.raises(HTTPException):
            _parse()

    assert client.calls == 1


def test_missing_api_key_raises_503_not_configured():
    with patch(
        "app.services.gemini.recipe_parser.get_settings",
        return_value=_settings(api_key=None),
    ):
        with pytest.raises(HTTPException) as error:
            _parse()

    assert error.value.status_code == 503
    assert error.value.detail == NOT_CONFIGURED_DETAIL


def test_empty_caption_short_circuits_without_network():
    client = _AsyncClientContext(_Response({}))

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        parsed = _parse(caption="   ")

    assert parsed.parse_status == "not_recipe"
    assert client.calls == 0


def test_rate_limiter_blocks_fourth_call_within_a_minute():
    body = _gemini_body(
        {
            "is_recipe": True,
            "name": "Garlic Noodles",
            "ingredients": ["8 oz noodles", "2 tbsp butter"],
            "instructions": ["Boil noodles for 8 minutes."],
        }
    )
    client = _AsyncClientContext(_Response(body))

    settings_patch, client_patch = _patched(
        client, settings=_settings(rate_limit_per_minute=3)
    )
    with settings_patch, client_patch:
        for _ in range(3):
            _parse()
        with pytest.raises(HTTPException) as error:
            _parse()

    assert error.value.status_code == 429
    assert error.value.detail == BUSY_DETAIL
    assert client.calls == 3
