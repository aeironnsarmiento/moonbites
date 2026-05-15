from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

try:
    from google import genai
    from google.genai import types as genai_types
except ModuleNotFoundError:  # pragma: no cover - exercised only without dependency.

    class _MissingGenAI:
        class Client:  # type: ignore[no-untyped-def]
            def __init__(self, *args: object, **kwargs: object) -> None:
                raise RuntimeError("google-genai is not installed")

    class _MissingGenAITypes:
        class HttpOptions:  # type: ignore[no-untyped-def]
            def __init__(self, *args: object, **kwargs: object) -> None:
                raise RuntimeError("google-genai is not installed")

    genai = _MissingGenAI()  # type: ignore[assignment]
    genai_types = _MissingGenAITypes()  # type: ignore[assignment]

from ...core.config import Settings
from ...schemas.extract import NormalizedRecipe
from .guardrails import gemini_guardrails
from .prompt import build_gemini_prompt
from .types import GeminiRecipeResult, RawExtractionPayload

MIN_CONFIDENCE = 0.7
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeminiNormalizationResult:
    recipes: list[NormalizedRecipe] = field(default_factory=list)
    accepted: bool = False
    warnings: list[str] = field(default_factory=list)
    fallback_reason: str | None = None
    normalization_model: str | None = None
    confidence: float | None = None


async def normalize_with_gemini(
    payload: RawExtractionPayload,
    *,
    settings: Settings,
    rate_key: str | None,
) -> GeminiNormalizationResult:
    if not settings.gemini_normalization_enabled:
        logger.info(
            "Gemini normalization skipped source_type=%s reason=disabled",
            payload.source_type,
        )
        return _skipped("disabled")

    if not settings.gemini_api_key:
        logger.warning(
            "Gemini normalization skipped source_type=%s reason=not_configured",
            payload.source_type,
        )
        return _skipped("not_configured")

    normalized_rate_key = (rate_key or "").strip()
    if not normalized_rate_key:
        logger.warning(
            "Gemini normalization skipped source_type=%s reason=missing_rate_key",
            payload.source_type,
        )
        return _skipped("missing_rate_key")

    now = time.monotonic()
    allowed, guardrail_reason = gemini_guardrails.allow_call(
        normalized_rate_key,
        limit=settings.gemini_rate_limit_per_minute,
        now=now,
    )
    if not allowed:
        logger.warning(
            "Gemini normalization skipped source_type=%s reason=%s model=%s",
            payload.source_type,
            guardrail_reason or "rate_limited",
            settings.gemini_model,
        )
        return _skipped(guardrail_reason or "rate_limited")

    prompt = build_gemini_prompt(payload)
    warnings = list(prompt.warnings)
    logger.info(
        "Gemini normalization attempt started source_type=%s attempt=initial model=%s deadline=disabled warning_count=%d",
        payload.source_type,
        settings.gemini_model,
        len(warnings),
    )

    try:
        first_response = await _call_gemini(
            settings=settings,
            contents=prompt.parts,
        )
    except asyncio.TimeoutError:
        gemini_guardrails.record_failure(now=time.monotonic())
        logger.warning(
            "Gemini normalization timed out source_type=%s attempt=initial model=%s deadline=disabled",
            payload.source_type,
            settings.gemini_model,
        )
        return _skipped("timeout", warnings=warnings)
    except Exception as error:
        gemini_guardrails.record_failure(now=time.monotonic())
        logger.exception(
            "Gemini normalization provider error source_type=%s attempt=initial model=%s error_type=%s",
            payload.source_type,
            settings.gemini_model,
            type(error).__name__,
        )
        return _skipped("provider_error", warnings=warnings)

    first_validation = _validate_response(first_response)
    if first_validation.accepted:
        gemini_guardrails.record_success()
        logger.info(
            "Gemini normalization accepted source_type=%s attempt=initial model=%s confidence=%s warning_count=%d",
            payload.source_type,
            settings.gemini_model,
            first_validation.confidence,
            len(warnings) + len(first_validation.warnings),
        )
        return _accepted(first_validation.result, settings=settings, warnings=warnings)

    logger.warning(
        "Gemini normalization retry requested source_type=%s model=%s reason=%s confidence=%s warning_count=%d",
        payload.source_type,
        settings.gemini_model,
        first_validation.reason,
        first_validation.confidence,
        len(warnings) + len(first_validation.warnings),
    )

    retry_allowed, retry_guardrail_reason = gemini_guardrails.allow_call(
        normalized_rate_key,
        limit=settings.gemini_rate_limit_per_minute,
        now=time.monotonic(),
    )
    if not retry_allowed:
        logger.warning(
            "Gemini normalization retry skipped source_type=%s reason=%s model=%s confidence=%s",
            payload.source_type,
            retry_guardrail_reason or "rate_limited",
            settings.gemini_model,
            first_validation.confidence,
        )
        return _skipped(
            retry_guardrail_reason or "rate_limited",
            warnings=warnings + first_validation.warnings,
            confidence=first_validation.confidence,
            normalization_model=settings.gemini_model,
        )

    logger.info(
        "Gemini normalization attempt started source_type=%s attempt=retry model=%s deadline=disabled warning_count=%d",
        payload.source_type,
        settings.gemini_model,
        len(warnings) + len(first_validation.warnings),
    )

    try:
        retry_response = await _call_gemini(
            settings=settings,
            contents=[
                *prompt.parts,
                (
                    "Previous output failed validation. Return corrected JSON only. "
                    f"Validation error: {first_validation.error_context}"
                ),
            ],
        )
    except asyncio.TimeoutError:
        gemini_guardrails.record_failure(now=time.monotonic())
        logger.warning(
            "Gemini normalization timed out source_type=%s attempt=retry model=%s deadline=disabled",
            payload.source_type,
            settings.gemini_model,
        )
        return _skipped("timeout", warnings=warnings)
    except Exception as error:
        gemini_guardrails.record_failure(now=time.monotonic())
        logger.exception(
            "Gemini normalization provider error source_type=%s attempt=retry model=%s error_type=%s",
            payload.source_type,
            settings.gemini_model,
            type(error).__name__,
        )
        return _skipped("provider_error", warnings=warnings)

    retry_validation = _validate_response(retry_response)
    if retry_validation.accepted:
        gemini_guardrails.record_success()
        logger.info(
            "Gemini normalization accepted source_type=%s attempt=retry model=%s confidence=%s warning_count=%d",
            payload.source_type,
            settings.gemini_model,
            retry_validation.confidence,
            len(warnings) + len(retry_validation.warnings),
        )
        return _accepted(retry_validation.result, settings=settings, warnings=warnings)

    if retry_validation.reason == "low_confidence":
        logger.warning(
            "Gemini normalization rejected source_type=%s attempt=retry model=%s reason=low_confidence confidence=%s warning_count=%d",
            payload.source_type,
            settings.gemini_model,
            retry_validation.confidence,
            len(warnings) + len(retry_validation.warnings),
        )
        return _skipped(
            "low_confidence",
            warnings=warnings + retry_validation.warnings,
            confidence=retry_validation.confidence,
            normalization_model=settings.gemini_model,
        )

    gemini_guardrails.record_failure(now=time.monotonic())
    logger.warning(
        "Gemini normalization rejected source_type=%s attempt=retry model=%s reason=invalid_output confidence=%s warning_count=%d",
        payload.source_type,
        settings.gemini_model,
        retry_validation.confidence,
        len(warnings) + len(retry_validation.warnings),
    )
    return _skipped(
        "invalid_output",
        warnings=warnings + retry_validation.warnings,
        confidence=retry_validation.confidence,
        normalization_model=settings.gemini_model,
    )


async def _call_gemini(*, settings: Settings, contents: list[str]) -> Any:
    def call_sync_sdk() -> Any:
        client = genai.Client(api_key=settings.gemini_api_key)
        try:
            return client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config={
                    "temperature": 0,
                    "response_mime_type": "application/json",
                    "response_json_schema": GeminiRecipeResult.model_json_schema(),
                },
            )
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    return await asyncio.wait_for(
        asyncio.to_thread(call_sync_sdk),
        timeout=settings.gemini_timeout_seconds,
    )


@dataclass(frozen=True)
class _ValidationOutcome:
    accepted: bool
    result: GeminiRecipeResult | None = None
    reason: str | None = None
    error_context: str | None = None
    warnings: list[str] = field(default_factory=list)
    confidence: float | None = None


def _validate_response(response: Any) -> _ValidationOutcome:
    text = getattr(response, "text", None)
    if not isinstance(text, str) or not text.strip():
        return _invalid("Missing response text.")

    try:
        result = GeminiRecipeResult.model_validate_json(text)
    except ValidationError as exc:
        return _invalid(_validation_error_context(exc))
    except ValueError as exc:
        return _invalid(str(exc))

    if not result.recipes:
        return _ValidationOutcome(
            accepted=False,
            reason="invalid_output",
            error_context="At least one recipe is required.",
            warnings=list(result.warnings),
            confidence=result.confidence,
        )

    if result.confidence < MIN_CONFIDENCE:
        return _ValidationOutcome(
            accepted=False,
            reason="low_confidence",
            error_context=(
                f"Confidence must be at least {MIN_CONFIDENCE}. "
                "Only return recipes when recipe information is explicit in the "
                "supplied raw data."
            ),
            warnings=list(result.warnings),
            confidence=result.confidence,
        )

    return _ValidationOutcome(accepted=True, result=result)


def _validation_error_context(exc: ValidationError) -> str:
    return json.dumps(exc.errors(), ensure_ascii=False)


def _invalid(error_context: str) -> _ValidationOutcome:
    return _ValidationOutcome(
        accepted=False,
        reason="invalid_output",
        error_context=error_context,
    )


def _accepted(
    result: GeminiRecipeResult | None,
    *,
    settings: Settings,
    warnings: list[str],
) -> GeminiNormalizationResult:
    if result is None:
        return _skipped("invalid_output", warnings=warnings)

    return GeminiNormalizationResult(
        recipes=result.recipes,
        accepted=True,
        warnings=warnings + list(result.warnings),
        fallback_reason=None,
        normalization_model=settings.gemini_model,
        confidence=result.confidence,
    )


def _skipped(
    reason: str,
    *,
    warnings: list[str] | None = None,
    confidence: float | None = None,
    normalization_model: str | None = None,
) -> GeminiNormalizationResult:
    return GeminiNormalizationResult(
        accepted=False,
        warnings=warnings or [],
        fallback_reason=reason,
        normalization_model=normalization_model,
        confidence=confidence,
    )
