from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from urllib.parse import parse_qs

import httpx
import pytest

from app.core.config import Settings
from app.services.instagram.apify import ApifyClient
from app.services.instagram.models import (
    ApifyProviderError,
    ApifyRunStatus,
    ProviderErrorCode,
)
from app.services.instagram.urls import parse_instagram_reel_url


REEL_ACTOR_ID = "xMc5Ga1oCONPmWJIa"
PROFILE_ACTOR_ID = "dSCLg0C3YEZ83HzYX"
RUN_ID = "HG7ML7M8z78YcAPEB"
DATASET_ID = "wmKPijuyDnPZAPRMk"


def _settings(**overrides) -> Settings:
    settings = Settings(
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
        instagram_apify_token="secret-token",
    )
    return replace(settings, **overrides)


def _json_response(payload, status=200, headers=None):
    return httpx.Response(
        status,
        json=payload,
        headers={"content-type": "application/json", **(headers or {})},
    )


def _preflight_response(request: httpx.Request):
    if request.url.path == "/v2/users/me":
        return _json_response(
            {
                "data": {
                    "isPaying": False,
                    "plan": {
                        "tier": "FREE",
                        "isEnabled": True,
                        "monthlyBasePriceUsd": 0,
                        "monthlyUsageCreditsUsd": 5,
                        "maxMonthlyUsageUsd": 5,
                    },
                }
            }
        )
    if request.url.path == "/v2/users/me/limits":
        return _json_response(
            {
                "data": {
                    "limits": {"maxMonthlyUsageUsd": 5},
                    "current": {"monthlyUsageUsd": 1.25},
                }
            }
        )
    if request.url.path == "/v2/users/me/usage/monthly":
        return _json_response(
            {"data": {"totalUsageCreditsUsdAfterVolumeDiscount": 1.25}}
        )
    return None


def _client(handler, **settings_overrides):
    return ApifyClient(
        _settings(**settings_overrides), transport=httpx.MockTransport(handler)
    )


def test_start_reel_preflights_spend_and_uses_pinned_capped_async_request():
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        if response := _preflight_response(request):
            return response
        assert request.url.path == f"/v2/actors/{REEL_ACTOR_ID}/runs"
        assert parse_qs(request.url.query.decode()) == {
            "build": ["0.0.542"],
            "maxItems": ["1"],
            "maxTotalChargeUsd": ["0.0073"],
            "restartOnError": ["false"],
            "timeout": ["120"],
            "waitForFinish": ["0"],
        }
        assert json.loads(request.content) == {
            "username": ["https://www.instagram.com/reel/DZuzc9PNedT/"],
            "includeSharesCount": False,
            "includeTranscript": False,
            "includeDownloadedVideo": False,
        }
        return _json_response(
            {"data": {"id": RUN_ID, "status": "READY", "defaultDatasetId": DATASET_ID}},
            201,
        )

    run = asyncio.run(
        _client(handler).start_reel(
            parse_instagram_reel_url(
                "https://www.instagram.com/reel/DZuzc9PNedT/?igsh=discard"
            )
        )
    )

    assert run.run_id == RUN_ID
    assert run.status is ApifyRunStatus.READY
    assert run.default_dataset_id == DATASET_ID
    assert [request.url.path for request in requests[:3]] == [
        "/v2/users/me",
        "/v2/users/me/limits",
        "/v2/users/me/usage/monthly",
    ]
    assert all(request.url.host == "api.apify.com" for request in requests)
    assert all(request.url.scheme == "https" for request in requests)
    assert all(request.headers["authorization"] == "Bearer secret-token" for request in requests)
    assert all("secret-token" not in str(request.url) for request in requests)


def test_start_profile_rechecks_usage_and_disables_paid_about_section():
    paths = []

    def handler(request: httpx.Request):
        paths.append(request.url.path)
        if response := _preflight_response(request):
            return response
        assert request.url.path == f"/v2/actors/{PROFILE_ACTOR_ID}/runs"
        assert parse_qs(request.url.query.decode())["build"] == ["0.0.580"]
        assert parse_qs(request.url.query.decode())["maxTotalChargeUsd"] == ["0.0026"]
        assert json.loads(request.content) == {
            "usernames": ["tasty"],
            "includeAboutSection": False,
        }
        return _json_response({"data": {"id": RUN_ID, "status": "RUNNING"}}, 201)

    run = asyncio.run(_client(handler).start_profile("tasty"))

    assert run.status is ApifyRunStatus.RUNNING
    assert paths.count("/v2/users/me/usage/monthly") == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"instagram_apify_token": None},
        {"instagram_reel_actor_build": ""},
        {"instagram_reel_max_charge_usd": None},
        {"instagram_reel_actor_id": "unapproved"},
        {"instagram_profile_actor_id": "unapproved"},
    ],
)
def test_unsafe_or_missing_configuration_fails_before_network(overrides):
    called = False

    def handler(_request):
        nonlocal called
        called = True
        raise AssertionError("network must not be reached")

    with pytest.raises(ApifyProviderError) as exc_info:
        ApifyClient(_settings(**overrides), transport=httpx.MockTransport(handler))

    assert exc_info.value.code is ProviderErrorCode.PROVIDER_UNAVAILABLE
    assert called is False


@pytest.mark.parametrize(
    "account_patch",
    [
        {"tier": "PERSONAL"},
        {"isEnabled": False},
        {"monthlyBasePriceUsd": 1},
        {"monthlyUsageCreditsUsd": 4},
        {"isPaying": True},
        {"maxMonthlyUsageUsd": 6},
        {"usage": 4.5},
    ],
)
def test_spend_contract_drift_fails_before_actor_start(account_patch):
    started = False

    def handler(request: httpx.Request):
        nonlocal started
        if request.url.path == "/v2/users/me":
            plan = {
                "tier": "FREE",
                "isEnabled": True,
                "monthlyBasePriceUsd": 0,
                "monthlyUsageCreditsUsd": 5,
                "maxMonthlyUsageUsd": 5,
            }
            plan.update({k: v for k, v in account_patch.items() if k in plan})
            return _json_response(
                {"data": {"isPaying": account_patch.get("isPaying", False), "plan": plan}}
            )
        if request.url.path == "/v2/users/me/limits":
            return _json_response(
                {
                    "data": {
                        "limits": {
                            "maxMonthlyUsageUsd": account_patch.get("maxMonthlyUsageUsd", 5)
                        },
                        "current": {
                            "monthlyUsageUsd": account_patch.get("usage", 1)
                        },
                    }
                }
            )
        if request.url.path == "/v2/users/me/usage/monthly":
            return _json_response(
                {
                    "data": {
                        "totalUsageCreditsUsdAfterVolumeDiscount": account_patch.get("usage", 1)
                    }
                }
            )
        started = True
        raise AssertionError("actor must not start")

    with pytest.raises(ApifyProviderError) as exc_info:
        asyncio.run(
            _client(handler).start_reel(
                parse_instagram_reel_url("https://instagram.com/reel/abc123/")
            )
        )

    assert exc_info.value.code is ProviderErrorCode.PROVIDER_UNAVAILABLE
    assert started is False


def test_poll_run_accepts_only_known_ids_and_statuses():
    def handler(request: httpx.Request):
        assert request.url.path == f"/v2/actor-runs/{RUN_ID}"
        return _json_response(
            {"data": {"id": RUN_ID, "status": "SUCCEEDED", "defaultDatasetId": DATASET_ID}}
        )

    run = asyncio.run(_client(handler).get_run(RUN_ID))
    assert run.status is ApifyRunStatus.SUCCEEDED

    with pytest.raises(ApifyProviderError):
        asyncio.run(_client(handler).get_run("../users/me"))

    def unknown_status(_request):
        return _json_response({"data": {"id": RUN_ID, "status": "NEW_STATUS"}})

    with pytest.raises(ApifyProviderError) as exc_info:
        asyncio.run(_client(unknown_status).get_run(RUN_ID))
    assert exc_info.value.code is ProviderErrorCode.PROVIDER_INVALID_RESPONSE


def test_reel_dataset_read_is_bounded_allowlisted_and_strictly_adapted():
    def handler(request: httpx.Request):
        assert request.url.path == f"/v2/datasets/{DATASET_ID}/items"
        assert parse_qs(request.url.query.decode()) == {
            "clean": ["1"],
            "limit": ["2"],
            "fields": [
                "shortCode,url,caption,displayUrl,ownerUsername,inputUrl,error,errorDescription"
            ],
        }
        return _json_response(
            [
                {
                    "shortCode": "DZuzc9PNedT",
                    "url": "https://www.instagram.com/p/DZuzc9PNedT/",
                    "caption": None,
                    "displayUrl": "https://cdn.example/reel.webp",
                    "ownerUsername": "creator.name",
                    "inputUrl": "https://www.instagram.com/reel/DZuzc9PNedT/",
                    "ignored": "additive field",
                }
            ]
        )

    result = asyncio.run(
        _client(handler).get_reel_result(
            DATASET_ID,
            parse_instagram_reel_url("https://instagram.com/reel/DZuzc9PNedT/"),
        )
    )

    assert result.caption is None
    assert result.canonical_url == "https://www.instagram.com/reel/DZuzc9PNedT/"
    assert result.owner_username == "creator.name"
    assert result.thumbnail_url == "https://cdn.example/reel.webp"


@pytest.mark.parametrize(
    "items",
    [
        [],
        [{}, {}],
        {"not": "a list"},
        [{"error": "private", "errorDescription": "sensitive"}],
        [{"shortCode": "wrong", "caption": "", "displayUrl": "https://cdn/x", "ownerUsername": "u"}],
        [{"shortCode": "abc", "caption": 42, "displayUrl": "https://cdn/x", "ownerUsername": "u"}],
        [{"shortCode": "abc", "caption": "", "displayUrl": "http://cdn/x", "ownerUsername": "u"}],
    ],
)
def test_reel_adapter_rejects_drift_without_leaking_payload(items):
    def handler(_request):
        return _json_response(items)

    with pytest.raises(ApifyProviderError) as exc_info:
        asyncio.run(
            _client(handler).get_reel_result(
                DATASET_ID,
                parse_instagram_reel_url("https://instagram.com/reel/abc/"),
            )
        )
    expected = (
        ProviderErrorCode.INSTAGRAM_UNAVAILABLE
        if isinstance(items, list) and len(items) == 1 and items[0].get("error")
        else ProviderErrorCode.PROVIDER_INVALID_RESPONSE
    )
    assert exc_info.value.code is expected
    assert "sensitive" not in str(exc_info.value)


def test_profile_dataset_requires_matching_public_owner_and_allowlists_direct_links():
    def handler(request: httpx.Request):
        assert parse_qs(request.url.query.decode())["fields"] == [
            "username,url,externalUrl,externalUrls,private,error,errorDescription"
        ]
        return _json_response(
            [
                {
                    "username": "Tasty",
                    "url": "https://instagram.com/tasty/",
                    "externalUrl": "https://tasty.co/",
                    "externalUrls": [
                        {"url": "https://linktr.ee/tasty", "title": "recipes"},
                        {"url": "https://tasty.co/recipes"},
                        {"url": "http://plain-http-bio-link.example/tasty"},
                    ],
                    "private": False,
                    "biography": "must be ignored",
                }
            ]
        )

    result = asyncio.run(_client(handler).get_profile_result(DATASET_ID, "tasty"))
    assert result.username == "Tasty"
    # A real-world mixed-scheme bio link list: the plain-http entry is
    # silently dropped rather than failing the whole profile.
    assert result.external_urls == (
        "https://tasty.co/",
        "https://linktr.ee/tasty",
        "https://tasty.co/recipes",
    )


@pytest.mark.parametrize(
    "item",
    [
        {"username": "other", "externalUrl": "https://example.com", "private": False},
        {"username": "tasty", "externalUrl": "https://example.com", "private": True},
        {"username": "tasty", "externalUrl": 3, "private": False},
        {"username": "tasty", "error": "gone", "private": False},
    ],
)
def test_profile_adapter_rejects_identity_privacy_and_error_rows(item):
    with pytest.raises(ApifyProviderError) as exc_info:
        asyncio.run(
            _client(lambda _request: _json_response([item])).get_profile_result(
                DATASET_ID, "tasty"
            )
        )
    expected = (
        ProviderErrorCode.INSTAGRAM_UNAVAILABLE
        if item.get("private") is True or item.get("error") is not None
        else ProviderErrorCode.PROVIDER_INVALID_RESPONSE
    )
    assert exc_info.value.code is expected


def test_profile_adapter_filters_non_https_links_instead_of_failing():
    # A real bio can be entirely non-HTTPS links; that is unusable for the
    # HTTPS-only downstream fetch but is not itself a malformed response.
    item = {
        "username": "tasty",
        "externalUrl": "http://example.com",
        "externalUrls": [{"url": "http://also-plain.example"}],
        "private": False,
    }

    result = asyncio.run(
        _client(lambda _request: _json_response([item])).get_profile_result(
            DATASET_ID, "tasty"
        )
    )

    assert result.username == "tasty"
    assert result.external_urls == ()


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (400, ProviderErrorCode.PROVIDER_INVALID_RESPONSE),
        (401, ProviderErrorCode.PROVIDER_UNAVAILABLE),
        (403, ProviderErrorCode.PROVIDER_UNAVAILABLE),
        (404, ProviderErrorCode.PROVIDER_UNAVAILABLE),
        (408, ProviderErrorCode.PROVIDER_TIMEOUT),
        (429, ProviderErrorCode.PROVIDER_UNAVAILABLE),
        (500, ProviderErrorCode.PROVIDER_UNAVAILABLE),
    ],
)
def test_http_errors_are_stable_and_sanitized(status, expected_code):
    sensitive = "caption token profile-link"

    with pytest.raises(ApifyProviderError) as exc_info:
        asyncio.run(
            _client(lambda _request: _json_response({"error": sensitive}, status)).get_run(
                RUN_ID
            )
        )
    assert exc_info.value.code is expected_code
    assert sensitive not in str(exc_info.value)


def test_timeout_redirect_non_json_and_oversize_responses_fail_closed():
    cases = [
        (
            lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("secret", request=request)),
            ProviderErrorCode.PROVIDER_TIMEOUT,
        ),
        (
            lambda _request: httpx.Response(302, headers={"location": "https://evil.example"}),
            ProviderErrorCode.PROVIDER_INVALID_RESPONSE,
        ),
        (
            lambda _request: httpx.Response(200, text="{}", headers={"content-type": "text/html"}),
            ProviderErrorCode.PROVIDER_INVALID_RESPONSE,
        ),
        (
            lambda _request: httpx.Response(
                200,
                content=b'"' + (b"x" * (256 * 1024)) + b'"',
                headers={"content-type": "application/json"},
            ),
            ProviderErrorCode.PROVIDER_INVALID_RESPONSE,
        ),
    ]

    for handler, expected_code in cases:
        with pytest.raises(ApifyProviderError) as exc_info:
            asyncio.run(_client(handler).get_run(RUN_ID))
        assert exc_info.value.code is expected_code


def test_start_response_required_field_drift_fails_visibly_without_retry():
    starts = 0

    def handler(request: httpx.Request):
        nonlocal starts
        if response := _preflight_response(request):
            return response
        starts += 1
        return _json_response({"data": {"status": "READY"}}, 201)

    with pytest.raises(ApifyProviderError) as exc_info:
        asyncio.run(
            _client(handler).start_reel(
                parse_instagram_reel_url("https://instagram.com/reel/abc/")
            )
        )
    assert exc_info.value.code is ProviderErrorCode.PROVIDER_INVALID_RESPONSE
    assert starts == 1
