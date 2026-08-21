from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx


class PublicWebError(RuntimeError):
    """A safe-fetch policy violation, or the public resource is unavailable."""


MAX_REDIRECTS = 5
_CHUNK_SIZE = 64 * 1024
_NUMERIC_LITERAL_RE = re.compile(r"^(0[xX][0-9a-fA-F]+|[0-9]+)$")

Resolver = Callable[[str, int], Awaitable[list[str]]]


@dataclass(frozen=True)
class FetchPolicy:
    name: str
    allowed_content_types: frozenset[str]
    max_bytes: int


HTML_POLICY = FetchPolicy(
    name="html",
    allowed_content_types=frozenset({"text/html", "application/xhtml+xml"}),
    max_bytes=2 * 1024 * 1024,
)

IMAGE_POLICY = FetchPolicy(
    name="image",
    allowed_content_types=frozenset(
        {"image/jpeg", "image/png", "image/webp", "image/avif"}
    ),
    max_bytes=5 * 1024 * 1024,
)


@dataclass(frozen=True)
class SafeFetchResult:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes


async def _default_resolve(host: str, port: int) -> list[str]:
    loop = asyncio.get_event_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, OSError) as exc:
        raise PublicWebError("The hostname could not be resolved.") from exc
    return [info[4][0] for info in infos]


def _looks_like_numeric_ip_literal(host: str) -> bool:
    if _NUMERIC_LITERAL_RE.fullmatch(host):
        return True
    labels = host.split(".")
    return len(labels) == 4 and all(
        _NUMERIC_LITERAL_RE.fullmatch(label) or re.fullmatch(r"0[0-7]*", label)
        for label in labels
    )


def _is_global_address(raw: str) -> bool:
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


async def _resolve_validated_address(
    host: str, port: int, resolver: Resolver
) -> str:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not _is_global_address(host):
            raise PublicWebError("The target address is not publicly routable.")
        return host

    if host.casefold() == "localhost" or host.casefold().endswith(".localhost"):
        raise PublicWebError("Localhost is not a publicly routable target.")

    if _looks_like_numeric_ip_literal(host):
        raise PublicWebError("Non-canonical numeric host literals are rejected.")

    try:
        addresses = await resolver(host, port)
    except PublicWebError:
        raise
    except OSError as exc:
        raise PublicWebError("The hostname could not be resolved.") from exc
    if not addresses:
        raise PublicWebError("The hostname did not resolve to any address.")
    for address in addresses:
        if not _is_global_address(address):
            raise PublicWebError("The target address is not publicly routable.")
    return addresses[0]


def _validate_absolute_https_url(url: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise PublicWebError("Only absolute HTTPS URLs are supported.") from exc

    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or (port is not None and port != 443)
    ):
        raise PublicWebError("Only absolute HTTPS URLs are supported.")

    return parsed.hostname, url


def _pin_address(url: str, address: str) -> str:
    parsed = urlsplit(url)
    netloc = f"[{address}]" if ":" in address else address
    return urlunsplit(
        (parsed.scheme, netloc, parsed.path or "/", parsed.query, "")
    )


async def safe_fetch(
    url: str,
    policy: FetchPolicy,
    *,
    deadline_seconds: float,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    resolver: Resolver = _default_resolve,
) -> SafeFetchResult:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + deadline_seconds
    requested_url = url
    current_url = url

    for _hop in range(MAX_REDIRECTS + 1):
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise PublicWebError("The request deadline elapsed.")

        original_host, current_url = _validate_absolute_https_url(current_url)
        address = await _resolve_validated_address(original_host, 443, resolver)
        pinned_url = _pin_address(current_url, address)

        try:
            async with httpx.AsyncClient(
                transport=transport,
                follow_redirects=False,
                timeout=httpx.Timeout(remaining),
                trust_env=False,
            ) as client:
                request = client.build_request(
                    "GET",
                    pinned_url,
                    headers={"Host": original_host},
                    extensions={"sni_hostname": original_host},
                )
                response = await client.send(request, stream=True)
                try:
                    if 300 <= response.status_code < 400:
                        location = response.headers.get("location")
                        if not location:
                            raise PublicWebError("Redirect had no location.")
                        current_url = urljoin(current_url, location)
                        continue

                    content_type = (
                        response.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .casefold()
                    )
                    if content_type not in policy.allowed_content_types:
                        raise PublicWebError("Unexpected response content type.")

                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            if int(content_length) > policy.max_bytes:
                                raise PublicWebError("Response exceeded the size cap.")
                        except ValueError as exc:
                            raise PublicWebError(
                                "Invalid content-length header."
                            ) from exc

                    body = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=_CHUNK_SIZE):
                        if len(body) + len(chunk) > policy.max_bytes:
                            raise PublicWebError("Response exceeded the size cap.")
                        body.extend(chunk)

                    return SafeFetchResult(
                        requested_url=requested_url,
                        final_url=current_url,
                        status_code=response.status_code,
                        content_type=content_type,
                        body=bytes(body),
                    )
                finally:
                    await response.aclose()
        except PublicWebError:
            raise
        except httpx.TimeoutException as exc:
            raise PublicWebError("The request timed out.") from exc
        except httpx.HTTPError as exc:
            raise PublicWebError("The target site is unavailable.") from exc

    raise PublicWebError("Too many redirects.")
