from __future__ import annotations

import re
from urllib.parse import urlparse


URL_PATTERN = re.compile(r"https?://[^\s<>\]\)\"']+")

SKIP_HOST_PARTS = {
    "youtube.",
    "youtu.be",
    "instagram.",
    "tiktok.",
    "facebook.",
    "fb.",
    "amazon.",
    "amzn.",
    "twitter.",
    "x.com",
    "pinterest.",
}


def _is_skipped_host(hostname: str) -> bool:
    return any(part in hostname for part in SKIP_HOST_PARTS)


def extract_ranked_recipe_urls(text: str) -> list[str]:
    scored_urls: list[tuple[int, int, str]] = []
    seen: set[str] = set()

    for line_number, line in enumerate(text.splitlines()):
        for match in URL_PATTERN.finditer(line):
            url = match.group(0).rstrip(".,;:!?)")
            parsed = urlparse(url)
            hostname = (parsed.hostname or "").casefold()
            if not hostname or _is_skipped_host(hostname) or url in seen:
                continue

            score = 0
            line_key = line.casefold()
            if "full recipe" in line_key or "recipe here" in line_key:
                score += 5
            if "recipe" in line_key:
                score += 3
            if any(word in hostname for word in ("recipe", "cook", "food", "kitchen")):
                score += 1

            seen.add(url)
            scored_urls.append((score, line_number, url))

    return [url for _, _, url in sorted(scored_urls, key=lambda item: (-item[0], item[1]))]
