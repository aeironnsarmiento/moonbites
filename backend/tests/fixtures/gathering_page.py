"""The Gathering Page fixture and the Gemini output it is expected to produce.

The HTML is the page's server response captured with curl, so it carries no
Recipe JSON-LD: the site injects that client-side. Gemini is never called in
tests; these payloads are hand-built in the shape Gemini returns.
"""

from __future__ import annotations

import json
from pathlib import Path


GATHERING_URL = "https://thegatheringpage.com/recipes/creamy-tuscan-chicken-skillet"
GATHERING_DISH = "Creamy Tuscan Chicken Skillet"
GATHERING_SECTION_TITLES = ["Chickem", "Mushrooms & Sun Dried Tomato Sauce"]

_HTML_PATH = Path(__file__).with_name(
    "thegatheringpage_creamy_tuscan_chicken_skillet.html"
)

_CHICKEN = [
    "4 boneless, skinless chicken thighs (~2 lbs)",
    "1 tsp. cumin",
    "1/2 tsp. paprika",
    "1/2 tsp. garlic powder",
    "1/4 tsp. salt",
    "Dash of cracked black pepper",
    "2 tbsp. olive oil",
]
_SAUCE = [
    "1 tbsp. butter",
    "3 cloves minced garlic",
    "1/2 yellow onion, chopped fine",
    "1/3 cup sun dried tomatoes, drained and sliced thin",
    "8 oz. baby bella mushrooms, sliced",
    "1.5 cups heavy cream",
    "1/2 cup grated parmesan cheese",
    "2 cups spinach, roughly chopped",
]
_INSTRUCTIONS = [
    "Place chicken thighs in a large bowl and pat them with a paper towel to remove excess liquid.",
    "Add cumin, paprika, garlic powder, salt and pepper. Use your hands to gently rub the seasonings in to the chicken.",
    "Heat olive oil in a skillet over medium heat. Once the oil is heated, add the chicken to the skillet. Let cook for 5 minutes, flip and let cook for 7 more minutes. (Use a thermometer to check thickest part of chicken and make sure it has reached an internal temperature of 165°F).",
    "Remove the chicken and place on a plate for later use.",
    "Turn the heat down to medium low, add the butter to the skillet and once it has melted add the minced garlic and onions. Let sauté for about a minute, then add the sun dried tomatoes and mushrooms. Sauté for 5 minutes, stirring occasionally.",
    "Add the cream and parmesan cheese to the skillet and bring to a low simmer. Let simmer 5 minutes, stirring occasionally.",
    "Add the chopped spinach, stir in, and remove the skillet from the heat.",
    "Place the chicken on top of the creamy vegetable mixture and serve. Enjoy!",
]
_PARAPHRASED_INSTRUCTIONS = [
    "Put the chicken thighs in a large bowl and pat dry with a paper towel.",
    "Season with cumin, paprika, garlic powder, salt and pepper, rubbing the spices into the chicken.",
    "Heat the olive oil in a skillet over medium heat, then cook the chicken 5 minutes, flip, and cook 7 minutes more until it reaches 165°F.",
    "Move the chicken to a plate.",
    "Lower the heat to medium low, melt the butter, and sauté the garlic and onions for a minute, then add the sun dried tomatoes and mushrooms and sauté 5 minutes.",
    "Stir in the cream and parmesan and simmer 5 minutes.",
    "Stir in the spinach and take the skillet off the heat.",
    "Top with the chicken and serve.",
]
_NORMALIZED_CHICKEN = [
    "4 boneless skinless chicken thighs (about 2 pounds)",
    "1 teaspoon cumin",
    "1/2 teaspoon paprika",
    "1/2 teaspoon garlic powder",
    "1/4 teaspoon salt",
    "A dash of cracked black pepper",
    "2 tablespoons olive oil",
]
_NORMALIZED_SAUCE = [
    "1 tablespoon butter",
    "3 cloves garlic, minced",
    "1/2 yellow onion, finely chopped",
    "1/3 cup sun-dried tomatoes, drained and thinly sliced",
    "8 ounces baby bella mushrooms, sliced",
    "1 1/2 cups heavy cream",
    "1/2 cup grated parmesan cheese",
    "2 cups spinach, roughly chopped",
]


def gathering_html() -> str:
    return _HTML_PATH.read_text()


def _payload(chicken: list[str], sauce: list[str], instructions: list[str]) -> dict:
    return {
        "is_recipe": True,
        "name": GATHERING_DISH,
        "ingredients": chicken + sauce,
        "instructions": instructions,
        "ingredient_sections": [
            {"title": GATHERING_SECTION_TITLES[0], "items": chicken},
            {"title": GATHERING_SECTION_TITLES[1], "items": sauce},
        ],
        "recipe_yield": None,
        "recipe_cuisine": None,
        "reason": None,
    }


def gathering_payload_verbatim() -> dict:
    return _payload(_CHICKEN, _SAUCE, _INSTRUCTIONS)


def gathering_payload_paraphrased() -> dict:
    return _payload(_CHICKEN, _SAUCE, _PARAPHRASED_INSTRUCTIONS)


def gathering_payload_normalized_units() -> dict:
    return _payload(_NORMALIZED_CHICKEN, _NORMALIZED_SAUCE, _INSTRUCTIONS)


def not_recipe_payload(reason: str = "The page is a list of recipe links.") -> dict:
    return {
        "is_recipe": False,
        "name": None,
        "ingredients": [],
        "instructions": [],
        "ingredient_sections": None,
        "recipe_yield": None,
        "recipe_cuisine": None,
        "reason": reason,
    }


def gemini_body(payload: dict) -> dict:
    """Wrap a recipe payload the way generateContent returns it."""
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}
