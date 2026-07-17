import asyncio
from typing import Any, Optional
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException

from app.services.gemini.client import (
    GeminiErrorDetails,
    RateLimiter,
    candidate_text,
    map_status_error,
    post_generate_content,
)


DETAILS = GeminiErrorDetails(
    busy="busy detail",
    not_configured="not configured detail",
    timeout="timeout detail",
    rejected="rejected detail",
    unreachable="unreachable detail",
    upstream_template="upstream {status_code} detail",
)


class _Response:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("POST", "https://example.test"),
                response=httpx.Response(self.status_code, json=self._payload),
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


def _post(client: _AsyncClientContext):
    with patch(
        "app.services.gemini.client.httpx.AsyncClient",
        return_value=client,
    ):
        return asyncio.run(
            post_generate_content(
                "https://example.test/models/m:generateContent",
                {"contents": []},
                api_key="key-123",
                timeout_seconds=1.0,
                details=DETAILS,
            )
        )


def test_rate_limiter_admits_exactly_the_limit_per_rolling_minute():
    limiter = RateLimiter()

    assert [limiter.try_acquire(3) for _ in range(4)] == [True, True, True, False]


def test_rate_limiter_reset_clears_the_budget():
    limiter = RateLimiter()
    for _ in range(3):
        limiter.try_acquire(3)

    limiter.reset()

    assert limiter.try_acquire(3) is True


def test_rate_limiter_treats_a_zero_limit_as_one():
    limiter = RateLimiter()

    assert limiter.try_acquire(0) is True
    assert limiter.try_acquire(0) is False


def test_rate_limiter_instances_hold_independent_budgets():
    exhausted = RateLimiter()
    fresh = RateLimiter()
    for _ in range(3):
        exhausted.try_acquire(3)

    # A best-effort caller must never be able to starve a blocking one.
    assert exhausted.try_acquire(3) is False
    assert fresh.try_acquire(3) is True


@pytest.mark.parametrize(
    ("status_code", "payload", "expected_status", "expected_detail"),
    [
        (429, {}, 429, "busy detail"),
        (403, {}, 503, "not configured detail"),
        (404, {}, 503, "not configured detail"),
        (400, {"error": {"status": "FAILED_PRECONDITION"}}, 503, "not configured detail"),
        (400, {"error": {"status": "INVALID_ARGUMENT"}}, 502, "rejected detail"),
        (418, {}, 502, "upstream 418 detail"),
    ],
)
def test_map_status_error_uses_the_injected_details(
    status_code, payload, expected_status, expected_detail
):
    error = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("POST", "https://example.test"),
        response=httpx.Response(status_code, json=payload),
    )

    mapped = map_status_error(error, DETAILS)

    assert mapped.status_code == expected_status
    assert mapped.detail == expected_detail


def test_map_status_error_survives_an_unreadable_body():
    error = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("POST", "https://example.test"),
        response=httpx.Response(400, content=b"not json"),
    )

    mapped = map_status_error(error, DETAILS)

    assert mapped.status_code == 502
    assert mapped.detail == "rejected detail"


def test_post_generate_content_sends_the_api_key_header_and_body():
    client = _AsyncClientContext(_Response({"ok": True}))

    _post(client)

    assert client.calls == 1
    assert client.headers["x-goog-api-key"] == "key-123"
    assert client.headers["Content-Type"] == "application/json"
    assert client.body == {"contents": []}


def test_post_generate_content_retries_once_on_a_retryable_status():
    client = _AsyncClientContext(_Response({}, status_code=503))

    with pytest.raises(HTTPException) as error:
        _post(client)

    assert client.calls == 2
    assert error.value.status_code == 502
    assert error.value.detail == "upstream 503 detail"


def test_post_generate_content_does_not_retry_a_non_retryable_status():
    client = _AsyncClientContext(_Response({}, status_code=429))

    with pytest.raises(HTTPException) as error:
        _post(client)

    assert client.calls == 1
    assert error.value.status_code == 429


def test_post_generate_content_retries_then_reports_a_timeout():
    client = _AsyncClientContext(error=httpx.ConnectTimeout("timed out"))

    with pytest.raises(HTTPException) as error:
        _post(client)

    assert client.calls == 2
    assert error.value.status_code == 504
    assert error.value.detail == "timeout detail"


def test_post_generate_content_maps_a_transport_error_without_retrying():
    client = _AsyncClientContext(error=httpx.ConnectError("no route"))

    with pytest.raises(HTTPException) as error:
        _post(client)

    assert client.calls == 1
    assert error.value.status_code == 502
    assert error.value.detail == "unreachable detail"


def test_candidate_text_reads_the_first_non_blank_part():
    payload = {
        "candidates": [
            {"content": {"parts": [{"text": "   "}, {"text": "chosen"}]}}
        ]
    }

    assert candidate_text(payload) == "chosen"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "not a dict",
        {},
        {"candidates": []},
        {"candidates": "nope"},
        {"candidates": [{}]},
        {"candidates": [{"content": {}}]},
        {"candidates": [{"content": {"parts": "nope"}}]},
        {"candidates": [{"content": {"parts": [{"text": "  "}]}}]},
    ],
)
def test_candidate_text_returns_none_for_unusable_payloads(payload):
    assert candidate_text(payload) is None
