from __future__ import annotations

import asyncio
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services.http_utils import (
    UpstreamErrorDetails,
    get_page,
    translate_httpx_errors,
)


DETAILS = UpstreamErrorDetails(
    timeout="Upstream timed out",
    status="Upstream returned HTTP {status_code}",
    unreachable="Unable to reach upstream",
)

DETAILS_WITH_NOT_FOUND = UpstreamErrorDetails(
    timeout="Upstream timed out",
    status="Upstream returned HTTP {status_code}",
    unreachable="Unable to reach upstream",
    not_found="Post was not found",
    not_found_statuses=frozenset({400, 404}),
)


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
    )


def _status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://upstream.example/")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("failed", request=request, response=response)


def _raise_inside(details: UpstreamErrorDetails, error: Exception) -> HTTPException:
    with pytest.raises(HTTPException) as exc_info:
        with translate_httpx_errors(details):
            raise error
    return exc_info.value


def test_translate_httpx_errors_maps_timeout_to_504():
    error = _raise_inside(DETAILS, httpx.ReadTimeout("slow"))

    assert error.status_code == 504
    assert error.detail == "Upstream timed out"


def test_translate_httpx_errors_maps_status_error_to_502_with_status_code():
    error = _raise_inside(DETAILS, _status_error(500))

    assert error.status_code == 502
    assert error.detail == "Upstream returned HTTP 500"


def test_translate_httpx_errors_maps_connect_error_to_502_fallback():
    error = _raise_inside(DETAILS, httpx.ConnectError("refused"))

    assert error.status_code == 502
    assert error.detail == "Unable to reach upstream"


@pytest.mark.parametrize("status_code", [400, 404])
def test_translate_httpx_errors_maps_not_found_statuses_to_404(status_code):
    error = _raise_inside(DETAILS_WITH_NOT_FOUND, _status_error(status_code))

    assert error.status_code == 404
    assert error.detail == "Post was not found"


def test_translate_httpx_errors_without_not_found_mapping_keeps_404_as_502():
    error = _raise_inside(DETAILS, _status_error(404))

    assert error.status_code == 502
    assert error.detail == "Upstream returned HTTP 404"


def test_translate_httpx_errors_passes_other_exceptions_through():
    with pytest.raises(ValueError):
        with translate_httpx_errors(DETAILS):
            raise ValueError("not an httpx failure")


def _patched_client(handler):
    real_client = httpx.AsyncClient

    def factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    return patch("app.services.http_utils.httpx.AsyncClient", side_effect=factory)


def test_get_page_retries_once_with_403_headers():
    requests: list[httpx.Request] = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(403)
        return httpx.Response(200, text="<html>ok</html>")

    with _patched_client(handler):
        response = asyncio.run(get_page("https://blog.example/recipe", _settings()))

    assert response.status_code == 200
    assert len(requests) == 2
    assert "Sec-Fetch-Mode" not in requests[0].headers
    assert requests[1].headers["Sec-Fetch-Mode"] == "navigate"
    assert requests[1].headers["User-Agent"] == "test-agent"


def test_get_page_raises_on_final_non_2xx():
    requests: list[httpx.Request] = []

    def handler(request):
        requests.append(request)
        return httpx.Response(403)

    with _patched_client(handler):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            asyncio.run(get_page("https://blog.example/recipe", _settings()))

    assert exc_info.value.response.status_code == 403
    assert len(requests) == 2
