"""Deciding whether a candidate page is the dish a social post named.

Sole owner of the confident-match rule behind **Linked Recipe**: a candidate is
accepted only when it is the *one* page whose title names the same dish. Two
plausible candidates are no match at all.

Both the caption-link path (``social/caption_recipe.py``) and **Creator-site
Lookup** (``instagram/creator_site_lookup.py``) match through this module, so
the rule has one implementation and one test corpus.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from .extraction_types import ExtractionResult


_GENERIC_TITLE_TOKENS = frozenset(
    {
        "recipe",
        "recipes",
        "easy",
        "quick",
        "best",
        "homemade",
        "classic",
        "the",
        "a",
        "an",
        "simple",
        "delicious",
        "perfect",
        "healthy",
    }
)

_TIME_QUALIFIER_UNITS = frozenset(
    {
        "minute",
        "minutes",
        "min",
        "mins",
        "hour",
        "hours",
        "hr",
        "hrs",
        "second",
        "seconds",
        "ingredient",
        "ingredients",
    }
)

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def hostname(url: str) -> Optional[str]:
    try:
        return urlsplit(url).hostname
    except ValueError:
        return None


def canonicalize_candidate_url(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), host, path, "", ""))


def normalize_dish_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = stripped.casefold()
    no_punct = _PUNCT_RE.sub(" ", lowered)

    raw = no_punct.split()
    tokens: list[str] = []
    index = 0
    while index < len(raw):
        token = raw[index]
        # "15 Minute", "5 Ingredient": a prep-time or count qualifier the site
        # adds, never part of the dish. The numeral is dropped only alongside
        # its unit, because a bare numeral can itself name the dish and must
        # stay distinguishing ("7 Layer Dip" is not "5 Layer Dip").
        if (
            token.isdigit()
            and index + 1 < len(raw)
            and raw[index + 1] in _TIME_QUALIFIER_UNITS
        ):
            index += 2
            continue
        if token in _TIME_QUALIFIER_UNITS:
            index += 1
            continue
        if token not in _GENERIC_TITLE_TOKENS:
            tokens.append(token)
        index += 1
    return " ".join(tokens)


def _site_brand_label(domain: Optional[str]) -> Optional[str]:
    if not domain:
        return None
    host = domain.casefold()
    if host.startswith("www."):
        host = host[len("www."):]
    return host.split(".")[0] or None


def strip_site_brand(normalized_title: str, domain: Optional[str]) -> str:
    """Drop a trailing "by <brand>" naming the site the page was served from.

    Sites sign their own titles ("... Recipe by Tasty"), which the post never
    does. Only the fetched host's own label is removed, so a dish word can
    never be stripped by accident.
    """
    label = _site_brand_label(domain)
    if not label:
        return normalized_title

    tokens = normalized_title.split()

    # The label has no word boundaries ("smittenkitchen"), but a multi-word
    # brand signs its title as separate tokens ("Smitten Kitchen"). Walk
    # backward accumulating a trailing run of tokens until its concatenation
    # matches the label, rather than requiring a single trailing token to
    # match it whole.
    end = len(tokens)
    joined = ""
    while end > 0:
        end -= 1
        joined = tokens[end] + joined
        if joined == label:
            tokens = tokens[:end]
            if tokens and tokens[-1] == "by":
                tokens.pop()
            break
        if len(joined) > len(label):
            break
    return " ".join(tokens)


def is_matching_title(
    candidate_title: str, dish_name: str, *, site_domain: Optional[str] = None
) -> bool:
    candidate_norm = strip_site_brand(normalize_dish_name(candidate_title), site_domain)
    dish_norm = normalize_dish_name(dish_name)
    if not dish_norm or not candidate_norm:
        return False
    if candidate_norm == dish_norm:
        return True

    dish_tokens = dish_norm.split()
    if len(dish_tokens) < 2:
        return False

    # Order-independent match only: any additional or missing substantive
    # (non-generic) token is treated as a distinct dish, favoring precision.
    return set(candidate_norm.split()) == set(dish_tokens)


@dataclass(frozen=True)
class RecipeCandidate:
    canonical_url: str
    title: str
    result: ExtractionResult


def select_unique_match(
    candidates: list[RecipeCandidate], dish_name: str
) -> Optional[RecipeCandidate]:
    deduped: dict[tuple[str, str], RecipeCandidate] = {}
    for candidate in candidates:
        host = hostname(candidate.canonical_url)
        key = (
            canonicalize_candidate_url(candidate.canonical_url),
            strip_site_brand(normalize_dish_name(candidate.title), host),
        )
        deduped.setdefault(key, candidate)

    matches = [
        candidate
        for candidate in deduped.values()
        if is_matching_title(
            candidate.title,
            dish_name,
            site_domain=hostname(candidate.canonical_url),
        )
    ]
    if len(matches) != 1:
        return None
    return matches[0]
