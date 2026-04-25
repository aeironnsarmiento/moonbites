import re
from collections.abc import Iterable
from typing import Optional, Union


OTHER_CUISINE_LABEL = "Other"


_CUISINE_ALIASES: dict[str, tuple[str, ...]] = {
    "American": (
        "american",
        "america",
        "north american",
        "north america",
        "united states",
        "united states of america",
        "usa",
        "us",
        "u s",
        "u s a",
        "southern",
        "southern us",
        "southern united states",
        "cajun",
        "creole",
        "tex mex",
        "tex-mex",
        "new england",
        "southwestern",
    ),
    "British": (
        "british",
        "english",
        "england",
        "uk",
        "u k",
        "united kingdom",
        "great britain",
        "scottish",
        "scotland",
        "welsh",
        "wales",
        "irish",
        "ireland",
    ),
    "Chinese": ("chinese", "china", "szechuan", "sichuan", "cantonese"),
    "French": ("french", "france"),
    "Greek": ("greek", "greece"),
    "Indian": ("indian", "india"),
    "Italian": ("italian", "italy"),
    "Japanese": ("japanese", "japan"),
    "Korean": ("korean", "korea", "south korea"),
    "Mediterranean": ("mediterranean",),
    "Mexican": ("mexican", "mexico"),
    "Middle Eastern": ("middle eastern", "middle east", "levantine", "levant"),
    "Moroccan": ("moroccan", "morocco"),
    "Spanish": ("spanish", "spain"),
    "Thai": ("thai", "thailand"),
    "Vietnamese": ("vietnamese", "vietnam"),
}


CANONICAL_CUISINES = sorted(_CUISINE_ALIASES)


def _normalize_cuisine_text(value: str) -> str:
    normalized = value.strip().casefold()
    normalized = re.sub(r"[^\w\s-]", " ", normalized)
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


_ALIAS_TO_CANONICAL = {
    _normalize_cuisine_text(alias): canonical
    for canonical, aliases in _CUISINE_ALIASES.items()
    for alias in aliases
}


def canonical_cuisine(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    normalized = _normalize_cuisine_text(value)
    if not normalized:
        return None

    return _ALIAS_TO_CANONICAL.get(normalized)


def collect_canonical_cuisines(
    recipe_cuisines: Iterable[Union[Iterable[str], None]],
) -> set[str]:
    cuisines: set[str] = set()
    has_unknown = False

    for cuisine_values in recipe_cuisines:
        if not cuisine_values:
            continue

        for cuisine_value in cuisine_values:
            canonical = canonical_cuisine(cuisine_value)
            if canonical:
                cuisines.add(canonical)
            elif str(cuisine_value).strip():
                has_unknown = True

    if not cuisines and has_unknown:
        cuisines.add(OTHER_CUISINE_LABEL)

    return cuisines
