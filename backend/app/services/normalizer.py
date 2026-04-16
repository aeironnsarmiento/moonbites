import re
from hashlib import sha256
from json import dumps
from typing import Any, Optional

from backend.app.schemas.extract import NormalizedRecipe
from backend.app.utils.text import clean_text, unique_strings


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
        return value == "Recipe"
    if isinstance(value, list):
        return any(isinstance(item, str) and item == "Recipe" for item in value)
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
    return normalize_string_list(value)


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


def normalize_recipe(recipe: Any) -> Optional[NormalizedRecipe]:
    if not isinstance(recipe, dict):
        return None

    name = clean_text(recipe.get("name"))
    ingredients = normalize_ingredients(recipe.get("recipeIngredient"))
    instructions = extract_instruction_lines(recipe.get("recipeInstructions"))

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
