from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from fastapi import HTTPException


GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


@dataclass(frozen=True)
class GeminiErrorDetails:
    """User-facing copy for a caller's mapped errors.

    Detail strings surface verbatim in the UI, so each caller owns its own
    wording rather than sharing a generic catalog.
    """

    busy: str
    not_configured: str
    timeout: str
    rejected: str
    unreachable: str
    upstream_template: str


class RateLimiter:
    """A rolling one-minute call budget.

    Each caller holds its own instance: a best-effort caller must not be able
    to exhaust the budget of one whose failure blocks a user request.
    """

    def __init__(self) -> None:
        self._timestamps: deque[float] = deque()

    def try_acquire(self, limit: int) -> bool:
        now = time.monotonic()
        while self._timestamps and now - self._timestamps[0] >= 60.0:
            self._timestamps.popleft()
        if len(self._timestamps) >= max(limit, 1):
            return False
        self._timestamps.append(now)
        return True

    def reset(self) -> None:
        self._timestamps.clear()


def map_status_error(
    error: httpx.HTTPStatusError,
    details: GeminiErrorDetails,
) -> HTTPException:
    status_code = error.response.status_code

    status_token = ""
    try:
        payload = error.response.json()
        status_token = str(payload.get("error", {}).get("status") or "")
    except Exception:  # pragma: no cover - defensive body parse
        status_token = ""

    if status_code == 429:
        return HTTPException(status_code=429, detail=details.busy)
    if status_code in (403, 404):
        return HTTPException(status_code=503, detail=details.not_configured)
    if status_code == 400:
        if status_token == "FAILED_PRECONDITION":
            return HTTPException(status_code=503, detail=details.not_configured)
        return HTTPException(status_code=502, detail=details.rejected)
    return HTTPException(
        status_code=502,
        detail=details.upstream_template.format(status_code=status_code),
    )


async def post_generate_content(
    request_url: str,
    request_body: dict[str, Any],
    *,
    api_key: str,
    timeout_seconds: float,
    details: GeminiErrorDetails,
) -> httpx.Response:
    last_exception: Optional[HTTPException] = None
    last_cause: Optional[Exception] = None

    for _ in range(2):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    request_url,
                    headers={
                        "x-goog-api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )
                response.raise_for_status()
                return response
        except httpx.TimeoutException as error:
            last_exception = HTTPException(status_code=504, detail=details.timeout)
            last_cause = error
        except httpx.HTTPStatusError as error:
            mapped = map_status_error(error, details)
            if error.response.status_code not in _RETRYABLE_STATUS_CODES:
                raise mapped from error
            last_exception = mapped
            last_cause = error
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=502,
                detail=details.unreachable,
            ) from error

    if last_exception is None:  # pragma: no cover - unreachable by loop shape
        last_exception = HTTPException(status_code=502, detail=details.unreachable)
    raise last_exception from last_cause


def candidate_text(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return None
    for part in parts:
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                return text
    return None
