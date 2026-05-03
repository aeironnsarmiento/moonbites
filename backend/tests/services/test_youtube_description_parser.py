from app.schemas.extract import IngredientSection
from app.services.youtube.description_parser import (
    extract_ranked_recipe_urls,
    parse_youtube_description,
)


def test_parse_youtube_description_extracts_header_sections():
    parsed = parse_youtube_description(
        title="Garlic Noodles",
        description="""
Ingredients
- 8 oz noodles
- 2 tbsp butter

Instructions
1. Boil noodles for 8 minutes.
2. Toss noodles with butter.
""",
    )

    assert parsed.is_complete is True
    assert parsed.raw_recipe["recipeIngredient"] == ["8 oz noodles", "2 tbsp butter"]
    assert parsed.raw_recipe["recipeInstructions"] == [
        "Boil noodles for 8 minutes.",
        "Toss noodles with butter.",
    ]


def test_parse_youtube_description_preserves_for_the_sections():
    parsed = parse_youtube_description(
        title="Tacos",
        description="""
For the sauce
- 1 cup yogurt
- 1 tbsp lime juice

For serving
- 8 tortillas
- 1 cup cilantro

Method
1. Stir sauce for 1 minute.
2. Fill tortillas and serve.
""",
    )

    assert parsed.is_complete is True
    assert parsed.raw_recipe["ingredientSections"] == [
        {"name": "For the sauce", "recipeIngredient": ["1 cup yogurt", "1 tbsp lime juice"]},
        {"name": "For serving", "recipeIngredient": ["8 tortillas", "1 cup cilantro"]},
    ]
    assert parsed.ingredient_sections == [
        IngredientSection(title="For the sauce", items=["1 cup yogurt", "1 tbsp lime juice"]),
        IngredientSection(title="For serving", items=["8 tortillas", "1 cup cilantro"]),
    ]


def test_parse_youtube_description_stops_at_social_content():
    parsed = parse_youtube_description(
        title="Soup",
        description="""
Ingredients:
- 2 cups stock
- 1 tsp salt
Subscribe for more recipes
- merch link

Directions:
1. Heat stock for 10 minutes.
2. Season and serve.
Instagram @example
""",
    )

    assert parsed.raw_recipe["recipeIngredient"] == ["2 cups stock", "1 tsp salt"]
    assert parsed.raw_recipe["recipeInstructions"] == [
        "Heat stock for 10 minutes.",
        "Season and serve.",
    ]


def test_parse_youtube_description_classifies_lines_without_headers():
    parsed = parse_youtube_description(
        title="Pancakes",
        description="""
- 1 cup flour
- 2 tbsp sugar
- 1 cup milk
Mix flour and milk for 1 minute.
Cook pancakes at 350F until golden.
""",
    )

    assert parsed.is_complete is True
    assert parsed.raw_recipe["recipeIngredient"] == [
        "1 cup flour",
        "2 tbsp sugar",
        "1 cup milk",
    ]
    assert parsed.raw_recipe["recipeInstructions"] == [
        "Mix flour and milk for 1 minute.",
        "Cook pancakes at 350F until golden.",
    ]


def test_parse_youtube_description_handles_sectioned_ingredients_without_instructions():
    parsed = parse_youtube_description(
        title="Honey Garlic Salmon Meal Prep",
        description="""
Recipe -
Makes - 5 (1 litre) Containers

Ingredients -

Salmon -
1 tsp (5ml) - Olive Oil
1.25kg (2.7lbs) - Fresh Salmon, Cut Into 5 Fillets, Skin on or off
1 tsp (2.5g) - Garlic Powder
1 tsp (2.5g) - Smoked or Regular Paprika
Seasoning To Taste

Honey Garlic Sauce -
2 Tbsp (28g) - Clarified Butter, Regular Unsalted Butter or Olive Oil (40ml)
6 - Garlic Cloves, Minced
2 Tbsp (40ml) - Chicken or Vegetable Stock
1 1/2 Tbsp (30ml) - Light Soy Sauce
1/2 Lemon, Juiced
5 Tbsp (70g) - Honey
Seasoning To Taste

Rice -
350g (12.3oz) - Basmati Rice, Washed
700ml (700g) - Cold Water
Salt To Taste

Broccoli -
1 Tbsp (20ml) - Peanut Oil
2 Heads - Broccoli, Cut Into Florets, Stems Trimmed
Pinch of Sesame Seeds (Optional)
Seasoning To Taste

Nutritional Guide -

Portion Size 450g - 1lb
Calories 636
Total Fat 18.6g
Saturated Fat 5g
Cholesterol 100mg
Sodium 439mg
Total Carbohydrate 70.2g
Dietary Fiber 2.2g
Sugar 12.6g
Protein 45.6g
""",
        source_url="https://youtu.be/salmon12345",
    )

    assert parsed.is_complete is True
    assert parsed.raw_recipe["recipeYield"] == "5 (1 litre) Containers"
    assert parsed.raw_recipe["recipeInstructions"] == ["https://youtu.be/salmon12345"]
    assert [section.title for section in parsed.ingredient_sections] == [
        "Salmon",
        "Honey Garlic Sauce",
        "Rice",
        "Broccoli",
    ]
    assert parsed.raw_recipe["recipeIngredient"][:4] == [
        "1 tsp (5ml) - Olive Oil",
        "1.25kg (2.7lbs) - Fresh Salmon, Cut Into 5 Fillets, Skin on or off",
        "1 tsp (2.5g) - Garlic Powder",
        "1 tsp (2.5g) - Smoked or Regular Paprika",
    ]
    assert "Calories 636" not in parsed.raw_recipe["recipeIngredient"]
    assert parsed.raw_recipe["nutrition"] == {
        "servingSize": "450g - 1lb",
        "calories": "636",
        "fatContent": "18.6g",
        "saturatedFatContent": "5g",
        "cholesterolContent": "100mg",
        "sodiumContent": "439mg",
        "carbohydrateContent": "70.2g",
        "fiberContent": "2.2g",
        "sugarContent": "12.6g",
        "proteinContent": "45.6g",
    }


def test_parse_youtube_description_detects_generic_context_headings():
    parsed = parse_youtube_description(
        title="Chicken Bowls",
        description="""
Ingredients

Marinade
2 tbsp soy sauce
1 tbsp honey

Chicken -
1 lb chicken breast, sliced
1 tsp garlic powder

SAUCE
1 cup yogurt
2 tbsp lemon juice

For serving
2 cups cooked rice
1 cup cucumber, diced

This is one of my favorite dinners.

Directions
1. Cook chicken for 8 minutes.
2. Serve bowls with sauce.
""",
    )

    assert [section.title for section in parsed.ingredient_sections] == [
        "Marinade",
        "Chicken",
        "SAUCE",
        "For serving",
    ]
    assert "This is one of my favorite dinners." not in parsed.raw_recipe[
        "recipeIngredient"
    ]
    assert parsed.raw_recipe["recipeInstructions"] == [
        "Cook chicken for 8 minutes.",
        "Serve bowls with sauce.",
    ]


def test_parse_youtube_description_excludes_nutrition_and_junk_from_ingredients():
    parsed = parse_youtube_description(
        title="Rice Bowl",
        description="""
Ingredients
1 cup rice
2 tbsp soy sauce

Nutrition
Calories 500
Protein 30g

Follow me on Instagram
https://example.com/not-a-recipe

Steps
1. Cook rice for 20 minutes.
2. Stir in sauce.
""",
    )

    assert parsed.raw_recipe["recipeIngredient"] == ["1 cup rice", "2 tbsp soy sauce"]
    assert parsed.raw_recipe["nutrition"] == {
        "calories": "500",
        "proteinContent": "30g",
    }
    assert parsed.raw_recipe["recipeInstructions"] == [
        "Cook rice for 20 minutes.",
        "Stir in sauce.",
    ]


def test_parse_youtube_description_returns_not_recipe_for_gaming_video():
    parsed = parse_youtube_description(
        title="Shroud CS LAN",
        description="""
Shroud competes in his first CS LAN Tournament in nearly a DECADE.

SECRET PROMO CODE ON ALL LOGITECH PRODUCTS: shroud
https://www.logitechg.com

THE PERFECT PC - https://maingear.com/shroud-ref

► Follow me!
TWITTER →   / shroud
TWITCH →   / shroud

#shroud #gaming #cs2
""",
        source_url="https://youtu.be/shroud123",
    )

    assert parsed.is_complete is False
    assert parsed.parse_status == "not_recipe"
    assert parsed.parse_reason is not None
    assert parsed.ingredients == []
    assert parsed.instructions == []


def test_parse_youtube_description_url_fallback_blocked_when_description_is_junk():
    parsed = parse_youtube_description(
        title="Sponsored Cooking Stream",
        description="""
SECRET PROMO CODE: cook
https://www.sponsor.com

► Follow me!
TWITTER →   / cook
TWITCH →   / cook
INSTAGRAM →   / cook
FACEBOOK →   / cook

#sponsored #stream
""",
        source_url="https://youtu.be/spam123",
    )

    assert parsed.parse_status == "not_recipe"
    assert parsed.instructions == []


def test_parse_youtube_description_url_fallback_applied_when_description_is_clean():
    parsed = parse_youtube_description(
        title="Rice Bowl",
        description="""
Ingredients
Rice -
1 cup rice
2 tbsp soy sauce
1 tsp salt
""",
        source_url="https://youtu.be/rice123",
    )

    assert parsed.parse_status == "recipe"
    assert parsed.is_complete is True
    assert parsed.instructions == ["https://youtu.be/rice123"]


def test_extract_ranked_recipe_urls_prefers_recipe_context_and_skips_social_links():
    urls = extract_ranked_recipe_urls(
        """
Follow me: https://instagram.com/cook
Gear: https://amazon.com/example
Full recipe: https://example.com/best-soup?utm_source=youtube
Website: https://cookbook.test/soup
Watch more: https://youtu.be/abc12345678
"""
    )

    assert urls == [
        "https://example.com/best-soup?utm_source=youtube",
        "https://cookbook.test/soup",
    ]
