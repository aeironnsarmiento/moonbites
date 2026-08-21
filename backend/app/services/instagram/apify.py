from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from ...core.config import Settings
from ..public_web import upgrade_to_https
from .models import (
    ApifyProviderError,
    ApifyProfileItem,
    ApifyReelItem,
    ApifyRun,
    ApifyRunData,
    ApifyRunStatus,
    InstagramProfileMetadata,
    InstagramReelMetadata,
    ProviderErrorCode,
)
from .urls import INSTAGRAM_HOSTS, InstagramReelIdentity, parse_instagram_reel_url


APIFY_ORIGIN = "https://api.apify.com"
MAX_RESPONSE_BYTES = 256 * 1024
REEL_ACTOR_ID = "xMc5Ga1oCONPmWJIa"
PROFILE_ACTOR_ID = "dSCLg0C3YEZ83HzYX"
REEL_ACTOR_BUILD = "0.0.542"
PROFILE_ACTOR_BUILD = "0.0.580"
REEL_MAX_CHARGE_USD = Decimal("0.0073")
PROFILE_MAX_CHARGE_USD = Decimal("0.0026")
FREE_MONTHLY_CREDITS_USD = Decimal("5")
FREE_ACCOUNT_MAX_USD = Decimal("5")
APPLICATION_USAGE_STOP_USD = Decimal("4.5")

REEL_FIELDS = (
    "shortCode,url,caption,displayUrl,ownerUsername,inputUrl,error,errorDescription"
)
PROFILE_FIELDS = (
    "username,url,externalUrl,externalUrls,private,error,errorDescription"
)

_OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9]{1,64}$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def _fail(code: ProviderErrorCode) -> None:
    raise ApifyProviderError(code)


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
    if not result.is_finite():
        _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
    return result


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
    return value


def _data(payload: Any) -> Mapping[str, Any]:
    return _mapping(_mapping(payload).get("data"))


def _opaque_id(value: Any) -> str:
    if not isinstance(value, str) or not _OPAQUE_ID_RE.fullmatch(value):
        _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
    return value


def _https_url(value: Any) -> str:
    if not isinstance(value, str):
        _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
    ):
        _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
    return value


def _content_url_matches(value: Any, identity: InstagramReelIdentity) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.hostname.casefold() not in INSTAGRAM_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
    ):
        return False
    parts = [part for part in parsed.path.split("/") if part]
    return len(parts) == 2 and parts[0] in {"p", "reel"} and parts[1] == identity.shortcode


def _query_number(value: Decimal) -> str:
    return format(value, "f")


class ApifyClient:
    """Minimal fail-closed adapter for the two pinned Instagram Actors."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        settings = self._settings
        valid = (
            isinstance(settings.instagram_apify_token, str)
            and bool(settings.instagram_apify_token.strip())
            and settings.instagram_reel_actor_id == REEL_ACTOR_ID
            and settings.instagram_profile_actor_id == PROFILE_ACTOR_ID
            and settings.instagram_reel_actor_build == REEL_ACTOR_BUILD
            and settings.instagram_profile_actor_build == PROFILE_ACTOR_BUILD
            and settings.instagram_reel_max_charge_usd is not None
            and settings.instagram_profile_max_charge_usd is not None
        )
        if not valid:
            _fail(ProviderErrorCode.PROVIDER_UNAVAILABLE)
        try:
            valid = (
                _decimal(settings.instagram_reel_max_charge_usd) == REEL_MAX_CHARGE_USD
                and _decimal(settings.instagram_profile_max_charge_usd)
                == PROFILE_MAX_CHARGE_USD
                and _decimal(settings.instagram_monthly_usage_stop_usd)
                == APPLICATION_USAGE_STOP_USD
                and 0 < settings.instagram_reel_actor_timeout_seconds <= 120
                and 0 < settings.instagram_profile_actor_timeout_seconds <= 120
                and 0 < settings.instagram_request_deadline_seconds <= 45
            )
        except (TypeError, ValueError, ApifyProviderError):
            valid = False
        if not valid:
            _fail(ProviderErrorCode.PROVIDER_UNAVAILABLE)

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
    ) -> Any:
        if not path.startswith("/v2/") or ".." in path or "?" in path:
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        url = f"{APIFY_ORIGIN}{path}"
        headers = {
            "Authorization": f"Bearer {self._settings.instagram_apify_token}",
            "Accept": "application/json",
        }
        timeout = httpx.Timeout(self._settings.instagram_request_deadline_seconds)
        try:
            async with httpx.AsyncClient(
                follow_redirects=False,
                timeout=timeout,
                transport=self._transport,
                trust_env=False,
            ) as client:
                async with client.stream(
                    method, url, params=params, json=body, headers=headers
                ) as response:
                    if 300 <= response.status_code < 400:
                        _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            if int(content_length) > MAX_RESPONSE_BYTES:
                                _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
                        except ValueError:
                            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
                    content = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                        if len(content) + len(chunk) > MAX_RESPONSE_BYTES:
                            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
                        content.extend(chunk)
                    status = response.status_code
                    content_type = response.headers.get("content-type", "")
        except ApifyProviderError:
            raise
        except httpx.TimeoutException:
            _fail(ProviderErrorCode.PROVIDER_TIMEOUT)
        except httpx.RequestError:
            _fail(ProviderErrorCode.PROVIDER_UNAVAILABLE)

        if status == 408:
            _fail(ProviderErrorCode.PROVIDER_TIMEOUT)
        if status == 400:
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        if status in {401, 403, 404, 409, 429} or status >= 500:
            _fail(ProviderErrorCode.PROVIDER_UNAVAILABLE)
        if not 200 <= status < 300:
            _fail(ProviderErrorCode.PROVIDER_UNAVAILABLE)
        if content_type.split(";", 1)[0].strip().casefold() != "application/json":
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        try:
            return json.loads(bytes(content))
        except (UnicodeDecodeError, json.JSONDecodeError):
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)

    async def preflight_spend(self) -> None:
        """Read-only spend guard. Issues three GETs and starts no Actor run.

        Exposed separately from `start_reel`/`start_profile` so a caller can
        run it *before* committing to the non-idempotent run-creating POST: a
        failure here provably charged nothing and left nothing in flight, so
        it must not be treated as an ambiguous external operation.
        """
        account = _data(await self._request_json("GET", "/v2/users/me"))
        plan = _mapping(account.get("plan"))
        if (
            plan.get("tier") != "FREE"
            or plan.get("isEnabled") is not True
            or account.get("isPaying") is not False
            or _decimal(plan.get("monthlyBasePriceUsd")) != 0
            or _decimal(plan.get("monthlyUsageCreditsUsd"))
            != FREE_MONTHLY_CREDITS_USD
            or _decimal(plan.get("maxMonthlyUsageUsd")) != FREE_ACCOUNT_MAX_USD
        ):
            _fail(ProviderErrorCode.PROVIDER_UNAVAILABLE)

        limit_data = _data(await self._request_json("GET", "/v2/users/me/limits"))
        limits = _mapping(limit_data.get("limits"))
        current = _mapping(limit_data.get("current"))
        if _decimal(limits.get("maxMonthlyUsageUsd")) != FREE_ACCOUNT_MAX_USD:
            _fail(ProviderErrorCode.PROVIDER_UNAVAILABLE)

        usage_data = _data(
            await self._request_json("GET", "/v2/users/me/usage/monthly")
        )
        current_usage = max(
            _decimal(current.get("monthlyUsageUsd")),
            _decimal(usage_data.get("totalUsageCreditsUsdAfterVolumeDiscount")),
        )
        if current_usage >= APPLICATION_USAGE_STOP_USD:
            _fail(ProviderErrorCode.PROVIDER_UNAVAILABLE)

    async def start_reel(
        self, identity: InstagramReelIdentity, *, preflighted: bool = False
    ) -> ApifyRun:
        if not preflighted:
            await self.preflight_spend()
        payload = await self._request_json(
            "POST",
            f"/v2/actors/{REEL_ACTOR_ID}/runs",
            params={
                "build": REEL_ACTOR_BUILD,
                "maxItems": 1,
                "maxTotalChargeUsd": _query_number(REEL_MAX_CHARGE_USD),
                "restartOnError": "false",
                "timeout": int(self._settings.instagram_reel_actor_timeout_seconds),
                "waitForFinish": 0,
            },
            body={
                "username": [identity.canonical_url],
                "includeSharesCount": False,
                "includeTranscript": False,
                "includeDownloadedVideo": False,
            },
        )
        return self._adapt_run(payload)

    async def start_profile(
        self, username: str, *, preflighted: bool = False
    ) -> ApifyRun:
        if not isinstance(username, str) or not _USERNAME_RE.fullmatch(username):
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        if not preflighted:
            await self.preflight_spend()
        payload = await self._request_json(
            "POST",
            f"/v2/actors/{PROFILE_ACTOR_ID}/runs",
            params={
                "build": PROFILE_ACTOR_BUILD,
                "maxItems": 1,
                "maxTotalChargeUsd": _query_number(PROFILE_MAX_CHARGE_USD),
                "restartOnError": "false",
                "timeout": int(self._settings.instagram_profile_actor_timeout_seconds),
                "waitForFinish": 0,
            },
            body={"usernames": [username], "includeAboutSection": False},
        )
        return self._adapt_run(payload)

    async def get_run(self, run_id: str) -> ApifyRun:
        run_id = _opaque_id(run_id)
        payload = await self._request_json("GET", f"/v2/actor-runs/{run_id}")
        run = self._adapt_run(payload)
        if run.run_id != run_id:
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        return run

    def _adapt_run(self, payload: Any) -> ApifyRun:
        try:
            data = ApifyRunData.model_validate(_data(payload))
        except ValidationError:
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        run_id = _opaque_id(data.run_id)
        try:
            status = ApifyRunStatus(data.status)
        except ValueError:
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        dataset_value = data.default_dataset_id
        dataset_id = None if dataset_value is None else _opaque_id(dataset_value)
        if status is ApifyRunStatus.SUCCEEDED and dataset_id is None:
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        return ApifyRun(
            run_id=run_id, status=status, default_dataset_id=dataset_id
        )

    async def _get_dataset(self, dataset_id: str, fields: str) -> list[Any]:
        dataset_id = _opaque_id(dataset_id)
        payload = await self._request_json(
            "GET",
            f"/v2/datasets/{dataset_id}/items",
            params={"clean": 1, "limit": 2, "fields": fields},
        )
        if not isinstance(payload, list) or len(payload) != 1:
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        return payload

    async def get_reel_result(
        self, dataset_id: str, identity: InstagramReelIdentity
    ) -> InstagramReelMetadata:
        item = _mapping((await self._get_dataset(dataset_id, REEL_FIELDS))[0])
        if item.get("error") is not None or item.get("errorDescription") is not None:
            _fail(ProviderErrorCode.INSTAGRAM_UNAVAILABLE)
        try:
            parsed_item = ApifyReelItem.model_validate(item)
        except ValidationError:
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        shortcode = parsed_item.short_code
        caption = parsed_item.caption
        owner = parsed_item.owner_username
        if (
            shortcode != identity.shortcode
            or not _content_url_matches(parsed_item.url, identity)
            or not _USERNAME_RE.fullmatch(owner)
        ):
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        input_url = parsed_item.input_url
        if input_url is not None:
            try:
                if parse_instagram_reel_url(input_url) != identity:
                    _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
            except ValueError:
                _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        return InstagramReelMetadata(
            shortcode=shortcode,
            canonical_url=identity.canonical_url,
            caption=caption,
            owner_username=owner,
            thumbnail_url=_https_url(parsed_item.display_url),
        )

    async def get_profile_result(
        self, dataset_id: str, expected_username: str
    ) -> InstagramProfileMetadata:
        if not isinstance(expected_username, str) or not _USERNAME_RE.fullmatch(
            expected_username
        ):
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        item = _mapping((await self._get_dataset(dataset_id, PROFILE_FIELDS))[0])
        if (
            item.get("error") is not None
            or item.get("errorDescription") is not None
            or item.get("private") is not False
        ):
            _fail(ProviderErrorCode.INSTAGRAM_UNAVAILABLE)
        try:
            parsed_item = ApifyProfileItem.model_validate(item)
        except ValidationError:
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)
        username = parsed_item.username
        if username.casefold() != expected_username.casefold():
            _fail(ProviderErrorCode.PROVIDER_INVALID_RESPONSE)

        raw_urls: list[str] = []
        if parsed_item.external_url is not None:
            raw_urls.append(parsed_item.external_url)
        raw_urls.extend(entry.url for entry in parsed_item.external_urls)

        # Real bios commonly carry a plain http:// link (frequently one that
        # itself redirects straight to https); those are upgraded rather
        # than dropped or treated as a malformed response, since the
        # downstream fetch is https-only regardless and this never issues an
        # actual cleartext request.
        urls: list[str] = []
        for raw_url in raw_urls:
            upgraded = upgrade_to_https(raw_url)
            if upgraded is not None and upgraded not in urls:
                urls.append(upgraded)
        return InstagramProfileMetadata(username=username, external_urls=tuple(urls))
