"""Instagram-specific acquisition boundary."""

from .urls import (
    InstagramReelIdentity,
    InstagramUrlError,
    is_instagram_url,
    parse_instagram_reel_url,
)

__all__ = [
    "InstagramReelIdentity",
    "InstagramUrlError",
    "is_instagram_url",
    "parse_instagram_reel_url",
]
