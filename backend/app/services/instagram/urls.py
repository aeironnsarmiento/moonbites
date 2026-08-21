from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit


INSTAGRAM_HOSTS = frozenset(
    {"instagram.com", "www.instagram.com", "m.instagram.com"}
)
_SHORTCODE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class InstagramUrlError(ValueError):
    """The URL belongs to Instagram but is not an eligible public Reel URL."""


@dataclass(frozen=True)
class InstagramReelIdentity:
    shortcode: str
    canonical_url: str


def is_instagram_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return parsed.hostname is not None and parsed.hostname.casefold() in INSTAGRAM_HOSTS
    except (TypeError, ValueError):
        return False


def parse_instagram_reel_url(url: str) -> InstagramReelIdentity:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise InstagramUrlError("Invalid Instagram Reel URL.") from exc

    host = parsed.hostname.casefold() if parsed.hostname else ""
    if (
        parsed.scheme.casefold() != "https"
        or host not in INSTAGRAM_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
    ):
        raise InstagramUrlError("Only public HTTPS Instagram Reel URLs are supported.")

    segments = parsed.path.split("/")
    if len(segments) == 4 and segments[-1] == "":
        segments = segments[:-1]
    if len(segments) != 3 or segments[0] != "" or segments[1] != "reel":
        raise InstagramUrlError("Only public Instagram Reel URLs are supported.")

    shortcode = segments[2]
    if unquote(shortcode) != shortcode or not _SHORTCODE_RE.fullmatch(shortcode):
        raise InstagramUrlError("The Instagram Reel shortcode is invalid.")

    return InstagramReelIdentity(
        shortcode=shortcode,
        canonical_url=f"https://www.instagram.com/reel/{shortcode}/",
    )
