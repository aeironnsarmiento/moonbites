import pytest

from app.schemas.extract import NormalizedRecipe
from app.services.display_titles import (
    PLACEHOLDER_TITLE,
    build_title_source_text,
    clean_source_title,
    resolve_display_title,
    shape_violation,
    unsupported_tokens,
)


def _recipe(
    name: str = "Creamy Garlic Pasta",
    ingredients: list[str] | None = None,
    cuisine: list[str] | None = None,
    recipe_yield: str | None = None,
) -> NormalizedRecipe:
    return NormalizedRecipe(
        name=name,
        ingredients=ingredients
        or ["200g spaghetti", "4 cloves garlic", "150ml double cream"],
        instructions=["Boil the pasta.", "Make the sauce."],
        recipeCuisine=cuisine,
        recipeYield=recipe_yield,
    )


AE1_SOURCE_TITLE = (
    "The BEST Creamy Garlic Pasta You'll EVER Make!! \U0001f35d | Cooking with Sam Ep. 12"
)


# --- clean_source_title (KTD3, R3, R9) --------------------------------------


def test_clean_source_title_strips_hype_emoji_and_episode_suffix():
    # Covers AE1 on the fallback path: the deterministic cleaner alone lands
    # the contract's expected title.
    assert clean_source_title(AE1_SOURCE_TITLE, [_recipe()]) == "Creamy Garlic Pasta"


def test_clean_source_title_keeps_the_richest_segment_when_the_site_leads():
    assert (
        clean_source_title("Bon Appetit | Creamy Garlic Pasta", [_recipe()])
        == "Creamy Garlic Pasta"
    )


def test_clean_source_title_drops_hashtags_and_handles():
    assert (
        clean_source_title("#pasta #dinner Garlic Noodles @chefsam", [_recipe()])
        == "Garlic Noodles"
    )


def test_clean_source_title_drops_a_trailing_recipe_word():
    assert clean_source_title("Garlic Pasta Recipe", [_recipe()]) == "Garlic Pasta"


def test_clean_source_title_strips_a_site_tail_after_a_real_title():
    assert (
        clean_source_title("Creamy Garlic Pasta - Serious Eats", [_recipe()])
        == "Creamy Garlic Pasta"
    )


def test_clean_source_title_keeps_a_short_left_side_intact():
    # Fewer than 3 words before the dash: the tail is probably part of the title.
    assert clean_source_title("Chicken - the easy way", [_recipe()]) == "Chicken - the easy way"


@pytest.mark.parametrize(
    "raw",
    [
        "Ready in 20 minutes Garlic Pasta",
        "The Ultimate Garlic Pasta",
        "World's Greatest Garlic Pasta",
        "Viral Garlic Pasta",
    ],
)
def test_clean_source_title_removes_promo_wording(raw):
    assert clean_source_title(raw, [_recipe()]) == "Garlic Pasta"


@pytest.mark.parametrize(
    "qualifier",
    ["Easy", "Vegan", "One-Pot", "Air Fryer"],
)
def test_clean_source_title_keeps_useful_qualifiers(qualifier):
    # R2: these are informative, not hype.
    assert qualifier in clean_source_title(f"{qualifier} Garlic Pasta", [_recipe()])


def test_clean_source_title_preserves_accented_letters():
    assert clean_source_title("Jalapeño Popper Dip \U0001f336", [_recipe()]) == (
        "Jalapeño Popper Dip"
    )


def test_clean_source_title_truncates_on_a_word_boundary():
    raw = "Slow Cooked Beef Brisket With Smoked Paprika And Charred Sweetcorn Salsa"

    cleaned = clean_source_title(raw, [_recipe()])

    assert len(cleaned) <= 60
    assert not cleaned.endswith("-")
    assert cleaned == "Slow Cooked Beef Brisket With Smoked Paprika And Charred"


def test_clean_source_title_falls_back_to_the_recipe_name_when_empty():
    assert clean_source_title("   ", [_recipe(name="Chicken Adobo")]) == "Chicken Adobo"


def test_clean_source_title_falls_back_to_the_recipe_name_when_nothing_survives():
    assert clean_source_title("#viral @chef", [_recipe(name="Chicken Adobo")]) == (
        "Chicken Adobo"
    )


def test_clean_source_title_falls_back_to_the_placeholder_with_no_recipes():
    assert clean_source_title(None, []) == PLACEHOLDER_TITLE


# --- shape_violation (R1, R3) -----------------------------------------------


def test_shape_violation_accepts_a_two_word_title():
    # Deliberate: the gate floors at 2 words, not R1's 3. "Chicken Adobo" is a
    # correct title, and rejecting it would degrade to a worse raw title. Pinned
    # so it is not silently "corrected" to a 3-word floor later.
    assert shape_violation("Chicken Adobo") is None


def test_shape_violation_accepts_an_eight_word_title():
    assert shape_violation("One Pot Creamy Garlic Pasta With Crispy Sage") is None


@pytest.mark.parametrize(
    "title",
    [
        "",
        "   ",
        "Pasta",
        "Creamy Garlic Pasta With Crispy Sage And Toasted Pine Nuts Everywhere",
        "Creamy Garlic Pasta \U0001f35d",
        "Creamy Garlic Pasta #dinner",
        "Creamy Garlic Pasta @chefsam",
        "Creamy Garlic Pasta | Bon Appetit",
    ],
)
def test_shape_violation_rejects_unusable_titles(title):
    assert shape_violation(title) is not None


def test_shape_violation_rejects_a_title_over_sixty_characters():
    title = "Creamy " + "Garlic " * 8 + "Pasta"

    assert shape_violation(title) is not None


# --- unsupported_tokens (KTD2, R4, R5) --------------------------------------


def test_unsupported_tokens_accepts_a_fully_attested_title():
    # Covers AE1.
    source = build_title_source_text(AE1_SOURCE_TITLE, [_recipe()])

    assert unsupported_tokens(source, "Creamy Garlic Pasta") == []


def test_unsupported_tokens_rejects_an_unsupported_dietary_claim():
    # Covers AE2 -- the case a 0.3 overlap ratio would let through (2 of 3
    # tokens attested = 0.67).
    source = build_title_source_text(AE1_SOURCE_TITLE, [_recipe()])

    assert unsupported_tokens(source, "Vegan Garlic Pasta") == ["vegan"]


def test_unsupported_tokens_rejects_an_unsupported_cooking_method():
    source = build_title_source_text(AE1_SOURCE_TITLE, [_recipe()])

    assert unsupported_tokens(source, "Air Fryer Garlic Pasta") == ["air", "fryer"]


def test_unsupported_tokens_accepts_a_collection_title_via_the_numeral_bridge():
    # Covers AE6: "three" is attested only by the literal "3" in the source.
    source = build_title_source_text(
        "3 easy weeknight dinners!!",
        [
            _recipe(name="Weeknight Garlic Noodles"),
            _recipe(name="Weeknight Chicken Adobo"),
            _recipe(name="Weeknight Beef Chili"),
        ],
    )

    assert unsupported_tokens(source, "Three Weeknight Dinners") == []


@pytest.mark.parametrize(
    ("source_text", "title", "expected"),
    [
        ("3 weeknight dinners", "Three Weeknight Dinners", []),
        ("12 weeknight dinners", "Twelve Weeknight Dinners", []),
        ("21 weeknight dinners", "Twenty Weeknight Dinners", ["twenty"]),
        ("5 weeknight dinners", "Three Weeknight Dinners", ["three"]),
    ],
)
def test_numeral_bridge_only_attests_the_number_actually_present(
    source_text, title, expected
):
    assert unsupported_tokens(source_text, title) == expected


@pytest.mark.parametrize(
    ("source_text", "title"),
    [
        ("a rich sauce", "Rich Sauces"),
        ("garlic noodles", "Garlic Noodle"),
        ("crispy potatoes", "Crispy Potato"),
    ],
)
def test_variant_set_matches_plural_and_singular(source_text, title):
    assert unsupported_tokens(source_text, title) == []


def test_variant_set_does_not_match_a_bare_prefix():
    # A prefix rule would wrongly attest "gla" from "glass".
    assert unsupported_tokens("a glass of milk", "Gla Milk") == ["gla"]


def test_unsupported_tokens_exempts_stopwords():
    assert unsupported_tokens("garlic pasta", "Garlic and the Pasta for Pasta") == []


# --- build_title_source_text ------------------------------------------------


def test_build_title_source_text_covers_the_naming_fields_only():
    source = build_title_source_text(
        "Weeknight Dinner",
        [
            _recipe(
                name="Garlic Noodles",
                ingredients=["200g spaghetti"],
                cuisine=["Italian"],
                recipe_yield="4 servings",
            )
        ],
    )

    assert "Weeknight Dinner" in source
    assert "Garlic Noodles" in source
    assert "Italian" in source
    assert "4 servings" in source
    assert "200g spaghetti" in source
    # Instructions and nutrition never name the dish.
    assert "Boil the pasta." not in source


def test_build_title_source_text_bounds_long_inputs():
    source = build_title_source_text(
        "Big Batch",
        [_recipe(ingredients=[f"ingredient {index}" for index in range(60)])] * 5,
    )

    assert "ingredient 24" in source
    assert "ingredient 25" not in source


def test_build_title_source_text_tolerates_no_recipes():
    assert build_title_source_text("Weeknight Dinner", []) == "Weeknight Dinner"


# --- resolve_display_title (R6) ---------------------------------------------


def test_resolve_display_title_prefers_the_display_title():
    assert (
        resolve_display_title("Creamy Garlic Pasta", [_recipe(name="Pasta")], "Page")
        == "Creamy Garlic Pasta"
    )


def test_resolve_display_title_falls_back_to_the_recipe_name():
    assert resolve_display_title(None, [_recipe(name="Chicken Adobo")], "Page") == (
        "Chicken Adobo"
    )


def test_resolve_display_title_falls_back_to_the_page_title():
    assert resolve_display_title(None, [], "Page Title") == "Page Title"


def test_resolve_display_title_falls_back_to_the_placeholder():
    assert resolve_display_title(None, [], None) == PLACEHOLDER_TITLE


def test_resolve_display_title_ignores_a_blank_display_title():
    assert resolve_display_title("   ", [_recipe(name="Chicken Adobo")], None) == (
        "Chicken Adobo"
    )
