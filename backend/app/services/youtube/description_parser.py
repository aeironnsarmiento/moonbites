from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

from ...schemas.extract import IngredientSection
from ...utils.text import clean_text


URL_PATTERN = re.compile(r"https?://[^\s<>\]\)\"']+")
SOCIAL_OR_URL_PATTERN = re.compile(
    r"(?i)(https?://|subscribe|follow me|watch more|instagram|tiktok|facebook|"
    r"affiliate|amazon|music|chapters|timestamps)"
)
QUANTITY_PATTERN = re.compile(
    r"(?i)\b(?:\d+(?:\s+\d+/\d+|[./]\d+)?|pinch|dash|handful)\b"
)
MEASUREMENT_PATTERN = re.compile(
    r"(?i)\b(?:\d+(?:\s+\d+/\d+|[./]\d+)?\s*)?(cups?|tbsp|tablespoons?|tsp|"
    r"teaspoons?|g|kg|oz|lb|lbs|ml|l|liters?|litres?|cloves?|heads?)\b"
)
FOOD_KEYWORD_PATTERN = re.compile(
    r"(?i)\b(salt|sugar|flour|butter|oil|garlic|onion|pepper|rice|noodles?|stock|"
    r"broth|chicken|beef|pork|fish|salmon|egg|eggs|milk|cream|cheese|tomato|"
    r"cilantro|lime|lemon|sauce|yogurt|tortillas?|honey|soy|paprika|broccoli|"
    r"seasoning|water|seeds?)\b"
)
PREP_PHRASE_PATTERN = re.compile(
    r"(?i)\b(minced|chopped|diced|sliced|washed|juiced|trimmed|cut|florets|"
    r"skin on|skin off)\b"
)
ACTION_VERB_PATTERN = re.compile(
    r"(?i)^(add|mix|stir|bake|cook|combine|whisk|pour|heat|boil|toss|season|"
    r"serve|fry|saute|sauté|simmer|chop|slice|blend|preheat|roast|grill|warm)\b"
)
NUMBERED_STEP_PATTERN = re.compile(r"(?i)^(\d+[\).\s-]+|step\s+\d+)")
TIME_TEMP_PATTERN = re.compile(
    r"(?i)\b(\d+\s*(minutes?|mins?|hours?|hrs?)|\d+\s*[FC]\b|\d+\s*degrees?)\b"
)
YIELD_PATTERN = re.compile(
    r"(?i)^(?:makes?|serves?|yield|yields|portions?)\s*[:-]\s*(.+)$"
)

INGREDIENT_REGION_HINTS = {
    "ingredients",
    "ingredient list",
    "what you'll need",
    "what you need",
    "shopping list",
    "components",
}
INSTRUCTION_REGION_HINTS = {
    "instructions",
    "directions",
    "method",
    "steps",
    "preparation",
    "how to make",
    "how to cook",
}
NUTRITION_REGION_HINTS = {
    "nutrition",
    "nutrition facts",
    "nutritional guide",
    "nutritional information",
}
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
NUTRITION_KEY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("servingSize", re.compile(r"(?i)^(?:portion size|serving size)\s*[:-]?\s*(.+)$")),
    ("calories", re.compile(r"(?i)^calories\s*[:-]?\s*(.+)$")),
    ("saturatedFatContent", re.compile(r"(?i)^saturated fat\s*[:-]?\s*(.+)$")),
    ("transFatContent", re.compile(r"(?i)^trans fat\s*[:-]?\s*(.+)$")),
    ("fatContent", re.compile(r"(?i)^(?:total fat|fat)\s*[:-]?\s*(.+)$")),
    ("cholesterolContent", re.compile(r"(?i)^cholesterol\s*[:-]?\s*(.+)$")),
    ("sodiumContent", re.compile(r"(?i)^sodium\s*[:-]?\s*(.+)$")),
    (
        "carbohydrateContent",
        re.compile(r"(?i)^(?:total carbohydrate|carbohydrates?|carbs?)\s*[:-]?\s*(.+)$"),
    ),
    ("fiberContent", re.compile(r"(?i)^(?:dietary fiber|fiber)\s*[:-]?\s*(.+)$")),
    ("sugarContent", re.compile(r"(?i)^sugars?\s*[:-]?\s*(.+)$")),
    ("proteinContent", re.compile(r"(?i)^protein\s*[:-]?\s*(.+)$")),
)


@dataclass(frozen=True)
class ParsedYouTubeDescription:
    raw_recipe: dict[str, Any]
    ingredient_sections: list[IngredientSection]
    ingredients: list[str]
    instructions: list[str]
    confidence: int
    is_complete: bool
    parse_status: str
    parse_reason: Optional[str]


@dataclass(frozen=True)
class ScoredLine:
    raw: str
    text: str
    ingredient_score: int
    instruction_score: int
    heading_score: int
    nutrition_score: int
    junk_score: int


def _strip_bullet(value: str) -> str:
    return re.sub(r"^[\s•◦▪▫●○■□▢▣▤▥▦▧▨▩☐☑✓✔✗✘*-]+", "", value).strip()


def _strip_step_marker(value: str) -> str:
    stripped = _strip_bullet(value)
    return re.sub(r"(?i)^(?:step\s*)?\d+[\).\s-]+", "", stripped).strip()


def _heading_title(value: str) -> Optional[str]:
    cleaned = clean_text(_strip_bullet(value))
    if not cleaned:
        return None

    title = re.sub(r"\s*[:-]\s*$", "", cleaned).strip()
    return title or None


def _heading_key(value: str) -> str:
    return (_heading_title(value) or "").casefold()


def _word_count(value: str) -> int:
    return len([part for part in re.split(r"\s+", value.strip()) if part])


def _is_title_like(value: str) -> bool:
    words = [word for word in re.split(r"\s+", value.strip()) if word]
    if not words:
        return False
    title_words = sum(1 for word in words if word[:1].isupper())
    return value.isupper() or title_words >= max(1, len(words) - 1)


def _nutrition_value(text: str) -> tuple[Optional[str], Optional[str]]:
    for key, pattern in NUTRITION_KEY_PATTERNS:
        if match := pattern.match(text):
            value = clean_text(match.group(1))
            if value:
                return key, value

    return None, None


def _parse_yield(text: str) -> Optional[str]:
    if match := YIELD_PATTERN.match(text):
        return clean_text(match.group(1))
    return None


def _ingredient_score(raw_line: str) -> int:
    cleaned = clean_text(_strip_bullet(raw_line)) or ""
    score = 0
    if MEASUREMENT_PATTERN.search(cleaned):
        score += 4
    elif QUANTITY_PATTERN.search(cleaned):
        score += 2
    if re.match(r"^\s*[-*•]", raw_line):
        score += 2
    if PREP_PHRASE_PATTERN.search(cleaned):
        score += 1
    if _word_count(cleaned) <= 10:
        score += 1
    if FOOD_KEYWORD_PATTERN.search(cleaned):
        score += 1
    if _nutrition_value(cleaned)[0]:
        score -= 4
    if SOCIAL_OR_URL_PATTERN.search(cleaned):
        score -= 4
    if _word_count(cleaned) > 18:
        score -= 2
    return score


def _instruction_score(raw_line: str) -> int:
    cleaned = clean_text(_strip_step_marker(raw_line)) or ""
    score = 0
    if ACTION_VERB_PATTERN.search(cleaned):
        score += 3
    if NUMBERED_STEP_PATTERN.search(raw_line.strip()):
        score += 2
    if TIME_TEMP_PATTERN.search(cleaned):
        score += 2
    if _word_count(cleaned) > 8 or cleaned.endswith("."):
        score += 1
    if SOCIAL_OR_URL_PATTERN.search(cleaned):
        score -= 4
    return score


def _heading_score(raw_line: str) -> int:
    cleaned = clean_text(_strip_bullet(raw_line)) or ""
    key = _heading_key(raw_line)
    score = 0
    if not cleaned:
        return score
    if _word_count(cleaned) <= 5:
        score += 2
    if re.search(r"[:-]\s*$", cleaned):
        score += 3
    if _is_title_like(_heading_title(cleaned) or ""):
        score += 1
    if key.startswith("for "):
        score += 2
    if key in INGREDIENT_REGION_HINTS | INSTRUCTION_REGION_HINTS | NUTRITION_REGION_HINTS:
        score += 4
    if MEASUREMENT_PATTERN.search(cleaned):
        score -= 5
    if SOCIAL_OR_URL_PATTERN.search(cleaned):
        score -= 5
    return score


def _nutrition_score(raw_line: str) -> int:
    cleaned = clean_text(_strip_bullet(raw_line)) or ""
    key = _heading_key(cleaned)
    score = 0
    if key in NUTRITION_REGION_HINTS:
        score += 4
    if _nutrition_value(cleaned)[0]:
        score += 5
    return score


def _junk_score(raw_line: str) -> int:
    cleaned = clean_text(raw_line) or ""
    score = 0
    if SOCIAL_OR_URL_PATTERN.search(cleaned):
        score += 5
    return score


def _score_line(raw_line: str) -> Optional[ScoredLine]:
    cleaned = clean_text(raw_line)
    if not cleaned:
        return None

    return ScoredLine(
        raw=raw_line,
        text=cleaned,
        ingredient_score=_ingredient_score(raw_line),
        instruction_score=_instruction_score(raw_line),
        heading_score=_heading_score(raw_line),
        nutrition_score=_nutrition_score(raw_line),
        junk_score=_junk_score(raw_line),
    )


def _clean_ingredient_line(value: str) -> Optional[str]:
    cleaned = clean_text(_strip_bullet(value))
    if not cleaned or SOCIAL_OR_URL_PATTERN.search(cleaned):
        return None
    return cleaned


def _clean_instruction_line(value: str) -> Optional[str]:
    cleaned = clean_text(_strip_step_marker(value))
    if not cleaned or SOCIAL_OR_URL_PATTERN.search(cleaned):
        return None
    return cleaned


def _next_content_lines(lines: list[ScoredLine], index: int, limit: int = 5) -> list[ScoredLine]:
    next_lines: list[ScoredLine] = []
    for candidate in lines[index + 1 :]:
        if candidate.junk_score >= 5:
            break
        key = _heading_key(candidate.text)
        if key in INGREDIENT_REGION_HINTS | INSTRUCTION_REGION_HINTS | NUTRITION_REGION_HINTS:
            break
        next_lines.append(candidate)
        if len(next_lines) >= limit:
            break

    return next_lines


def _is_ingredient_context_heading(lines: list[ScoredLine], index: int) -> bool:
    line = lines[index]
    if line.heading_score < 2 or line.ingredient_score >= 4:
        return False

    next_lines = _next_content_lines(lines, index)
    ingredient_like = [
        candidate
        for candidate in next_lines
        if candidate.ingredient_score >= 3 and candidate.nutrition_score < 5
    ]
    return len(ingredient_like) >= 2


def _classify_region_anchor(line: ScoredLine) -> Optional[str]:
    key = _heading_key(line.text)
    if key in INGREDIENT_REGION_HINTS:
        return "ingredient"
    if key in INSTRUCTION_REGION_HINTS:
        return "instruction"
    if key in NUTRITION_REGION_HINTS:
        return "nutrition"
    return None


def _scored_description_lines(description: str) -> list[ScoredLine]:
    return [
        scored
        for raw_line in description.splitlines()
        if (scored := _score_line(raw_line)) is not None
    ]


def count_recipe_signals(description: str) -> int:
    return sum(
        1
        for line in _scored_description_lines(description)
        if line.ingredient_score >= 2
        or line.instruction_score >= 3
        or line.heading_score >= 3
    )


def count_junk_signals(description: str) -> int:
    return sum(
        1
        for line in _scored_description_lines(description)
        if line.junk_score > 0
    )


def _description_signals_recipe(description: str) -> tuple[bool, Optional[str]]:
    recipe_signal_count = count_recipe_signals(description)
    junk_signal_count = count_junk_signals(description)

    if recipe_signal_count < 2:
        return False, "Description lacks recipe signals."
    if junk_signal_count > recipe_signal_count:
        return False, "Description dominated by promotional/social content."
    return True, None


def is_probable_recipe_parse(
    ingredients: list[str],
    instructions: list[str],
    description: str,
) -> tuple[bool, Optional[str]]:
    if len(ingredients) < 2:
        return False, "Fewer than 2 ingredient lines found."
    if len(instructions) < 1:
        return False, "No instruction lines found."
    if any(line.startswith(("http://", "https://")) for line in instructions):
        return False, "Instructions consist only of URLs."

    return _description_signals_recipe(description)


def parse_youtube_description(
    title: str,
    description: str,
    *,
    source_url: Optional[str] = None,
) -> ParsedYouTubeDescription:
    scored_lines = _scored_description_lines(description)
    region: Optional[str] = None
    recipe_yield: Optional[str] = None
    nutrition: dict[str, str] = {}
    ingredients: list[str] = []
    instructions: list[str] = []
    ingredient_sections: list[IngredientSection] = []
    current_section_title: Optional[str] = None
    current_section_items: list[str] = []
    confidence = 0

    def flush_section() -> None:
        nonlocal current_section_items, current_section_title
        if current_section_title and current_section_items:
            ingredient_sections.append(
                IngredientSection(
                    title=current_section_title,
                    items=list(current_section_items),
                )
            )
        current_section_title = None
        current_section_items = []

    def add_ingredient(line: ScoredLine) -> None:
        nonlocal confidence
        ingredient = _clean_ingredient_line(line.raw)
        if not ingredient:
            return
        if ingredient not in ingredients:
            ingredients.append(ingredient)
        if current_section_title and ingredient not in current_section_items:
            current_section_items.append(ingredient)
        confidence += max(line.ingredient_score, 1)

    def add_instruction(line: ScoredLine) -> None:
        nonlocal confidence
        instruction = _clean_instruction_line(line.raw)
        if instruction and instruction not in instructions:
            instructions.append(instruction)
            confidence += max(line.instruction_score, 1)

    for index, line in enumerate(scored_lines):
        if line.junk_score >= 5:
            region = "junk"
            continue

        if yield_value := _parse_yield(line.text):
            recipe_yield = recipe_yield or yield_value
            continue

        nutrition_key, nutrition_value = _nutrition_value(line.text)
        if nutrition_key and nutrition_value:
            nutrition[nutrition_key] = nutrition_value
            continue

        if anchor := _classify_region_anchor(line):
            if anchor != "ingredient":
                flush_section()
            region = anchor
            continue

        if region == "nutrition":
            continue

        if region == "junk":
            continue

        if _is_ingredient_context_heading(scored_lines, index):
            flush_section()
            current_section_title = _heading_title(line.text)
            region = "ingredient"
            confidence += max(line.heading_score, 1)
            continue

        if region == "instruction" or (
            line.instruction_score > line.ingredient_score and line.instruction_score >= 3
        ):
            add_instruction(line)
            continue

        if region == "ingredient":
            if line.ingredient_score >= 2:
                add_ingredient(line)
            continue

        if line.ingredient_score > line.instruction_score and line.ingredient_score >= 3:
            add_ingredient(line)

    flush_section()

    description_ok, description_reason = _description_signals_recipe(description)

    if (
        ingredients
        and not instructions
        and source_url
        and len(ingredients) >= 2
        and description_ok
    ):
        instructions = [source_url]
        confidence += 1

    if len(ingredients) < 2:
        parse_status = "not_recipe"
        parse_reason: Optional[str] = "Fewer than 2 ingredient lines found."
    elif len(instructions) < 1:
        parse_status = "not_recipe"
        parse_reason = "No instruction lines found."
    elif not description_ok:
        parse_status = "not_recipe"
        parse_reason = description_reason
    else:
        parse_status = "recipe"
        parse_reason = None

    raw_recipe: dict[str, Any] = {
        "@type": "Recipe",
        "name": title,
        "recipeIngredient": ingredients,
        "recipeInstructions": instructions,
    }
    if recipe_yield:
        raw_recipe["recipeYield"] = recipe_yield
    if nutrition:
        raw_recipe["nutrition"] = nutrition
    if ingredient_sections:
        raw_recipe["ingredientSections"] = [
            {"name": section.title, "recipeIngredient": section.items}
            for section in ingredient_sections
        ]

    is_complete = (
        parse_status == "recipe"
        and len(ingredients) >= 1
        and len(instructions) >= 1
        and confidence > 0
    )

    return ParsedYouTubeDescription(
        raw_recipe=raw_recipe,
        ingredient_sections=ingredient_sections,
        ingredients=ingredients,
        instructions=instructions,
        confidence=confidence,
        is_complete=is_complete,
        parse_status=parse_status,
        parse_reason=parse_reason,
    )


def _is_skipped_host(hostname: str) -> bool:
    return any(part in hostname for part in SKIP_HOST_PARTS)


def extract_ranked_recipe_urls(description: str) -> list[str]:
    scored_urls: list[tuple[int, int, str]] = []
    seen: set[str] = set()

    for line_number, line in enumerate(description.splitlines()):
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
