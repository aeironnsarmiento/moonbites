from app.services.cuisine_catalog import (
    CANONICAL_CUISINES,
    OTHER_CUISINE_LABEL,
    canonical_cuisine,
    collect_canonical_cuisines,
)


def test_canonical_cuisine_direct_match_returns_canonical_label():
    assert canonical_cuisine("American") == "American"


def test_canonical_cuisine_is_case_insensitive():
    assert canonical_cuisine("AMERICAN") == "American"
    assert canonical_cuisine("american") == "American"


def test_canonical_cuisine_trims_whitespace_and_punctuation():
    assert canonical_cuisine("  Italian.  ") == "Italian"
    assert canonical_cuisine("Italian,") == "Italian"


def test_canonical_cuisine_maps_us_aliases_to_american():
    aliases = (
        "America",
        "United States",
        "USA",
        "U.S.",
        "North America",
        "north american",
    )

    for alias in aliases:
        assert canonical_cuisine(alias) == "American", alias


def test_canonical_cuisine_maps_uk_aliases_to_british():
    aliases = ("English", "UK", "United Kingdom", "Scottish", "Welsh", "Irish")

    for alias in aliases:
        assert canonical_cuisine(alias) == "British", alias


def test_canonical_cuisine_maps_asian_country_aliases():
    assert canonical_cuisine("Japan") == "Japanese"
    assert canonical_cuisine("China") == "Chinese"
    assert canonical_cuisine("South Korea") == "Korean"
    assert canonical_cuisine("Thailand") == "Thai"
    assert canonical_cuisine("Vietnam") == "Vietnamese"


def test_canonical_cuisine_returns_none_for_unknown_value():
    assert canonical_cuisine("Atlantis") is None


def test_canonical_cuisine_returns_none_for_empty_and_none():
    assert canonical_cuisine("") is None
    assert canonical_cuisine("   ") is None
    assert canonical_cuisine(None) is None


def test_collect_canonical_cuisines_dedupes_across_aliases():
    recipe_cuisines = [["American", "USA"], ["North America"], ["Italian"]]

    assert collect_canonical_cuisines(recipe_cuisines) == {"American", "Italian"}


def test_collect_canonical_cuisines_handles_none_entries():
    recipe_cuisines = [None, ["Japanese"], []]

    assert collect_canonical_cuisines(recipe_cuisines) == {"Japanese"}


def test_collect_canonical_cuisines_groups_unknown_values_as_other():
    recipe_cuisines = [["Atlantis"], None]

    assert collect_canonical_cuisines(recipe_cuisines) == {OTHER_CUISINE_LABEL}


def test_collect_canonical_cuisines_prefers_known_values_over_other():
    recipe_cuisines = [["Atlantis"], ["USA"]]

    assert collect_canonical_cuisines(recipe_cuisines) == {"American"}


def test_canonical_cuisines_list_is_sorted_and_nonempty():
    assert CANONICAL_CUISINES
    assert CANONICAL_CUISINES == sorted(CANONICAL_CUISINES)
    assert OTHER_CUISINE_LABEL not in CANONICAL_CUISINES
