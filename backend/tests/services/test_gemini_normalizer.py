import json

import pytest
from pydantic import ValidationError

from app.schemas.extract import NormalizedRecipe
from app.services.gemini.prompt import (
    MAX_SERIALIZED_PAYLOAD_CHARS,
    build_gemini_prompt,
)
from app.services.gemini.types import GeminiRecipeResult, RawExtractionPayload


def _recipe() -> NormalizedRecipe:
    return NormalizedRecipe(
        name="Garlic Noodles",
        recipeYield="2 servings",
        cookTime=None,
        recipeCuisine=None,
        nutrition=None,
        ingredients=["8 oz noodles", "2 tbsp butter"],
        ingredientSections=None,
        instructions=["Boil noodles.", "Toss with butter."],
    )


def test_overlong_youtube_description_is_truncated_and_warning_added():
    payload = RawExtractionPayload(
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=abc123",
        description="a" * 20_100,
    )

    prompt = build_gemini_prompt(payload)

    assert len(prompt.payload["description"]) == 20_000
    assert any(
        "description" in warning and "truncated" in warning
        for warning in prompt.warnings
    )


def test_json_ld_blocks_are_capped_at_10_and_warning_added():
    payload = RawExtractionPayload(
        source_type="json_ld",
        source_url="https://example.com/recipe",
        json_ld_blocks=[{"name": f"Recipe {index}"} for index in range(12)],
    )

    prompt = build_gemini_prompt(payload)

    assert len(prompt.payload["json_ld_blocks"]) == 10
    assert any("JSON-LD blocks" in warning and "10" in warning for warning in prompt.warnings)


def test_long_string_inside_json_ld_block_is_truncated_and_warning_added():
    payload = RawExtractionPayload(
        source_type="json_ld",
        source_url="https://example.com/recipe",
        json_ld_blocks=[{"recipeIngredient": ["flour", "x" * 10_100]}],
    )

    prompt = build_gemini_prompt(payload)

    assert len(prompt.payload["json_ld_blocks"][0]["recipeIngredient"][1]) == 10_000
    assert any(
        "JSON-LD string" in warning and "truncated" in warning
        for warning in prompt.warnings
    )


def test_serialized_payload_is_capped_and_warning_added():
    payload = RawExtractionPayload(
        source_type="json_ld",
        source_url="https://example.com/recipe",
        metadata={"notes": "x" * 70_000},
    )

    prompt = build_gemini_prompt(payload)

    serialized_payload = json.dumps(prompt.payload, ensure_ascii=False, sort_keys=True)
    assert len(serialized_payload) <= MAX_SERIALIZED_PAYLOAD_CHARS
    assert any(
        "Serialized payload" in warning and "truncated" in warning
        for warning in prompt.warnings
    )


def test_oversized_json_ld_payload_keeps_first_block_content():
    payload = RawExtractionPayload(
        source_type="json_ld",
        source_url="https://example.com/recipe",
        json_ld_blocks=[
            {
                "@type": "Recipe",
                "name": "Keep Me",
                "recipeIngredient": ["1 cup flour", "x" * 10_000],
            },
            {"@type": "Recipe", "name": "Drop Me", "recipeIngredient": ["y" * 10_000]},
            {"@type": "Recipe", "name": "Drop Me Too", "recipeIngredient": ["z" * 10_000]},
            {"@type": "Recipe", "name": "Also Drop", "recipeIngredient": ["w" * 10_000]},
            {"@type": "Recipe", "name": "Drop Last", "recipeIngredient": ["v" * 10_000]},
            {"@type": "Recipe", "name": "Drop End", "recipeIngredient": ["u" * 10_000]},
        ],
    )

    prompt = build_gemini_prompt(payload)

    serialized_payload = json.dumps(prompt.payload, ensure_ascii=False, sort_keys=True)
    assert len(serialized_payload) <= MAX_SERIALIZED_PAYLOAD_CHARS
    assert prompt.payload["json_ld_blocks"]
    assert prompt.payload["json_ld_blocks"][0]["name"] == "Keep Me"
    assert "1 cup flour" in prompt.payload["json_ld_blocks"][0]["recipeIngredient"]
    assert any("JSON-LD blocks dropped" in warning for warning in prompt.warnings)


def test_single_oversized_json_ld_block_is_reduced_but_kept():
    payload = RawExtractionPayload(
        source_type="json_ld",
        source_url="https://example.com/recipe",
        json_ld_blocks=[
            {
                "@type": "Recipe",
                "name": "Big Recipe",
                "recipeIngredient": [
                    "1 cup flour",
                    "2 tbsp sugar",
                    "x" * 10_000,
                    "y" * 10_000,
                    "z" * 10_000,
                    "w" * 10_000,
                    "v" * 10_000,
                    "u" * 10_000,
                    "t" * 10_000,
                ],
            }
        ],
    )

    prompt = build_gemini_prompt(payload)

    serialized_payload = json.dumps(prompt.payload, ensure_ascii=False, sort_keys=True)
    assert len(serialized_payload) <= MAX_SERIALIZED_PAYLOAD_CHARS
    assert prompt.payload["json_ld_blocks"]
    assert prompt.payload["json_ld_blocks"][0]["name"] == "Big Recipe"
    assert "1 cup flour" in prompt.payload["json_ld_blocks"][0]["recipeIngredient"]
    assert any("Remaining JSON-LD block" in warning for warning in prompt.warnings)


def test_prompt_text_marks_raw_data_as_untrusted_input():
    payload = RawExtractionPayload(
        source_type="json_ld",
        source_url="https://example.com/recipe",
    )

    prompt = build_gemini_prompt(payload)

    assert "untrusted input" in "\n".join(prompt.parts).lower()


def test_youtube_prompt_includes_source_url_instruction_rule():
    payload = RawExtractionPayload(
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=abc123",
        description="Ingredients\n- 1 cup rice",
    )

    prompt = build_gemini_prompt(payload)

    text = "\n".join(prompt.parts)
    assert "instructions must be exactly [source_url]" in text
    assert "https://www.youtube.com/watch?v=abc123" in text


def test_gemini_recipe_result_validates_normalized_recipe_and_confidence_bounds():
    result = GeminiRecipeResult(recipes=[_recipe()], confidence=0.75)

    assert result.recipes[0].name == "Garlic Noodles"
    assert result.confidence == 0.75
    assert result.warnings == []

    with pytest.raises(ValidationError):
        GeminiRecipeResult(recipes=[_recipe()], confidence=1.1)
