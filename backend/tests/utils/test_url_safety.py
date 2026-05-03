from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.utils.url_safety import validate_public_http_url


def _addrinfo_for(ip: str):
    return [(None, None, None, "", (ip, 443))]


def test_validate_public_http_url_allows_public_url():
    with patch(
        "app.utils.url_safety.socket.getaddrinfo",
        return_value=_addrinfo_for("93.184.216.34"),
    ):
        assert (
            validate_public_http_url("https://example.com/recipe")
            == "https://example.com/recipe"
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost",
        "http://127.0.0.1",
    ],
)
def test_validate_public_http_url_rejects_localhost_and_loopback(url):
    with pytest.raises(HTTPException) as error:
        validate_public_http_url(url)

    assert error.value.status_code == 400
    assert error.value.detail == "Private or localhost URLs are not supported"


def test_validate_public_http_url_rejects_non_http_scheme():
    with pytest.raises(HTTPException) as error:
        validate_public_http_url("file://x")

    assert error.value.status_code == 400
    assert error.value.detail == "Enter a public http(s) URL"


def test_validate_public_http_url_rejects_host_resolving_to_private_ip():
    with patch(
        "app.utils.url_safety.socket.getaddrinfo",
        return_value=_addrinfo_for("10.0.0.5"),
    ):
        with pytest.raises(HTTPException) as error:
            validate_public_http_url("https://private.example/recipe")

    assert error.value.status_code == 400
    assert error.value.detail == "Private or localhost URLs are not supported"
