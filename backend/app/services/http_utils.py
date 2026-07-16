from __future__ import annotations

import httpx

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


def _should_retry_403(response: httpx.Response, *, retried: bool) -> bool:
    return not retried and response.status_code == 403


async def get_with_403_retry(
    client: httpx.AsyncClient, url: str, settings: Settings
) -> httpx.Response:
    response = await client.get(url)

    if _should_retry_403(response, retried=False):
        response = await client.get(url, headers=_build_403_retry_headers(settings))

    return response
