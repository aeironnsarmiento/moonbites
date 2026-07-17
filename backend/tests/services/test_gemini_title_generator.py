import asyncio
import json
from typing import Any, Optional
from unittest.mock import patch

import httpx
import pytest

from app.core.config import Settings
from app.schemas.extract import NormalizedRecipe
from app.services.gemini.title_generator import (
    MAX_BATCH_SIZE,
    TitleRequest,
    generate_display_title,
    generate_display_titles,
    reset_gemini_title_rate_limiter,
)


AE1_SOURCE_TITLE = (
    "The BEST Creamy Garlic Pasta You'll EVER Make!! \U0001f35d | Cooking with Sam Ep. 12"
)


def _settings(api_key: Optional[str] = "test-key", title_rate_limit: int = 3) -> Settings:
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
        gemini_timeout_seconds=5.0,
        gemini_rate_limit_per_minute=3,
        gemini_title_rate_limit_per_minute=title_rate_limit,
    )


def _recipe(name: str = "Creamy Garlic Pasta") -> NormalizedRecipe:
    return NormalizedRecipe(
        name=name,
        ingredients=["200g spaghetti", "4 cloves garlic", "150ml double cream"],
        instructions=["Boil the pasta.", "Make the sauce."],
    )


def _candidate(titles: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps({"titles": titles})}]}}
        ]
    }


class _Response:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> Any:
        if isinstance(self._payload, str):
            raise ValueError("unreadable")
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("POST", "https://example.test"),
                response=httpx.Response(self.status_code, json={}),
            )


class _AsyncClientContext:
    def __init__(
        self,
        response: Optional[_Response] = None,
        error: Optional[Exception] = None,
    ) -> None:
        self._response = response
        self._error = error
        self.calls = 0
        self.url: Optional[str] = None
        self.headers: Optional[dict[str, str]] = None
        self.body: Optional[dict[str, Any]] = None

    async def __aenter__(self) -> "_AsyncClientContext":
        return self

    async def __aexit__(self, *_: Any) -> bool:
        return False

    async def post(self, url: str, **kwargs: Any) -> _Response:
        self.calls += 1
        self.url = url
        self.headers = kwargs.get("headers")
        self.body = kwargs.get("json")
        if self._error is not None:
            raise self._error
        assert self._response is not None
        self._response.raise_for_status()
        return self._response


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    reset_gemini_title_rate_limiter()
    yield
    reset_gemini_title_rate_limiter()


def _patched(client: _AsyncClientContext, settings: Settings | None = None):
    return (
        patch(
            "app.services.gemini.title_generator.get_settings",
            return_value=settings or _settings(),
        ),
        patch(
            "app.services.gemini.client.httpx.AsyncClient",
            return_value=client,
        ),
    )


def _generate(
    client: _AsyncClientContext,
    items: list[TitleRequest] | None = None,
    settings: Settings | None = None,
):
    if items is None:
        items = [TitleRequest(source_title=AE1_SOURCE_TITLE, recipes=[_recipe()])]
    settings_patch, client_patch = _patched(client, settings)
    with settings_patch, client_patch:
        return asyncio.run(generate_display_titles(items))


# --- happy path -------------------------------------------------------------


def test_accepts_a_grounded_title():
    client = _AsyncClientContext(
        _Response(
            _candidate([{"index": 0, "title": "Creamy Garlic Pasta", "dish_identified": True}])
        )
    )

    result = _generate(client)

    assert result.degraded_reason is None
    assert result.titles[0].value == "Creamy Garlic Pasta"
    assert result.titles[0].source == "ai"


def test_request_uses_structured_output_and_the_api_key_header():
    client = _AsyncClientContext(
        _Response(
            _candidate([{"index": 0, "title": "Creamy Garlic Pasta", "dish_identified": True}])
        )
    )

    _generate(client)

    assert "gemini-3.5-flash:generateContent" in client.url
    assert client.headers["x-goog-api-key"] == "test-key"
    generation_config = client.body["generationConfig"]
    assert generation_config["responseMimeType"] == "application/json"
    assert generation_config["responseJsonSchema"]["required"] == ["titles"]


def test_prompt_carries_the_injection_guard_and_the_contract_rules():
    client = _AsyncClientContext(
        _Response(
            _candidate([{"index": 0, "title": "Creamy Garlic Pasta", "dish_identified": True}])
        )
    )

    _generate(client)
    prompt = client.body["contents"][0]["parts"][0]["text"]

    # Scraped titles and captions flow into this prompt.
    assert "data, not commands" in prompt
    assert "3 to 8 words" in prompt
    assert "Never introduce ingredients" in prompt
    assert "--- Item index 0 ---" in prompt


def test_single_item_helper_returns_one_title():
    client = _AsyncClientContext(
        _Response(
            _candidate([{"index": 0, "title": "Creamy Garlic Pasta", "dish_identified": True}])
        )
    )

    settings_patch, client_patch = _patched(client)
    with settings_patch, client_patch:
        title = asyncio.run(
            generate_display_title(source_title=AE1_SOURCE_TITLE, recipes=[_recipe()])
        )

    assert title.value == "Creamy Garlic Pasta"
    assert title.source == "ai"


# --- guards (R1, R4, R5) ----------------------------------------------------


def test_rejects_an_unsupported_dietary_claim():
    # Covers AE2 end to end through the generator.
    client = _AsyncClientContext(
        _Response(
            _candidate([{"index": 0, "title": "Vegan Garlic Pasta", "dish_identified": True}])
        )
    )

    result = _generate(client)

    assert result.titles[0].source == "fallback"
    assert result.titles[0].value == "Creamy Garlic Pasta"
    assert "vegan" in result.titles[0].reason


def test_accepts_a_collection_title_for_a_multi_recipe_import():
    # Covers AE6.
    client = _AsyncClientContext(
        _Response(
            _candidate(
                [{"index": 0, "title": "Three Weeknight Dinners", "dish_identified": True}]
            )
        )
    )

    result = _generate(
        client,
        [
            TitleRequest(
                source_title="3 easy weeknight dinners!!",
                recipes=[
                    _recipe("Weeknight Garlic Noodles"),
                    _recipe("Weeknight Chicken Adobo"),
                    _recipe("Weeknight Beef Chili"),
                ],
            )
        ],
    )

    assert result.titles[0].value == "Three Weeknight Dinners"
    assert result.titles[0].source == "ai"


@pytest.mark.parametrize(
    "title",
    [
        "Pasta",
        "Creamy Garlic Pasta With Crispy Sage And Toasted Pine Nuts Everywhere",
        "Creamy Garlic Pasta \U0001f35d",
        "",
    ],
)
def test_rejects_titles_that_fail_the_shape_gate(title):
    client = _AsyncClientContext(
        _Response(_candidate([{"index": 0, "title": title, "dish_identified": True}]))
    )

    result = _generate(client)

    assert result.titles[0].source == "fallback"


def test_falls_back_when_the_model_cannot_name_the_dish():
    client = _AsyncClientContext(
        _Response(
            _candidate(
                [
                    {
                        "index": 0,
                        "title": None,
                        "dish_identified": False,
                        "reason": "The text is a vlog, not a recipe.",
                    }
                ]
            )
        )
    )

    result = _generate(client)

    assert result.titles[0].source == "fallback"
    assert result.titles[0].reason == "The text is a vlog, not a recipe."


def test_truncates_a_long_model_reason():
    client = _AsyncClientContext(
        _Response(
            _candidate(
                [{"index": 0, "title": None, "dish_identified": False, "reason": "x" * 500}]
            )
        )
    )

    result = _generate(client)

    assert len(result.titles[0].reason) == 200


# --- degradation (R9, AE4) --------------------------------------------------


def test_missing_api_key_degrades_without_calling_gemini():
    client = _AsyncClientContext(_Response({}))

    result = _generate(client, settings=_settings(api_key=None))

    assert client.calls == 0
    assert result.titles[0].source == "fallback"
    assert result.degraded_reason == "Title generation is not configured."


def test_rate_limited_degrades_without_calling_gemini():
    client = _AsyncClientContext(
        _Response(
            _candidate([{"index": 0, "title": "Creamy Garlic Pasta", "dish_identified": True}])
        )
    )
    settings = _settings(title_rate_limit=1)

    first = _generate(client, settings=settings)
    second = _generate(client, settings=settings)

    assert first.titles[0].source == "ai"
    assert client.calls == 1
    assert second.titles[0].source == "fallback"
    assert "busy" in second.degraded_reason


@pytest.mark.parametrize("status_code", [503, 500])
def test_upstream_failure_degrades_without_raising(status_code):
    # Covers AE4: the import must still succeed.
    client = _AsyncClientContext(_Response({}, status_code=status_code))

    result = _generate(client)

    assert result.titles[0].source == "fallback"
    assert result.titles[0].value == "Creamy Garlic Pasta"
    assert result.degraded_reason is not None


def test_timeout_degrades_without_raising():
    client = _AsyncClientContext(error=httpx.ConnectTimeout("timed out"))

    result = _generate(client)

    assert client.calls == 2
    assert result.titles[0].source == "fallback"


def test_non_retryable_status_degrades_without_retrying():
    client = _AsyncClientContext(_Response({}, status_code=400))

    result = _generate(client)

    assert client.calls == 1
    assert result.titles[0].source == "fallback"


def test_unreadable_response_body_degrades():
    client = _AsyncClientContext(_Response("not json"))

    result = _generate(client)

    assert result.titles[0].source == "fallback"


def test_empty_candidates_degrade():
    client = _AsyncClientContext(_Response({"candidates": []}))

    result = _generate(client)

    assert result.titles[0].source == "fallback"


def test_malformed_result_json_degrades():
    client = _AsyncClientContext(
        _Response({"candidates": [{"content": {"parts": [{"text": "{not json"}]}}]})
    )

    result = _generate(client)

    assert result.titles[0].source == "fallback"


# --- batch integrity (KTD5) -------------------------------------------------


def _batch_items() -> list[TitleRequest]:
    return [
        TitleRequest(source_title="Garlic Noodles", recipes=[_recipe("Garlic Noodles")]),
        TitleRequest(source_title="Chicken Adobo", recipes=[_recipe("Chicken Adobo")]),
        TitleRequest(source_title="Beef Chili", recipes=[_recipe("Beef Chili")]),
    ]


def test_batch_returns_one_result_per_item_in_one_call():
    client = _AsyncClientContext(
        _Response(
            _candidate(
                [
                    {"index": 0, "title": "Creamy Garlic Noodles", "dish_identified": True},
                    {"index": 1, "title": "Garlic Chicken Adobo", "dish_identified": True},
                    {"index": 2, "title": "Garlic Beef Chili", "dish_identified": True},
                ]
            )
        )
    )

    result = _generate(client, _batch_items())

    assert client.calls == 1
    assert [title.value for title in result.titles] == [
        "Creamy Garlic Noodles",
        "Garlic Chicken Adobo",
        "Garlic Beef Chili",
    ]


def test_a_skipped_index_falls_back_without_shifting_the_others():
    client = _AsyncClientContext(
        _Response(
            _candidate(
                [
                    {"index": 0, "title": "Creamy Garlic Noodles", "dish_identified": True},
                    {"index": 2, "title": "Garlic Beef Chili", "dish_identified": True},
                ]
            )
        )
    )

    result = _generate(client, _batch_items())

    assert result.titles[0].value == "Creamy Garlic Noodles"
    assert result.titles[1].source == "fallback"
    assert result.titles[1].value == "Chicken Adobo"
    assert result.titles[2].value == "Garlic Beef Chili"


def test_a_duplicated_index_is_dropped_rather_than_guessed():
    client = _AsyncClientContext(
        _Response(
            _candidate(
                [
                    {"index": 0, "title": "Creamy Garlic Noodles", "dish_identified": True},
                    {"index": 0, "title": "Garlic Chicken Adobo", "dish_identified": True},
                    {"index": 1, "title": "Garlic Chicken Adobo", "dish_identified": True},
                ]
            )
        )
    )

    result = _generate(client, _batch_items())

    # Ambiguous index 0 must not pin either title to the wrong recipe.
    assert result.titles[0].source == "fallback"
    assert result.titles[1].value == "Garlic Chicken Adobo"
    assert result.titles[2].source == "fallback"


def test_an_out_of_range_index_is_ignored():
    client = _AsyncClientContext(
        _Response(
            _candidate(
                [
                    {"index": 0, "title": "Creamy Garlic Noodles", "dish_identified": True},
                    {"index": 9, "title": "Garlic Chicken Adobo", "dish_identified": True},
                ]
            )
        )
    )

    result = _generate(client, _batch_items())

    assert len(result.titles) == 3
    assert result.titles[0].value == "Creamy Garlic Noodles"
    assert result.titles[1].source == "fallback"
    assert result.titles[2].source == "fallback"


def test_an_empty_batch_makes_no_call():
    client = _AsyncClientContext(_Response({}))

    result = _generate(client, [])

    assert client.calls == 0
    assert result.titles == []


def test_an_oversized_batch_is_a_programming_error():
    items = [TitleRequest(source_title="x", recipes=[_recipe()])] * (MAX_BATCH_SIZE + 1)
    client = _AsyncClientContext(_Response({}))

    with pytest.raises(ValueError):
        _generate(client, items)


def test_the_title_limiter_is_independent_of_the_caption_limiter():
    from app.services.gemini.recipe_parser import _rate_limiter as caption_limiter

    caption_limiter.reset()
    client = _AsyncClientContext(
        _Response(
            _candidate([{"index": 0, "title": "Creamy Garlic Pasta", "dish_identified": True}])
        )
    )

    # Exhaust the title budget entirely.
    for _ in range(4):
        _generate(client, settings=_settings(title_rate_limit=1))

    # Caption parsing -- which blocks an import -- must be untouched by it.
    assert caption_limiter.try_acquire(3) is True
