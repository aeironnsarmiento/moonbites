import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import HTTPException


MALFORMED_URL_DETAIL = "Enter a public http(s) URL"
PRIVATE_URL_DETAIL = "Private or localhost URLs are not supported"


def _malformed_url_error() -> HTTPException:
    return HTTPException(status_code=400, detail=MALFORMED_URL_DETAIL)


def _private_url_error() -> HTTPException:
    return HTTPException(status_code=400, detail=PRIVATE_URL_DETAIL)


def _is_blocked_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False

    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
    )


def _is_localhost(hostname: str) -> bool:
    normalized = hostname.rstrip(".").casefold()
    return normalized == "localhost" or normalized.endswith(".localhost")


def _resolved_ips(hostname: str) -> set[str]:
    try:
        return {
            info[4][0]
            for info in socket.getaddrinfo(hostname, None)
            if len(info) >= 5 and info[4]
        }
    except socket.gaierror:
        return set()


def validate_public_http_url(url: str) -> str:
    normalized = url.strip()

    try:
        parsed = urlparse(normalized)
        hostname = parsed.hostname
        parsed.port
    except ValueError as error:
        raise _malformed_url_error() from error

    if parsed.scheme not in {"http", "https"} or not hostname:
        raise _malformed_url_error()

    if _is_localhost(hostname) or _is_blocked_ip(hostname):
        raise _private_url_error()

    if any(_is_blocked_ip(ip) for ip in _resolved_ips(hostname)):
        raise _private_url_error()

    return normalized


def assert_public_peer(response: object) -> None:
    extensions = getattr(response, "extensions", None)
    if not extensions:
        return
    stream = extensions.get("network_stream") if isinstance(extensions, dict) else None
    if stream is None:
        return
    try:
        info = stream.get_extra_info("server_addr")
    except Exception:
        return
    if not info:
        return
    peer_ip = info[0]
    if _is_blocked_ip(peer_ip):
        raise _private_url_error()
