from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.schemas.extract import ParseStatus
from app.services.blog.extractor import parse_recipes_from_html
from app.services.blog.page_fallback import (
    FallbackOutcome,
    apply_page_fallback,
    recover_recipe_from_page,
)
from app.services.extraction_types import ExtractionResult
from app.services.gemini.recipe_parser import ParsedCaption
from backend.tests.fixtures.gathering_page import (
    GATHERING_DISH,
    GATHERING_URL,
    gathering_html,
)


FALLBACK_LOGGER = "app.services.blog.page_fallback"


def _gathering_page() -> ExtractionResult:
    return parse_recipes_from_html(
        gathering_html(), source_url=GATHERING_URL, final_url=GATHERING_URL
    )


def _incomplete_json_ld_page() -> ExtractionResult:
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@type": "Recipe", "name": "Lemon Bars", "recipeIngredient": ["1 cup flour"]}'
        "</script></head><body><main><p>1 cup flour</p><p>Bake.</p></main></body></html>"
    )
    url = "https://www.bars.test/lemon"
    return parse_recipes_from_html(html, source_url=url, final_url=url)


def _complete(name: str = GATHERING_DISH) -> ParsedCaption:
    return ParsedCaption(
        raw_recipe={
            "@type": "Recipe",
            "name": name,
            "recipeIngredient": ["1 tsp. cumin", "1/2 tsp. paprika"],
            "recipeInstructions": ["Add cumin.", "Add paprika."],
        },
        ingredients=["1 tsp. cumin", "1/2 tsp. paprika"],
        instructions=["Add cumin.", "Add paprika."],
        is_complete=True,
        parse_status="recipe",
        parse_reason=None,
        candidate_name=name,
    )


def _not_recipe(reason: str = "Not a recipe page.") -> ParsedCaption:
    return ParsedCaption(
        raw_recipe={},
        ingredients=[],
        instructions=[],
        is_complete=False,
        parse_status="not_recipe",
        parse_reason=reason,
    )


def _recover(page: ExtractionResult, parse: AsyncMock):
    return asyncio.run(recover_recipe_from_page(page, parse=parse))


def _records(caplog) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == FALLBACK_LOGGER]


def test_recipe_outcome_passes_page_title_and_text_to_the_parser():
    parse = AsyncMock(return_value=_complete())

    result = _recover(_gathering_page(), parse)

    assert result.outcome is FallbackOutcome.RECIPE
    assert result.recipe is not None and result.recipe.name == GATHERING_DISH
    parse.assert_awaited_once()
    kwargs = parse.await_args.kwargs
    assert kwargs["title"] == GATHERING_DISH
    assert "Chickem" in kwargs["page_text"]
    assert kwargs["source_url"] == GATHERING_URL


def test_not_recipe_outcome_carries_the_parser_reason():
    result = _recover(_gathering_page(), AsyncMock(return_value=_not_recipe("A listing page.")))

    assert result.outcome is FallbackOutcome.NOT_RECIPE
    assert result.recipe is None
    assert result.reason == "A listing page."


@pytest.mark.parametrize(
    "error",
    [
        HTTPException(status_code=503, detail="Caption parsing is not configured"),
        HTTPException(status_code=429, detail="The recipe parser is busy"),
        HTTPException(status_code=502, detail="The recipe parser returned HTTP 500"),
        HTTPException(status_code=504, detail="Request to the recipe parser timed out"),
        RuntimeError("unexpected parser bug"),
    ],
    ids=["unconfigured", "rate-limited", "server-error", "timeout", "unexpected"],
)
def test_every_gemini_failure_is_gemini_unavailable_and_never_raises(error):
    result = _recover(_gathering_page(), AsyncMock(side_effect=error))

    assert result.outcome is FallbackOutcome.GEMINI_UNAVAILABLE
    assert result.recipe is None


def test_page_without_page_text_cannot_fall_back():
    page = ExtractionResult(
        source_url="https://x.test",
        final_url="https://x.test",
        title=None,
        image_url=None,
        recipe_node_count=0,
        recipes=[],
    )

    with pytest.raises(ValueError):
        _recover(page, AsyncMock())


def test_r12_logs_host_trigger_and_outcome_for_a_saved_fallback(caplog):
    with caplog.at_level(logging.INFO, logger=FALLBACK_LOGGER):
        _recover(_gathering_page(), AsyncMock(return_value=_complete()))

    (record,) = _records(caplog)
    assert record.levelno == logging.INFO
    assert record.fallback_host == "thegatheringpage.com"
    assert record.fallback_trigger == "missing_json_ld"
    assert record.fallback_outcome == "recipe"
    assert record.getMessage() == (
        "Blog Gemini fallback host=thegatheringpage.com "
        "trigger=missing_json_ld outcome=recipe"
    )


def test_r12_logs_incomplete_json_ld_trigger_and_not_recipe_outcome(caplog):
    with caplog.at_level(logging.INFO, logger=FALLBACK_LOGGER):
        _recover(_incomplete_json_ld_page(), AsyncMock(return_value=_not_recipe()))

    (record,) = _records(caplog)
    assert record.fallback_host == "www.bars.test"
    assert record.fallback_trigger == "incomplete_json_ld"
    assert record.fallback_outcome == "not_recipe"


def test_r12_logs_gemini_unavailable(caplog):
    with caplog.at_level(logging.INFO, logger=FALLBACK_LOGGER):
        _recover(_gathering_page(), AsyncMock(side_effect=HTTPException(status_code=429)))

    (record,) = _records(caplog)
    assert record.fallback_outcome == "gemini_unavailable"


def test_apply_folds_a_recipe_into_the_page_result():
    page = _gathering_page()

    result = asyncio.run(apply_page_fallback(page, parse=AsyncMock(return_value=_complete())))

    assert [recipe.name for recipe in result.recipes] == [GATHERING_DISH]
    assert result.parse_status is ParseStatus.RECIPE
    assert result.title == page.title
    assert result.image_url == page.image_url


def test_apply_turns_a_failed_quality_bar_into_not_recipe():
    result = asyncio.run(
        apply_page_fallback(_gathering_page(), parse=AsyncMock(return_value=_not_recipe("Nope.")))
    )

    assert result.recipes == []
    assert result.parse_status is ParseStatus.NOT_RECIPE
    assert result.parse_reason == "Nope."


def test_apply_returns_the_page_untouched_when_gemini_is_unavailable():
    page = _gathering_page()

    result = asyncio.run(
        apply_page_fallback(page, parse=AsyncMock(side_effect=HTTPException(status_code=503)))
    )

    assert result is page


def test_apply_never_calls_gemini_for_a_page_with_recipes():
    parse = AsyncMock()
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@type": "Recipe", "name": "Lemon Bars", "recipeIngredient": ["flour", "lemon"],'
        ' "recipeInstructions": ["Bake."]}'
        "</script></head><body></body></html>"
    )
    page = parse_recipes_from_html(html, source_url="https://x.test", final_url="https://x.test")

    result = asyncio.run(apply_page_fallback(page, parse=parse))

    assert result is page
    parse.assert_not_called()
