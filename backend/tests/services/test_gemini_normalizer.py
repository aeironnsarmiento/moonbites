from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.extract import NormalizedRecipe
from app.services.gemini.guardrails import GeminiGuardrails
import app.services.gemini.normalizer as gemini_normalizer
from app.services.gemini.prompt import (
    MAX_SERIALIZED_PAYLOAD_CHARS,
    build_gemini_prompt,
)
from app.services.gemini.normalizer import normalize_with_gemini
from app.services.gemini.types import GeminiRecipeResult, RawExtractionPayload


def _settings(
    *,
    enabled: bool = True,
    api_key: str | None = "test-key",
    timeout: float = 10.0,
    rate_limit: int = 3,
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
        gemini_normalization_enabled=enabled,
        gemini_model="gemini-test",
        gemini_timeout_seconds=timeout,
        gemini_rate_limit_per_minute=rate_limit,
    )


def _recipe() -> NormalizedRecipe:
    return NormalizedRecipe(
        name="Garlic Noodles",
        recipeYield="2 servings",
        cookTime=None,
        recipeCuisine=None,
        nutrition=None,
        ingredients=["8 oz noodles", "2 tbsp butter"],
        ingredientSections=None,
        instructions=["Boil noodles.", "Toss with butter."],
    )


def _payload(**overrides: object) -> RawExtractionPayload:
    data = {
        "source_type": "json_ld",
        "source_url": "https://example.com/recipe",
        "json_ld_blocks": [{"@type": "Recipe", "name": "Garlic Noodles"}],
    }
    data.update(overrides)
    return RawExtractionPayload(**data)


def _gemini_json(
    *,
    recipes: list[NormalizedRecipe] | None = None,
    confidence: float = 0.9,
    warnings: list[str] | None = None,
) -> str:
    return GeminiRecipeResult(
        recipes=recipes if recipes is not None else [_recipe()],
        confidence=confidence,
        warnings=warnings or [],
    ).model_dump_json()


class _FakeModels:
    calls: list[dict[str, object]] = []

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        self.__class__.calls.append(kwargs)
        outcome = _FakeClient.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _FakeClient:
    instances: list["_FakeClient"] = []
    outcomes: list[object] = []

    def __init__(self, *, api_key: str, http_options: object | None = None) -> None:
        self.api_key = api_key
        self.http_options = http_options
        self.closed = False
        self.models = _FakeModels()
        self.instances.append(self)

    def close(self) -> None:
        self.closed = True


def _patch_client(monkeypatch: pytest.MonkeyPatch, outcomes: list[object]) -> None:
    _FakeClient.instances = []
    _FakeClient.outcomes = outcomes
    _FakeModels.calls = []
    monkeypatch.setattr(gemini_normalizer.genai, "Client", _FakeClient)
    monkeypatch.setattr(
        gemini_normalizer.genai_types,
        "HttpOptions",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        gemini_normalizer,
        "gemini_guardrails",
        GeminiGuardrails(),
    )


def _response(text: str | None) -> SimpleNamespace:
    return SimpleNamespace(text=text)


def _run(payload: RawExtractionPayload, **kwargs: object):
    return asyncio.run(normalize_with_gemini(payload, **kwargs))


def test_overlong_youtube_description_is_truncated_and_warning_added():
    payload = RawExtractionPayload(
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=abc123",
        description="a" * 20_100,
    )

    prompt = build_gemini_prompt(payload)

    assert len(prompt.payload["description"]) == 20_000
    assert any(
        "description" in warning and "truncated" in warning
        for warning in prompt.warnings
    )


def test_json_ld_blocks_are_capped_at_10_and_warning_added():
    payload = RawExtractionPayload(
        source_type="json_ld",
        source_url="https://example.com/recipe",
        json_ld_blocks=[{"name": f"Recipe {index}"} for index in range(12)],
    )

    prompt = build_gemini_prompt(payload)

    assert len(prompt.payload["json_ld_blocks"]) == 10
    assert any(
        "JSON-LD blocks" in warning and "10" in warning for warning in prompt.warnings
    )


def test_long_string_inside_json_ld_block_is_truncated_and_warning_added():
    payload = RawExtractionPayload(
        source_type="json_ld",
        source_url="https://example.com/recipe",
        json_ld_blocks=[{"recipeIngredient": ["flour", "x" * 10_100]}],
    )

    prompt = build_gemini_prompt(payload)

    assert len(prompt.payload["json_ld_blocks"][0]["recipeIngredient"][1]) == 10_000
    assert any(
        "JSON-LD string" in warning and "truncated" in warning
        for warning in prompt.warnings
    )


def test_serialized_payload_is_capped_and_warning_added():
    payload = RawExtractionPayload(
        source_type="json_ld",
        source_url="https://example.com/recipe",
        metadata={"notes": "x" * 70_000},
    )

    prompt = build_gemini_prompt(payload)

    serialized_payload = json.dumps(prompt.payload, ensure_ascii=False, sort_keys=True)
    assert len(serialized_payload) <= MAX_SERIALIZED_PAYLOAD_CHARS
    assert any(
        "Serialized payload" in warning and "truncated" in warning
        for warning in prompt.warnings
    )


def test_oversized_json_ld_payload_keeps_first_block_content():
    payload = RawExtractionPayload(
        source_type="json_ld",
        source_url="https://example.com/recipe",
        json_ld_blocks=[
            {
                "@type": "Recipe",
                "name": "Keep Me",
                "recipeIngredient": ["1 cup flour", "x" * 10_000],
            },
            {"@type": "Recipe", "name": "Drop Me", "recipeIngredient": ["y" * 10_000]},
            {
                "@type": "Recipe",
                "name": "Drop Me Too",
                "recipeIngredient": ["z" * 10_000],
            },
            {
                "@type": "Recipe",
                "name": "Also Drop",
                "recipeIngredient": ["w" * 10_000],
            },
            {
                "@type": "Recipe",
                "name": "Drop Last",
                "recipeIngredient": ["v" * 10_000],
            },
            {"@type": "Recipe", "name": "Drop End", "recipeIngredient": ["u" * 10_000]},
        ],
    )

    prompt = build_gemini_prompt(payload)

    serialized_payload = json.dumps(prompt.payload, ensure_ascii=False, sort_keys=True)
    assert len(serialized_payload) <= MAX_SERIALIZED_PAYLOAD_CHARS
    assert prompt.payload["json_ld_blocks"]
    assert prompt.payload["json_ld_blocks"][0]["name"] == "Keep Me"
    assert "1 cup flour" in prompt.payload["json_ld_blocks"][0]["recipeIngredient"]
    assert any("JSON-LD blocks dropped" in warning for warning in prompt.warnings)


def test_single_oversized_json_ld_block_is_reduced_but_kept():
    payload = RawExtractionPayload(
        source_type="json_ld",
        source_url="https://example.com/recipe",
        json_ld_blocks=[
            {
                "@type": "Recipe",
                "name": "Big Recipe",
                "recipeIngredient": [
                    "1 cup flour",
                    "2 tbsp sugar",
                    "x" * 10_000,
                    "y" * 10_000,
                    "z" * 10_000,
                    "w" * 10_000,
                    "v" * 10_000,
                    "u" * 10_000,
                    "t" * 10_000,
                ],
            }
        ],
    )

    prompt = build_gemini_prompt(payload)

    serialized_payload = json.dumps(prompt.payload, ensure_ascii=False, sort_keys=True)
    assert len(serialized_payload) <= MAX_SERIALIZED_PAYLOAD_CHARS
    assert prompt.payload["json_ld_blocks"]
    assert prompt.payload["json_ld_blocks"][0]["name"] == "Big Recipe"
    assert "1 cup flour" in prompt.payload["json_ld_blocks"][0]["recipeIngredient"]
    assert any("Remaining JSON-LD block" in warning for warning in prompt.warnings)


def test_prompt_text_marks_raw_data_as_untrusted_input():
    payload = RawExtractionPayload(
        source_type="json_ld",
        source_url="https://example.com/recipe",
    )

    prompt = build_gemini_prompt(payload)

    assert "untrusted input" in "\n".join(prompt.parts).lower()


def test_youtube_prompt_includes_source_url_instruction_rule():
    payload = RawExtractionPayload(
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=abc123",
        description="Ingredients\n- 1 cup rice",
    )

    prompt = build_gemini_prompt(payload)

    text = "\n".join(prompt.parts)
    assert "instructions must be exactly [source_url]" in text
    assert "https://www.youtube.com/watch?v=abc123" in text


def test_gemini_recipe_result_validates_normalized_recipe_and_confidence_bounds():
    result = GeminiRecipeResult(recipes=[_recipe()], confidence=0.75)

    assert result.recipes[0].name == "Garlic Noodles"
    assert result.confidence == 0.75
    assert result.warnings == []

    with pytest.raises(ValidationError):
        GeminiRecipeResult(recipes=[_recipe()], confidence=1.1)


def test_normalize_disabled_returns_disabled_without_call(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_client(monkeypatch, [_response(_gemini_json())])

    result = _run(_payload(), settings=_settings(enabled=False), rate_key="admin")

    assert result.accepted is False
    assert result.fallback_reason == "disabled"
    assert _FakeClient.instances == []


def test_normalize_missing_key_returns_not_configured(monkeypatch: pytest.MonkeyPatch):
    _patch_client(monkeypatch, [_response(_gemini_json())])

    result = _run(_payload(), settings=_settings(api_key=None), rate_key="admin")

    assert result.accepted is False
    assert result.fallback_reason == "not_configured"
    assert _FakeClient.instances == []


def test_normalize_missing_rate_key_returns_missing_rate_key(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_client(monkeypatch, [_response(_gemini_json())])

    result = _run(_payload(), settings=_settings(), rate_key="")

    assert result.accepted is False
    assert result.fallback_reason == "missing_rate_key"
    assert _FakeClient.instances == []


def test_valid_response_returns_accepted_recipes_model_and_warnings(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_client(monkeypatch, [_response(_gemini_json(warnings=["model warning"]))])

    result = _run(_payload(), settings=_settings(), rate_key="admin")

    assert result.accepted is True
    assert result.fallback_reason is None
    assert result.recipes == [_recipe()]
    assert result.normalization_model == "gemini-test"
    assert result.confidence == 0.9
    assert result.warnings == ["model warning"]
    assert len(_FakeClient.instances) == 1
    assert _FakeClient.instances[0].api_key == "test-key"
    assert _FakeClient.instances[0].http_options is None
    assert _FakeClient.instances[0].closed is True
    call = _FakeClient.instances[0].models.calls[0]
    assert call["model"] == "gemini-test"
    assert "contents" in call
    assert "config" in call
    assert "response_json_schema" in call["config"]
    assert "response_schema" not in call["config"]


def test_configured_timeout_does_not_set_sdk_deadline(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    _patch_client(monkeypatch, [_response(_gemini_json())])

    with caplog.at_level(logging.INFO, logger=gemini_normalizer.__name__):
        result = _run(_payload(), settings=_settings(timeout=8.0), rate_key="admin")

    assert result.accepted is True
    assert _FakeClient.instances[0].http_options is None
    assert "deadline=disabled" in caplog.text


def test_call_gemini_enforces_configured_timeout(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    async def _fake_to_thread(func: object) -> object:
        captured["thread_func"] = func
        return "gemini-response"

    async def _fake_wait_for(awaitable: object, *, timeout: float) -> object:
        captured["timeout"] = timeout
        return await awaitable

    monkeypatch.setattr(gemini_normalizer.asyncio, "to_thread", _fake_to_thread)
    monkeypatch.setattr(gemini_normalizer.asyncio, "wait_for", _fake_wait_for)

    result = asyncio.run(
        gemini_normalizer._call_gemini(
            settings=_settings(timeout=2.5),
            contents=["prompt"],
        )
    )

    assert result == "gemini-response"
    assert captured["timeout"] == 2.5
    assert callable(captured["thread_func"])


def test_prompt_truncation_warnings_are_included_with_model_warnings(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_client(monkeypatch, [_response(_gemini_json(warnings=["model warning"]))])
    payload = _payload(
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=abc123",
        description="x" * 20_100,
    )

    result = _run(payload, settings=_settings(), rate_key="admin")

    assert result.accepted is True
    assert any(
        "description" in warning and "truncated" in warning
        for warning in result.warnings
    )
    assert "model warning" in result.warnings


def test_low_confidence_then_valid_retries_and_accepts(monkeypatch: pytest.MonkeyPatch):
    _patch_client(
        monkeypatch,
        [
            _response(_gemini_json(confidence=0.69)),
            _response(_gemini_json(confidence=0.91)),
        ],
    )

    result = _run(_payload(), settings=_settings(), rate_key="admin")

    assert result.accepted is True
    assert result.fallback_reason is None
    assert result.confidence == 0.91
    assert len(_FakeModels.calls) == 2
    assert (
        "confidence must be at least 0.7"
        in json.dumps(_FakeModels.calls[1]["contents"]).lower()
    )
    assert "explicit" in json.dumps(_FakeModels.calls[1]["contents"]).lower()


def test_low_confidence_twice_returns_low_confidence(monkeypatch: pytest.MonkeyPatch):
    _patch_client(
        monkeypatch,
        [
            _response(_gemini_json(confidence=0.69)),
            _response(_gemini_json(confidence=0.65)),
        ],
    )

    result = _run(_payload(), settings=_settings(), rate_key="admin")

    assert result.accepted is False
    assert result.fallback_reason == "low_confidence"
    assert result.confidence == 0.65
    assert len(_FakeModels.calls) == 2


def test_invalid_then_valid_retries_once(monkeypatch: pytest.MonkeyPatch):
    _patch_client(
        monkeypatch,
        [
            _response('{"recipes": [], "confidence": 0.9, "warnings": []}'),
            _response(_gemini_json()),
        ],
    )

    result = _run(_payload(), settings=_settings(), rate_key="admin")

    assert result.accepted is True
    assert result.recipes == [_recipe()]
    assert len(_FakeModels.calls) == 2
    assert "validation" in json.dumps(_FakeModels.calls[1]["contents"]).lower()


def test_retry_counts_against_guardrails(monkeypatch: pytest.MonkeyPatch):
    _patch_client(
        monkeypatch,
        [
            _response('{"recipes": [], "confidence": 0.9, "warnings": []}'),
            _response(_gemini_json()),
        ],
    )

    result = _run(_payload(), settings=_settings(rate_limit=1), rate_key="admin")

    assert result.accepted is False
    assert result.fallback_reason == "rate_limited"
    assert result.confidence == 0.9
    assert result.normalization_model == "gemini-test"
    assert len(_FakeModels.calls) == 1


def test_invalid_twice_returns_invalid_output(monkeypatch: pytest.MonkeyPatch):
    _patch_client(
        monkeypatch,
        [
            _response('{"recipes": [], "confidence": 0.9, "warnings": []}'),
            _response('{"recipes": [], "confidence": 0.9, "warnings": []}'),
        ],
    )

    result = _run(_payload(), settings=_settings(), rate_key="admin")

    assert result.accepted is False
    assert result.fallback_reason == "invalid_output"
    assert len(_FakeModels.calls) == 2


def test_timeout_returns_timeout(monkeypatch: pytest.MonkeyPatch):
    async def _raise_timeout(*args: object, **kwargs: object) -> object:
        raise asyncio.TimeoutError()

    _patch_client(monkeypatch, [_response(_gemini_json())])
    monkeypatch.setattr(gemini_normalizer, "_call_gemini", _raise_timeout)

    result = _run(_payload(), settings=_settings(), rate_key="admin")

    assert result.accepted is False
    assert result.fallback_reason == "timeout"


def test_provider_exception_returns_provider_error_and_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    _patch_client(monkeypatch, [RuntimeError("provider down")])

    with caplog.at_level(logging.ERROR, logger=gemini_normalizer.__name__):
        result = _run(_payload(), settings=_settings(), rate_key="admin")

    assert result.accepted is False
    assert result.fallback_reason == "provider_error"
    assert len(_FakeClient.instances) == 1
    assert _FakeClient.instances[0].closed is True
    assert "Gemini normalization provider error" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert "test-key" not in caplog.text
    assert "Garlic Noodles" not in caplog.text


def test_rate_limited_returns_rate_limited(monkeypatch: pytest.MonkeyPatch):
    _patch_client(monkeypatch, [_response(_gemini_json())])

    settings = _settings(rate_limit=1)
    assert _run(_payload(), settings=settings, rate_key="admin").accepted is True
    result = _run(_payload(), settings=settings, rate_key="admin")

    assert result.accepted is False
    assert result.fallback_reason == "rate_limited"


def test_circuit_open_returns_circuit_open(monkeypatch: pytest.MonkeyPatch):
    _patch_client(monkeypatch, [_response(_gemini_json())])
    guardrails = GeminiGuardrails()
    for index in range(5):
        guardrails.record_failure(now=float(index))
    monkeypatch.setattr(gemini_normalizer, "gemini_guardrails", guardrails)

    result = _run(_payload(), settings=_settings(), rate_key="admin")

    assert result.accepted is False
    assert result.fallback_reason == "circuit_open"
    assert _FakeClient.instances == []
