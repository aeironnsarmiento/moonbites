from app.services.youtube.description_parser import (
    count_junk_signals,
    count_recipe_signals,
    is_probable_recipe_parse,
)


SHROUD_DESCRIPTION = """
Shroud competes in his first CS LAN Tournament in nearly a DECADE, will the goat of CS prevail against other top CS talent such as flom, n0thing, AustinCS and many other FPS goats and creators alike... and whatever Ludwig is

SECRET PROMO CODE ON ALL LOGITECH PRODUCTS: shroud
https://www.logitechg.com

THE PERFECT PC - https://maingear.com/shroud-ref

► Follow me!
TWITTER →   / shroud
TWITCH →   / shroud
YOUTUBE (2ND) → https://goo.gl/e4dRqE

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬

👌Channel Management -   / loadedcsp

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬

#shroud #gaming #cs2
"""


GARLIC_NOODLES_DESCRIPTION = """
Ingredients
- 8 oz noodles
- 2 tbsp butter
- 2 cloves garlic, minced

Instructions
1. Boil noodles for 8 minutes.
2. Toss noodles with butter.
3. Add garlic and stir.
"""


def test_count_recipe_signals_zero_for_pure_social_description():
    assert count_recipe_signals(SHROUD_DESCRIPTION) == 0


def test_count_recipe_signals_high_for_real_recipe():
    assert count_recipe_signals(GARLIC_NOODLES_DESCRIPTION) >= 4


def test_count_junk_signals_flags_promo_links_and_social():
    junk = count_junk_signals(SHROUD_DESCRIPTION)
    assert junk >= 3


def test_count_junk_signals_zero_for_clean_recipe():
    assert count_junk_signals(GARLIC_NOODLES_DESCRIPTION) == 0


def test_is_probable_recipe_parse_rejects_too_few_ingredients():
    valid, reason = is_probable_recipe_parse(
        ingredients=["1 cup flour"],
        instructions=["Mix it."],
        description=GARLIC_NOODLES_DESCRIPTION,
    )
    assert valid is False
    assert reason and "ingredient" in reason.lower()


def test_is_probable_recipe_parse_rejects_no_instructions():
    valid, reason = is_probable_recipe_parse(
        ingredients=["1 cup flour", "2 tbsp sugar"],
        instructions=[],
        description=GARLIC_NOODLES_DESCRIPTION,
    )
    assert valid is False
    assert reason and "instruction" in reason.lower()


def test_is_probable_recipe_parse_rejects_url_only_instructions():
    valid, reason = is_probable_recipe_parse(
        ingredients=["1 cup flour", "2 tbsp sugar"],
        instructions=["https://youtu.be/abc"],
        description=GARLIC_NOODLES_DESCRIPTION,
    )
    assert valid is False
    assert reason and "url" in reason.lower()


def test_is_probable_recipe_parse_rejects_low_recipe_signals():
    valid, reason = is_probable_recipe_parse(
        ingredients=["item one", "item two"],
        instructions=["do a thing"],
        description="Just chatting about CS today, no food here.",
    )
    assert valid is False
    assert reason and "signal" in reason.lower()


def test_is_probable_recipe_parse_rejects_when_junk_dominates():
    valid, reason = is_probable_recipe_parse(
        ingredients=["1 cup flour", "2 tbsp sugar"],
        instructions=["Mix flour and sugar."],
        description=SHROUD_DESCRIPTION,
    )
    assert valid is False
    assert reason is not None


def test_is_probable_recipe_parse_accepts_real_recipe():
    valid, reason = is_probable_recipe_parse(
        ingredients=["1 cup flour", "2 tbsp sugar", "1 cup milk"],
        instructions=["Mix flour and milk for 1 minute.", "Cook pancakes at 350F."],
        description=GARLIC_NOODLES_DESCRIPTION,
    )
    assert valid is True
    assert reason is None
