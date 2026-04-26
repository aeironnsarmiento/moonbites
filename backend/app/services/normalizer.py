import re
from hashlib import sha256
from json import dumps
from typing import Any, Optional

from ..schemas.extract import IngredientSection, NormalizedRecipe
from ..utils.text import clean_text, unique_strings


NUTRITION_KEY_MAP = {
    "calories": "calories",
    "carbohydrateContent": "carbohydrates",
    "proteinContent": "protein",
    "fatContent": "fat",
    "saturatedFatContent": "saturatedFat",
    "transFatContent": "transFat",
    "cholesterolContent": "cholesterol",
    "sodiumContent": "sodium",
    "fiberContent": "fiber",
    "sugarContent": "sugar",
    "unsaturatedFatContent": "unsaturatedFat",
    "servingSize": "servingSize",
}


def has_recipe_type(value: Any) -> bool:
    if isinstance(value, str):
        return value.casefold() == "recipe"
    if isinstance(value, list):
        return any(
            isinstance(item, str) and item.casefold() == "recipe" for item in value
        )
    return False


def collect_recipe_nodes(payload: Any) -> list[Any]:
    recipes: list[Any] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            node_type = node.get("@type")

            if has_recipe_type(node_type):
                recipes.append(node)

            graph = node.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    visit(item)
            elif isinstance(graph, dict):
                visit(graph)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(payload)
    return recipes


def normalize_recipe_yield(value: Any) -> Optional[str]:
    if isinstance(value, list):
        candidates = unique_strings(
            [cleaned for item in value if (cleaned := clean_text(item))]
        )
    else:
        cleaned = clean_text(value)
        candidates = [cleaned] if cleaned else []

    if not candidates:
        return None

    descriptive = [
        candidate for candidate in candidates if re.search(r"[A-Za-z]", candidate)
    ]
    return descriptive[0] if descriptive else candidates[0]


def parse_iso_duration(value: str) -> Optional[str]:
    pattern = re.compile(
        r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
    )
    match = pattern.match(value)

    if not match:
        return None

    parts: list[str] = []
    units = {
        "days": "day",
        "hours": "hour",
        "minutes": "minute",
        "seconds": "second",
    }

    for key, label in units.items():
        amount = match.group(key)
        if amount:
            number = int(amount)
            suffix = "" if number == 1 else "s"
            parts.append(f"{number} {label}{suffix}")

    return ", ".join(parts) if parts else None


def normalize_cook_time(value: Any) -> Optional[str]:
    if isinstance(value, list):
        for item in value:
            normalized = normalize_cook_time(item)
            if normalized:
                return normalized
        return None

    cleaned = clean_text(value)
    if not cleaned:
        return None

    return parse_iso_duration(cleaned) or cleaned


def normalize_nutrition(value: Any) -> Optional[dict[str, str]]:
    if not isinstance(value, dict):
        return None

    normalized: dict[str, str] = {}

    for source_key, target_key in NUTRITION_KEY_MAP.items():
        cleaned = clean_text(value.get(source_key))
        if cleaned:
            normalized[target_key] = cleaned

    return normalized or None


def normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = value.splitlines()
    elif isinstance(value, list):
        raw_items = value
    else:
        return []

    cleaned_items = [cleaned for item in raw_items if (cleaned := clean_text(item))]
    return unique_strings(cleaned_items)


def normalize_ingredients(value: Any) -> list[str]:
    return _extract_ingredient_lines(value)


def _clean_ingredient_text(value: Any) -> Optional[str]:
    cleaned = clean_text(value)
    if not cleaned:
        return None

    normalized = re.sub(r"^[\s•◦▪▫●○■□▢▣▤▥▦▧▨▩☐☑✓✔✗✘*-]+", "", cleaned)
    return normalized.strip() or None


def _format_property_value_ingredient(value: dict[str, Any]) -> Optional[str]:
    quantity = _clean_ingredient_text(value.get("value"))
    unit = _clean_ingredient_text(value.get("unitText") or value.get("unitCode"))
    name = _clean_ingredient_text(value.get("name"))

    if not any((quantity, unit, name)):
        return None

    if quantity or unit:
        return _clean_ingredient_text(
            " ".join(part for part in (quantity, unit, name) if part)
        )

    return name


def _extract_ingredient_lines(value: Any) -> list[str]:
    ingredients: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, (str, int, float)):
            cleaned = _clean_ingredient_text(node)
            if cleaned:
                ingredients.append(cleaned)
            return

        if isinstance(node, list):
            for item in node:
                visit(item)
            return

        if not isinstance(node, dict):
            return

        item_list = node.get("itemListElement")
        if item_list is not None:
            visit(item_list)
            return

        text = _clean_ingredient_text(node.get("text"))
        if text:
            ingredients.append(text)
            return

        property_value_text = _format_property_value_ingredient(node)
        if property_value_text:
            ingredients.append(property_value_text)
            return

        name = _clean_ingredient_text(node.get("name"))
        if name:
            ingredients.append(name)

    visit(value)
    return ingredients


def _normalize_ingredient_section(value: Any) -> Optional[IngredientSection]:
    if not isinstance(value, dict):
        return None

    title = clean_text(value.get("name") or value.get("headline") or value.get("title"))
    items = normalize_ingredients(
        value.get("recipeIngredient")
        or value.get("ingredients")
        or value.get("itemListElement")
    )

    if not items:
        return None

    return IngredientSection(title=title, items=items)


def normalize_ingredient_sections(recipe: Any) -> list[IngredientSection]:
    if not isinstance(recipe, dict):
        return []

    sections: list[IngredientSection] = []
    candidates = [
        recipe.get("ingredientSections"),
        recipe.get("recipeIngredientSections"),
        recipe.get("hasPart"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            for item in candidate:
                normalized = _normalize_ingredient_section(item)
                if normalized is not None:
                    sections.append(normalized)
        elif isinstance(candidate, dict):
            normalized = _normalize_ingredient_section(candidate)
            if normalized is not None:
                sections.append(normalized)

    recipe_ingredient = recipe.get("recipeIngredient")
    if isinstance(recipe_ingredient, dict):
        normalized = _normalize_ingredient_section(recipe_ingredient)
        if normalized is not None:
            sections.append(normalized)
    elif isinstance(recipe_ingredient, list):
        for item in recipe_ingredient:
            normalized = _normalize_ingredient_section(item)
            if normalized is not None:
                sections.append(normalized)

    unique_sections: list[IngredientSection] = []
    seen: set[tuple[Optional[str], tuple[str, ...]]] = set()

    for section in sections:
        key = (section.title, tuple(section.items))
        if key in seen:
            continue

        seen.add(key)
        unique_sections.append(section)

    return unique_sections


def flatten_ingredient_sections(sections: list[IngredientSection]) -> list[str]:
    return [item for section in sections for item in section.items if item]


def _ingredient_match_key(value: str) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""

    simplified = re.sub(r"[(),]", " ", cleaned).casefold()
    return re.sub(r"\s+", " ", simplified).strip()


def ingredient_sections_match_ingredients(
    sections: list[IngredientSection], ingredients: list[str]
) -> bool:
    if not sections or not ingredients:
        return False

    section_items = [
        _ingredient_match_key(item) for item in flatten_ingredient_sections(sections)
    ]
    ingredient_items = [_ingredient_match_key(item) for item in ingredients]
    return section_items == ingredient_items


def extract_instruction_lines(value: Any) -> list[str]:
    instructions: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, str):
            cleaned = clean_text(node)
            if cleaned:
                instructions.append(cleaned)
            return

        if isinstance(node, list):
            for item in node:
                visit(item)
            return

        if isinstance(node, dict):
            item_list = node.get("itemListElement")
            if item_list is not None:
                visit(item_list)
                return

            text = clean_text(node.get("text")) or clean_text(node.get("name"))
            if text:
                instructions.append(text)

    visit(value)
    return unique_strings(instructions)


def normalize_recipe(
    recipe: Any,
    *,
    fallback_ingredient_sections: Optional[list[IngredientSection]] = None,
    fallback_instructions: Optional[list[str]] = None,
) -> Optional[NormalizedRecipe]:
    if not isinstance(recipe, dict):
        return None

    name = clean_text(recipe.get("name"))
    ingredient_sections = normalize_ingredient_sections(recipe)
    ingredients = (
        flatten_ingredient_sections(ingredient_sections)
        if ingredient_sections
        else normalize_ingredients(recipe.get("recipeIngredient"))
    )
    if not ingredients and fallback_ingredient_sections:
        ingredient_sections = fallback_ingredient_sections
        ingredients = flatten_ingredient_sections(ingredient_sections)
    elif (
        not ingredient_sections
        and fallback_ingredient_sections
        and ingredient_sections_match_ingredients(
            fallback_ingredient_sections,
            ingredients,
        )
    ):
        ingredient_sections = fallback_ingredient_sections

    instructions = extract_instruction_lines(recipe.get("recipeInstructions"))
    if not instructions and fallback_instructions:
        instructions = fallback_instructions

    if not name or not ingredients or not instructions:
        return None

    recipe_cuisine = normalize_string_list(recipe.get("recipeCuisine"))

    return NormalizedRecipe(
        name=name,
        recipeYield=normalize_recipe_yield(recipe.get("recipeYield")),
        cookTime=normalize_cook_time(recipe.get("cookTime")),
        recipeCuisine=recipe_cuisine or None,
        nutrition=normalize_nutrition(recipe.get("nutrition")),
        ingredients=ingredients,
        ingredientSections=ingredient_sections or None,
        instructions=instructions,
    )


def build_recipe_fingerprint(recipe: NormalizedRecipe) -> str:
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


def dedupe_normalized_recipes(
    recipes: list[NormalizedRecipe],
) -> list[NormalizedRecipe]:
    seen: set[str] = set()
    unique_recipes: list[NormalizedRecipe] = []

    for recipe in recipes:
        fingerprint = build_recipe_fingerprint(recipe)
        if fingerprint in seen:
            continue

        seen.add(fingerprint)
        unique_recipes.append(recipe)

    return unique_recipes
