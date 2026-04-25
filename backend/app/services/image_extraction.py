from typing import Any, Optional

from bs4 import BeautifulSoup


def _has_recipe_type(value: Any) -> bool:
    if isinstance(value, str):
        return value == "Recipe"

    if isinstance(value, list):
        return "Recipe" in value

    return False


def _extract_image_value(image: Any) -> Optional[str]:
    if isinstance(image, str) and image:
        return image

    if isinstance(image, list):
        for item in image:
            extracted = _extract_image_value(item)
            if extracted is not None:
                return extracted

    if isinstance(image, dict) and isinstance(image.get("url"), str):
        return image["url"]

    return None


def _from_jsonld(jsonld_blocks: list[Any]) -> Optional[str]:
    for block in jsonld_blocks or []:
        if not isinstance(block, dict):
            continue

        if not _has_recipe_type(block.get("@type")):
            continue

        image_url = _extract_image_value(block.get("image"))
        if image_url is not None:
            return image_url

    return None


def _from_meta(html: str) -> Optional[str]:
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        return str(og["content"])

    twitter = soup.find("meta", attrs={"name": "twitter:image"})
    if twitter and twitter.get("content"):
        return str(twitter["content"])

    return None


def extract_image_url(html: str, jsonld_blocks: list[Any]) -> Optional[str]:
    """Pick the best hero image URL from JSON-LD Recipe nodes or HTML meta tags."""
    return _from_jsonld(jsonld_blocks) or _from_meta(html)
