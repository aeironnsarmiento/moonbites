from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import httpx
from fastapi import HTTPException

from ..core.config import Settings


def build_request_headers(settings: Settings) -> dict[str, str]:
    return {
        "User-Agent": settings.user_agent,
        "Accept": settings.accept_header,
        "Accept-Language": settings.accept_language_header,
    }


def _build_403_retry_headers(settings: Settings) -> dict[str, str]:
    return {
        **build_request_headers(settings),
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }


async def get_with_403_retry(
    client: httpx.AsyncClient, url: str, settings: Settings
) -> httpx.Response:
    response = await client.get(url)

    if response.status_code == 403:
        response = await client.get(url, headers=_build_403_retry_headers(settings))

    return response


async def get_page(url: str, settings: Settings) -> httpx.Response:
    """Browser-headed GET with redirects and the 403 retry, raising for status.

    This is the direct-fetch path for URLs an admin pasted or a host we trust
    (a TikTok page). Links found *inside* third-party content go through
    ``public_web.safe_fetch`` instead.
    """
    async with httpx.AsyncClient(
        headers=build_request_headers(settings),
        follow_redirects=True,
        timeout=settings.request_timeout_seconds,
    ) as client:
        response = await get_with_403_retry(client, url, settings)
        response.raise_for_status()
        return response


@dataclass(frozen=True)
class UpstreamErrorDetails:
    """User-facing messages for the three ways an upstream fetch fails."""

    timeout: str
    status: str  # format string; receives ``status_code``
    unreachable: str
    not_found: str | None = None
    not_found_statuses: frozenset[int] = frozenset()


@contextmanager
def translate_httpx_errors(details: UpstreamErrorDetails) -> Iterator[None]:
    """Map httpx failures to the HTTPException each extractor used to raise
    by hand: 504 on timeout, 502 with the upstream status, 502 otherwise, and
    optionally 404 for statuses the caller treats as "post not found"."""
    try:
        yield
    except httpx.TimeoutException as error:
        raise HTTPException(status_code=504, detail=details.timeout) from error
    except httpx.HTTPStatusError as error:
        status_code = error.response.status_code
        if details.not_found is not None and status_code in details.not_found_statuses:
            raise HTTPException(status_code=404, detail=details.not_found) from error
        raise HTTPException(
            status_code=502,
            detail=details.status.format(status_code=status_code),
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=details.unreachable) from error
