"""Deterministic half of the display-title feature.

Pure functions only — no Gemini import, no network — so the guards that decide
whether a generated title is trustworthy can be tested without mocking. This
sits beside ``services/gemini/title_generator.py`` the way ``normalizer.py``
sits beside ``gemini/recipe_parser.py``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Optional

from ..schemas.extract import NormalizedRecipe
from ..utils.text import clean_text


PLACEHOLDER_TITLE = "Untitled recipe"

MAX_TITLE_LENGTH = 60
MIN_TITLE_WORDS = 2
MAX_TITLE_WORDS = 8

# The prompt asks for R1's 3-8 words, but the gate floors at 2: "Chicken Adobo"
# is a correct title, and rejecting it would degrade to a worse raw source
# title. The gate catches garbage; it does not enforce the prompt's target.
# One-word titles ("Pasta") stay rejected as too vague.

MAX_SOURCE_RECIPES = 3
MAX_SOURCE_INGREDIENTS = 25

# Same tokenizer as the caption parser's fabrication guard, deliberately.
_TOKEN_PATTERN = re.compile(r"[a-z0-9]{3,}")

_STOPWORDS = frozenset({"and", "the", "for", "with"})

_NUMBER_WORDS = (
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
)

_SEPARATOR_PATTERN = re.compile(r"[|»·•—–]")
_DIGIT_RUN_PATTERN = re.compile(r"\d+")
_HASHTAG_OR_HANDLE_PATTERN = re.compile(r"[#@]\w+")

_EPISODE_PATTERN = re.compile(
    r"\b(?:ep|episode|pt|part|day|week)\.?\s*#?\d+\b",
    re.IGNORECASE,
)
_PLATFORM_PATTERNS = (
    re.compile(r"\bcooking with\s+[\w' ]+$", re.IGNORECASE),
    re.compile(r"\bon (?:tiktok|youtube|instagram)\b", re.IGNORECASE),
)
_PROMO_PATTERNS = (
    re.compile(r"\bthe (?:best|only|ultimate|easiest|greatest)\b", re.IGNORECASE),
    re.compile(r"\byou'?ll ever (?:make|need|eat|try)\b", re.IGNORECASE),
    re.compile(r"\bworld'?s\b", re.IGNORECASE),
    # Standalone hype, for titles that do not lead with "the".
    re.compile(
        r"\b(?:amazing|insane|viral|foolproof|must[- ]try|life[- ]changing|"
        r"incredible|unbelievable|epic|best|greatest|ultimate)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:in|under|ready in)\s*\d+\s*min(?:ute)?s?\b", re.IGNORECASE),
    re.compile(r"\brecipe\s*$", re.IGNORECASE),
)

# "Easy", "Vegan", "One-Pot", "Air Fryer" are useful qualifiers (R2) and are
# deliberately absent from _PROMO_PATTERNS.

_SITE_TAIL_PATTERN = re.compile(r"\s+-\s+(?:\S+\s+){0,3}\S+\s*$")


@dataclass(frozen=True)
class DisplayTitle:
    value: str
    source: str
    reason: Optional[str] = None


def _strip_symbols(value: str) -> str:
    """Drop emoji and pictographs while preserving accented letters."""
    return "".join(
        char for char in value if unicodedata.category(char) not in {"So", "Sk"}
    )


def _tokens(value: str) -> list[str]:
    return _TOKEN_PATTERN.findall(value.casefold())


def _word_count(value: str) -> int:
    return len(value.split())


def _pick_richest_segment(value: str) -> str:
    """Keep the segment with the most words.

    Taking the first segment breaks on inverted titles like
    "Bon Appetit | Creamy Garlic Pasta"; most-words handles both orders.
    """
    segments = [segment.strip() for segment in _SEPARATOR_PATTERN.split(value)]
    segments = [segment for segment in segments if segment]
    if not segments:
        return ""
    return max(segments, key=_word_count)


def _truncate_on_word_boundary(value: str, limit: int = MAX_TITLE_LENGTH) -> str:
    if len(value) <= limit:
        return value
    clipped = value[:limit]
    if " " in clipped:
        clipped = clipped[: clipped.rfind(" ")]
    return clipped.strip()


def clean_source_title(
    source_title: Optional[str],
    recipes: Optional[Iterable[NormalizedRecipe]] = None,
) -> str:
    """Best-effort deterministic cleanup of a raw source title (R9).

    Not reshaped to 3-8 words: R9 asks for "a cleaned version of the original
    source title", and truncating a legitimate long title loses meaning.
    """
    recipe_list = list(recipes or [])

    cleaned = clean_text(source_title) or ""
    if cleaned:
        cleaned = _pick_richest_segment(cleaned)
        cleaned = _strip_symbols(cleaned)
        cleaned = _HASHTAG_OR_HANDLE_PATTERN.sub(" ", cleaned)
        cleaned = _EPISODE_PATTERN.sub(" ", cleaned)
        for pattern in _PLATFORM_PATTERNS:
            cleaned = pattern.sub(" ", cleaned)
        for pattern in _PROMO_PATTERNS:
            cleaned = pattern.sub(" ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        # Only strip a trailing " - Site Name" when a real title precedes it.
        if _word_count(_SITE_TAIL_PATTERN.sub("", cleaned)) >= 3:
            cleaned = _SITE_TAIL_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = cleaned.strip(" -–—:;,.!?\"'()[]")
        cleaned = _truncate_on_word_boundary(cleaned)

    if cleaned:
        return cleaned

    if recipe_list:
        fallback_name = clean_text(recipe_list[0].name)
        if fallback_name:
            return _truncate_on_word_boundary(fallback_name)

    return PLACEHOLDER_TITLE


def build_title_source_text(
    source_title: Optional[str],
    recipes: Optional[Iterable[NormalizedRecipe]] = None,
) -> str:
    """The corpus a title must be grounded in.

    Used for BOTH the prompt and the attribution gate, so the model is never
    handed material the guard would then reject. Instructions and nutrition are
    excluded: they do not name the dish.
    """
    parts: list[str] = []
    if source_title:
        parts.append(source_title)

    for recipe in list(recipes or [])[:MAX_SOURCE_RECIPES]:
        parts.append(recipe.name)
        if recipe.recipeYield:
            parts.append(recipe.recipeYield)
        if recipe.recipeCuisine:
            parts.extend(recipe.recipeCuisine)
        parts.extend(recipe.ingredients[:MAX_SOURCE_INGREDIENTS])

    return "\n".join(part for part in parts if part)


def _attested_tokens(source_text: str) -> set[str]:
    attested = set(_tokens(source_text))

    # Numeral bridge: "3 easy weeknight dinners" must attest "Three" (AE6).
    # A blanket number-word allowlist would be wrong -- it would attest
    # "Three Dinners" against a source that says "5 dinners".
    for run in _DIGIT_RUN_PATTERN.findall(source_text):
        try:
            number = int(run)
        except ValueError:  # pragma: no cover - defensive
            continue
        if 1 <= number <= len(_NUMBER_WORDS):
            attested.add(_NUMBER_WORDS[number - 1])

    return attested


def _variants(token: str) -> set[str]:
    """Plural/singular variants, by membership rather than stemming.

    Suffix-folding would let "gla" match "glass"; an explicit variant set will
    not.
    """
    variants = {token, f"{token}s", f"{token}es"}
    if len(token) > 3:
        variants.add(token[:-1])
    if len(token) > 4:
        variants.add(token[:-2])
    return variants


def unsupported_tokens(source_text: str, title: str) -> list[str]:
    """Tokens in the title with no support in the source (R4).

    Every token must be attested. A ratio threshold -- the caption parser's
    0.3-per-line bar -- is the wrong instrument here: "Vegan Garlic Pasta"
    scores 0.67 and would sail through, which is exactly AE2's failure. Titles
    are short enough that all-tokens-attested is affordable.
    """
    attested = _attested_tokens(source_text)

    return [
        token
        for token in _tokens(title)
        if token not in _STOPWORDS and not (_variants(token) & attested)
    ]


def shape_violation(title: str) -> Optional[str]:
    """Why a candidate title is unusable, or None when it is fine (R1, R3)."""
    stripped = (title or "").strip()
    if not stripped:
        return "The generated title was empty."

    if len(stripped) > MAX_TITLE_LENGTH:
        return f"The generated title was longer than {MAX_TITLE_LENGTH} characters."

    words = _word_count(stripped)
    if words < MIN_TITLE_WORDS:
        return "The generated title was too vague."
    if words > MAX_TITLE_WORDS:
        return f"The generated title ran longer than {MAX_TITLE_WORDS} words."

    if stripped != _strip_symbols(stripped):
        return "The generated title contained emoji."

    if any(char in stripped for char in "#@|"):
        return "The generated title contained hashtags, handles, or separators."

    return None


def resolve_display_title(
    display_title: Optional[str],
    recipes: Optional[Iterable[NormalizedRecipe]] = None,
    page_title: Optional[str] = None,
) -> str:
    """The name a user should see, in precedence order.

    Mirrored in SQL (the display_title_sort generated column) and in TypeScript
    (resolveDisplayTitle) -- the same accepted duplication as the recipe
    fingerprint.
    """
    if display_title and display_title.strip():
        return display_title.strip()

    recipe_list = list(recipes or [])
    if recipe_list and recipe_list[0].name.strip():
        return recipe_list[0].name.strip()

    if page_title and page_title.strip():
        return page_title.strip()

    return PLACEHOLDER_TITLE
