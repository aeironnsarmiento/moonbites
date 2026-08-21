import pytest

from app.services.instagram.urls import (
    InstagramUrlError,
    is_instagram_url,
    parse_instagram_reel_url,
)


@pytest.mark.parametrize(
    ("url", "shortcode"),
    [
        ("https://www.instagram.com/reel/DZuzc9PNedT/", "DZuzc9PNedT"),
        (
            "https://instagram.com/reel/DcMelrnkfZe?igsh=private#ignored",
            "DcMelrnkfZe",
        ),
        ("https://m.instagram.com/reel/Daa0ZKGOuZb/", "Daa0ZKGOuZb"),
    ],
)
def test_parse_reel_url_canonicalizes_supported_urls(url, shortcode):
    identity = parse_instagram_reel_url(url)

    assert identity.shortcode == shortcode
    assert identity.canonical_url == f"https://www.instagram.com/reel/{shortcode}/"


@pytest.mark.parametrize(
    "url",
    [
        "http://www.instagram.com/reel/DZuzc9PNedT/",
        "https://user@www.instagram.com/reel/DZuzc9PNedT/",
        "https://www.instagram.com:443/reel/DZuzc9PNedT/",
        "https://instagram.example/reel/DZuzc9PNedT/",
        "https://notinstagram.com/reel/DZuzc9PNedT/",
        "https://www.instagram.com/p/DZuzc9PNedT/",
        "https://www.instagram.com/stories/user/123/",
        "https://www.instagram.com/someprofile/",
        "https://www.instagram.com/reel/",
        "https://www.instagram.com/reel/bad%20code/",
        "https://www.instagram.com/reel/good/extra",
        "https://www.instagram.com/reel//",
    ],
)
def test_parse_reel_url_rejects_unsupported_or_ambiguous_identity(url):
    with pytest.raises(InstagramUrlError):
        parse_instagram_reel_url(url)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://instagram.com/p/abc/", True),
        ("https://www.instagram.com/a_profile/", True),
        ("https://m.instagram.com/stories/name/1", True),
        ("https://instagram.example/reel/abc/", False),
        ("https://notinstagram.com/reel/abc/", False),
        ("not a url", False),
    ],
)
def test_instagram_dispatch_recognizes_only_exact_supported_hosts(url, expected):
    assert is_instagram_url(url) is expected
