from __future__ import annotations

from hashlib import sha256
from json import dumps
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..schemas.extract import NormalizedRecipe, RecipeImportRecord

# Parameters known to be tracking noise, not part of a page's identity. Every
# other parameter is preserved -- a YouTube URL's identity lives in `?v=`, so
# dropping unrecognized query params would collapse distinct videos together.
TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "ref",
    "spm",
    "utm_campaign",
    "utm_content",
    "utm_id",
    "utm_medium",
    "utm_name",
    "utm_source",
    "utm_term",
}


def content_identity(recipe: NormalizedRecipe) -> str:
    """What makes two recipes the same dish, for storage purposes."""
    normalized_payload = {
        "cookTime": recipe.cookTime,
        "ingredients": recipe.ingredients,
        "instructions": recipe.instructions,
        "name": recipe.name.casefold(),
        "nutrition": recipe.nutrition,
        "recipeCuisine": recipe.recipeCuisine,
        "recipeYield": recipe.recipeYield,
    }
    serialized = dumps(normalized_payload, ensure_ascii=False, sort_keys=True)
    return sha256(serialized.encode("utf-8")).hexdigest()


def dedupe_by_content(recipes: list[NormalizedRecipe]) -> list[NormalizedRecipe]:
    seen: set[str] = set()
    unique_recipes: list[NormalizedRecipe] = []

    for recipe in recipes:
        identity = content_identity(recipe)
        if identity in seen:
            continue
        seen.add(identity)
        unique_recipes.append(recipe)

    return unique_recipes


def source_identity(url: str) -> str:
    """What makes two recipe imports the same source."""
    parsed = urlsplit(url.strip())

    hostname = (parsed.hostname or "").lower()
    scheme = parsed.scheme.lower()
    path = parsed.path or "/"

    if path != "/":
        path = path.rstrip("/") or "/"

    include_port = parsed.port and not (
        (scheme == "http" and parsed.port == 80)
        or (scheme == "https" and parsed.port == 443)
    )
    netloc = f"{hostname}:{parsed.port}" if include_port else hostname

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key.lower() not in TRACKING_QUERY_PARAMS
    ]
    query = urlencode(sorted(query_pairs))

    return urlunsplit((scheme, netloc, path, query, ""))


def _source_identity_keys(record: RecipeImportRecord) -> set[str]:
    return {
        source_identity(record.submitted_url),
        source_identity(record.final_url),
    }


def dedupe_by_source(
    records: list[RecipeImportRecord],
) -> list[RecipeImportRecord]:
    seen: set[str] = set()
    unique_records: list[RecipeImportRecord] = []

    for record in records:
        keys = _source_identity_keys(record)
        if seen.intersection(keys):
            continue
        seen.update(keys)
        unique_records.append(record)

    return unique_records
