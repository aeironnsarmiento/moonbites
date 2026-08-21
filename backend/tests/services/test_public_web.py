from __future__ import annotations

import asyncio

import httpx
import pytest

from app.services.public_web import (
    HTML_POLICY,
    IMAGE_POLICY,
    PublicWebError,
    safe_fetch,
)


def _resolver(mapping):
    calls = []

    async def resolve(host, port):
        calls.append(host)
        addresses = mapping[host]
        if isinstance(addresses, Exception):
            raise addresses
        return list(addresses)

    resolve.calls = calls
    return resolve


def _html_response(body=b"<html></html>", status=200, headers=None):
    return httpx.Response(
        status,
        content=body,
        headers={"content-type": "text/html; charset=utf-8", **(headers or {})},
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/",
        "https://user:pass@example.com/",
        "https://example.com:8443/",
        "https://localhost/",
        "https://2130706433/",
        "https://0x7f000001/",
        "https://017700000001/",
        "https://127.0.0.1/",
        "https://[::1]/",
        "https://[::ffff:8.8.8.8]/",
        "https://[fe80::1]/",
        "https://[ff02::1]/",
        "not a url",
    ],
)
def test_safe_fetch_rejects_disallowed_url_forms(url):
    def handler(_request):
        raise AssertionError("network must not be reached")

    with pytest.raises(PublicWebError):
        asyncio.run(
            safe_fetch(
                url,
                HTML_POLICY,
                deadline_seconds=5,
                transport=httpx.MockTransport(handler),
                resolver=_resolver({}),
            )
        )


def test_safe_fetch_rejects_mixed_public_and_private_dns_answers():
    resolver = _resolver({"blog.example": ["93.184.216.34", "10.0.0.5"]})

    def handler(_request):
        raise AssertionError("network must not be reached")

    with pytest.raises(PublicWebError):
        asyncio.run(
            safe_fetch(
                "https://blog.example/recipe",
                HTML_POLICY,
                deadline_seconds=5,
                transport=httpx.MockTransport(handler),
                resolver=resolver,
            )
        )


def test_safe_fetch_resolves_once_and_pins_the_validated_address():
    resolver = _resolver({"blog.example": ["93.184.216.34"]})

    def handler(request: httpx.Request):
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "blog.example"
        assert request.extensions.get("sni_hostname") == "blog.example"
        # A realistic browser identity, not httpx's default: some sites'
        # baseline bot-protection silently serves a stub page to an
        # unidentified client rather than an error.
        assert "python-httpx" not in request.headers.get("user-agent", "")
        assert request.headers.get("user-agent")
        assert request.headers.get("accept")
        return _html_response()

    result = asyncio.run(
        safe_fetch(
            "https://blog.example/recipe",
            HTML_POLICY,
            deadline_seconds=5,
            transport=httpx.MockTransport(handler),
            resolver=resolver,
        )
    )

    assert result.final_url == "https://blog.example/recipe"
    assert result.status_code == 200
    assert resolver.calls == ["blog.example"]


def test_safe_fetch_follows_safe_public_redirect_and_revalidates_each_hop():
    resolver = _resolver(
        {
            "blog.example": ["93.184.216.34"],
            "cdn.example": ["93.184.216.35"],
        }
    )
    hops = []

    def handler(request: httpx.Request):
        hops.append(request.headers["host"])
        if request.headers["host"] == "blog.example":
            return httpx.Response(302, headers={"location": "https://cdn.example/final"})
        assert request.url.host == "93.184.216.35"
        return _html_response()

    result = asyncio.run(
        safe_fetch(
            "https://blog.example/start",
            HTML_POLICY,
            deadline_seconds=5,
            transport=httpx.MockTransport(handler),
            resolver=resolver,
        )
    )

    assert hops == ["blog.example", "cdn.example"]
    assert result.final_url == "https://cdn.example/final"


def test_safe_fetch_rejects_unsafe_redirect_target():
    resolver = _resolver({"blog.example": ["93.184.216.34"]})

    def handler(request: httpx.Request):
        return httpx.Response(302, headers={"location": "http://internal.example/"})

    with pytest.raises(PublicWebError):
        asyncio.run(
            safe_fetch(
                "https://blog.example/start",
                HTML_POLICY,
                deadline_seconds=5,
                transport=httpx.MockTransport(handler),
                resolver=resolver,
            )
        )


def test_safe_fetch_rejects_too_many_redirects():
    resolver = _resolver({f"hop{i}.example": ["93.184.216.34"] for i in range(10)})

    def handler(request: httpx.Request):
        host = request.headers["host"]
        index = int(host[len("hop"):-len(".example")])
        return httpx.Response(
            302, headers={"location": f"https://hop{index + 1}.example/"}
        )

    with pytest.raises(PublicWebError):
        asyncio.run(
            safe_fetch(
                "https://hop0.example/",
                HTML_POLICY,
                deadline_seconds=5,
                transport=httpx.MockTransport(handler),
                resolver=resolver,
            )
        )


def test_safe_fetch_rejects_wrong_content_type():
    resolver = _resolver({"blog.example": ["93.184.216.34"]})

    def handler(_request):
        return httpx.Response(
            200, content=b"{}", headers={"content-type": "application/json"}
        )

    with pytest.raises(PublicWebError):
        asyncio.run(
            safe_fetch(
                "https://blog.example/",
                HTML_POLICY,
                deadline_seconds=5,
                transport=httpx.MockTransport(handler),
                resolver=resolver,
            )
        )


def test_safe_fetch_rejects_oversized_html_body():
    resolver = _resolver({"blog.example": ["93.184.216.34"]})

    def handler(_request):
        return _html_response(body=b"x" * (HTML_POLICY.max_bytes + 1))

    with pytest.raises(PublicWebError):
        asyncio.run(
            safe_fetch(
                "https://blog.example/",
                HTML_POLICY,
                deadline_seconds=5,
                transport=httpx.MockTransport(handler),
                resolver=resolver,
            )
        )


def test_safe_fetch_rejects_oversized_image_body():
    resolver = _resolver({"cdn.example": ["93.184.216.34"]})

    def handler(_request):
        return httpx.Response(
            200,
            content=b"x" * (IMAGE_POLICY.max_bytes + 1),
            headers={"content-type": "image/jpeg"},
        )

    with pytest.raises(PublicWebError):
        asyncio.run(
            safe_fetch(
                "https://cdn.example/thumb.jpg",
                IMAGE_POLICY,
                deadline_seconds=5,
                transport=httpx.MockTransport(handler),
                resolver=resolver,
            )
        )


def test_safe_fetch_allows_image_policy_content_types():
    resolver = _resolver({"cdn.example": ["93.184.216.34"]})

    def handler(_request):
        return httpx.Response(
            200, content=b"binary", headers={"content-type": "image/webp"}
        )

    result = asyncio.run(
        safe_fetch(
            "https://cdn.example/thumb.webp",
            IMAGE_POLICY,
            deadline_seconds=5,
            transport=httpx.MockTransport(handler),
            resolver=resolver,
        )
    )
    assert result.content_type == "image/webp"
    assert result.body == b"binary"


def test_safe_fetch_respects_absolute_deadline_across_hops():
    resolver = _resolver({"blog.example": ["93.184.216.34"]})

    def handler(_request):
        raise AssertionError("network must not be reached")

    with pytest.raises(PublicWebError):
        asyncio.run(
            safe_fetch(
                "https://blog.example/",
                HTML_POLICY,
                deadline_seconds=0,
                transport=httpx.MockTransport(handler),
                resolver=resolver,
            )
        )


def test_safe_fetch_fails_closed_on_dns_failure():
    resolver = _resolver({"blog.example": OSError("dns down")})

    def handler(_request):
        raise AssertionError("network must not be reached")

    with pytest.raises(PublicWebError):
        asyncio.run(
            safe_fetch(
                "https://blog.example/",
                HTML_POLICY,
                deadline_seconds=5,
                transport=httpx.MockTransport(handler),
                resolver=resolver,
            )
        )


def test_safe_fetch_fails_closed_on_transport_error():
    resolver = _resolver({"blog.example": ["93.184.216.34"]})

    def handler(request: httpx.Request):
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(PublicWebError):
        asyncio.run(
            safe_fetch(
                "https://blog.example/",
                HTML_POLICY,
                deadline_seconds=5,
                transport=httpx.MockTransport(handler),
                resolver=resolver,
            )
        )
