from __future__ import annotations

import pytest

from app.schemas.extract import NormalizedRecipe
from app.services.extraction_types import ExtractionResult
from app.services.recipe_match import (
    RecipeCandidate,
    is_matching_title,
    normalize_dish_name,
    select_unique_match,
)


# --- KTD9 matcher: development + locked holdout corpus ---------------------


DEVELOPMENT_CORPUS = [
    ("Miso Salmon Brothy Rice", "Miso Salmon Brothy Rice", True),
    ("Miso Salmon Brothy Rice Recipe", "Miso Salmon Brothy Rice", True),
    ("The Best Easy Miso Salmon Brothy Rice", "Miso Salmon Brothy Rice", True),
    ("Shanghai-Inspired Veggie-Packed Rice", "Shanghai-Inspired Veggie-Packed Rice", True),
    ("Raspberry Dark Chocolate Chia Pudding", "Raspberry Dark Chocolate Chia Pudding", True),
    ("Rice", "Rice", True),
    ("Fried Rice", "Rice", False),
    ("Brothy Rice Miso Salmon", "Miso Salmon Brothy Rice", True),
    ("Miso Salmon Rice Bowl With Extra Toppings", "Miso Salmon Rice", False),
    # Prep-time and count qualifiers the site prepends to its own title.
    ("15 Minute Miso Salmon Brothy Rice", "Miso Salmon Brothy Rice", True),
    ("30-Minute Miso Salmon Brothy Rice", "Miso Salmon Brothy Rice", True),
    ("5 Ingredient Chocolate Chia Pudding", "Chocolate Chia Pudding", True),
]

# Locked holdout: same-creator siblings, common-title collisions, expansions,
# near misses. Creator-site saves require zero false positives here.
HOLDOUT_CORPUS = [
    # Same-creator siblings: must not cross-match.
    ("Miso Glazed Salmon Rice Bowl", "Miso Salmon Brothy Rice", False),
    ("Brothy Chicken Rice", "Miso Salmon Brothy Rice", False),
    # Common-title collisions across unrelated creators.
    ("Chocolate Chia Pudding", "Raspberry Dark Chocolate Chia Pudding", False),
    ("Veggie-Packed Rice Bowl", "Shanghai-Inspired Veggie-Packed Rice", False),
    # Legitimate expansions (site adds a small descriptor/suffix).
    ("Shanghai-Inspired Veggie-Packed Rice Recipe", "Shanghai-Inspired Veggie-Packed Rice", True),
    ("Easy Raspberry Dark Chocolate Chia Pudding", "Raspberry Dark Chocolate Chia Pudding", True),
    # Near misses: one changed/extra substantive word.
    ("Miso Salmon Brothy Rice With Egg", "Miso Salmon Brothy Rice", False),
    ("White Chocolate Chia Pudding", "Raspberry Dark Chocolate Chia Pudding", False),
    # Single-token dish names require exact match only.
    ("Fried Rice", "Rice", False),
    ("Rice", "Rice", True),
    # A numeral that IS the dish must stay distinguishing. This is the guard
    # against "just strip every number" -- that variant collapses these two
    # into one title and produces a false-positive save.
    ("5 Layer Dip", "7 Layer Dip", False),
    ("7 Layer Dip", "7 Layer Dip", True),
]


@pytest.mark.parametrize(("title", "dish_name", "expected"), DEVELOPMENT_CORPUS)
def test_matcher_development_corpus(title, dish_name, expected):
    assert is_matching_title(title, dish_name) is expected


@pytest.mark.parametrize(("title", "dish_name", "expected"), HOLDOUT_CORPUS)
def test_matcher_locked_holdout_corpus(title, dish_name, expected):
    assert is_matching_title(title, dish_name) is expected


SITE_BRAND_CORPUS = [
    # The live Tasty case: the site signs its own JSON-LD title.
    (
        "Shanghai-Inspired Veggie-Packed Rice Recipe by Tasty",
        "tasty.co",
        "Easy Shanghai-Inspired Veggie-Packed Rice",
        True,
    ),
    ("Miso Salmon Rice by Tiffycooks", "www.tiffycooks.com", "Miso Salmon Rice", True),
    # A multi-word brand signs the title as separate tokens, while the label
    # derived from the domain has no word boundaries -- this is the case that
    # a single-token trailing match misses.
    ("Pasta Recipe by Smitten Kitchen", "smittenkitchen.com", "Pasta", True),
    # Only the fetched host's own label is stripped, never another site's.
    ("Miso Salmon Rice by Tasty", "tiffycooks.com", "Miso Salmon Rice", False),
    # A dish word that happens to match the brand is not a trailing signature.
    ("Chicken of the Sea", "tasty.co", "Chicken of the Sea", True),
    # Stripping the signature must not rescue a genuinely different dish.
    (
        "Miso Salmon Brothy Rice With Egg Recipe by Tasty",
        "tasty.co",
        "Miso Salmon Brothy Rice",
        False,
    ),
]


@pytest.mark.parametrize(
    ("title", "domain", "dish_name", "expected"), SITE_BRAND_CORPUS
)
def test_matcher_ignores_trailing_site_brand(title, domain, dish_name, expected):
    assert is_matching_title(title, dish_name, site_domain=domain) is expected


def test_site_brand_is_only_stripped_when_the_domain_is_known():
    title = "Shanghai-Inspired Veggie-Packed Rice Recipe by Tasty"
    dish = "Shanghai-Inspired Veggie-Packed Rice"

    assert is_matching_title(title, dish) is False
    assert is_matching_title(title, dish, site_domain="tasty.co") is True


def test_matcher_holdout_corpus_has_zero_false_positives():
    false_positives = [
        (title, dish_name)
        for title, dish_name, expected in HOLDOUT_CORPUS
        if not expected and is_matching_title(title, dish_name)
    ]
    assert false_positives == []


def test_normalize_dish_name_strips_accents_punctuation_and_generic_tokens():
    assert normalize_dish_name("The Best Café Crème Brûlée!") == "cafe creme brulee"


def test_normalize_dish_name_strips_time_qualifiers_but_keeps_naming_numerals():
    assert normalize_dish_name("15 Minute Miso Salmon") == "miso salmon"
    assert normalize_dish_name("30-Minute Miso Salmon") == "miso salmon"
    assert normalize_dish_name("5 Ingredient Chia Pudding") == "chia pudding"
    # The numeral names the dish here, so it survives.
    assert normalize_dish_name("7 Layer Dip") == "7 layer dip"




# --- The acceptance rule: exactly one match, or none ------------------------


def _page(url: str, *names: str) -> ExtractionResult:
    return ExtractionResult(
        source_url=url,
        final_url=url,
        title=names[0] if names else None,
        image_url=None,
        recipe_node_count=len(names),
        recipes=[
            NormalizedRecipe(
                name=name, ingredients=["1 cup flour"], instructions=["Mix it."]
            )
            for name in names
        ],
    )


def _candidates(*pairs: tuple[str, str]) -> list[RecipeCandidate]:
    return [
        RecipeCandidate(canonical_url=url, title=title, result=_page(url, title))
        for url, title in pairs
    ]


def test_select_unique_match_accepts_the_single_matching_candidate():
    candidates = _candidates(
        ("https://a.example/miso-salmon-rice", "Miso Salmon Rice"),
        ("https://a.example/pantry-staples", "Pantry Staples"),
    )

    match = select_unique_match(candidates, "Miso Salmon Rice")

    assert match is not None
    assert match.canonical_url == "https://a.example/miso-salmon-rice"


def test_select_unique_match_rejects_two_plausible_candidates():
    # Two distinct pages both naming the dish: ambiguous, so neither is the
    # Linked Recipe. Preferring the first would be a guess.
    candidates = _candidates(
        ("https://a.example/miso-salmon-rice", "Miso Salmon Rice"),
        ("https://b.example/miso-salmon-rice", "Easy Miso Salmon Rice"),
    )

    assert select_unique_match(candidates, "Miso Salmon Rice") is None


def test_select_unique_match_treats_one_page_reached_twice_as_one_candidate():
    # Same page, trailing slash and scheme case apart: deduped, so it still
    # counts once and stays a confident match.
    candidates = _candidates(
        ("https://a.example/miso-salmon-rice", "Miso Salmon Rice"),
        ("https://a.example/miso-salmon-rice/", "Miso Salmon Rice"),
    )

    assert select_unique_match(candidates, "Miso Salmon Rice") is not None


def test_select_unique_match_returns_none_without_a_dish_name():
    candidates = _candidates(("https://a.example/rice", "Miso Salmon Rice"))

    assert select_unique_match(candidates, "") is None


def test_select_unique_match_returns_none_when_nothing_matches():
    candidates = _candidates(("https://a.example/toast", "Salmon Toast"))

    assert select_unique_match(candidates, "Miso Salmon Rice") is None
