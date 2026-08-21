from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.extract import NormalizedRecipe
from app.services.extraction_types import ExtractionResult, ParseStatus
from app.services.gemini.recipe_parser import ParsedCaption
from app.services.social.caption_recipe import (
    MAX_CAPTION_LINKS,
    CaptionPost,
    extract_recipe_from_caption,
)


def _post(caption: str, *, image_url: str | None = None) -> CaptionPost:
    return CaptionPost(
        source_url="https://social.example/post/1",
        final_url="https://social.example/@chef/post/1",
        title="Chef posts a dish",
        caption=caption,
        image_url=image_url,
    )


def _complete(name: str = "Garlic Noodles") -> ParsedCaption:
    return ParsedCaption(
        raw_recipe={
            "@type": "Recipe",
            "name": name,
            "recipeIngredient": ["8 oz noodles", "2 tbsp butter"],
            "recipeInstructions": ["Boil noodles.", "Toss with butter."],
        },
        ingredients=["8 oz noodles", "2 tbsp butter"],
        instructions=["Boil noodles.", "Toss with butter."],
        is_complete=True,
        parse_status="recipe",
        parse_reason=None,
    )


def _incomplete(candidate_name: str | None) -> ParsedCaption:
    return ParsedCaption(
        raw_recipe={},
        ingredients=[],
        instructions=[],
        is_complete=False,
        parse_status="not_recipe",
        parse_reason="The recipe lives on a linked page.",
        candidate_name=candidate_name,
    )


def _page(url: str, *names: str, image_url: str | None = None) -> ExtractionResult:
    return ExtractionResult(
        source_url=url,
        final_url=url,
        title=names[0] if names else None,
        image_url=image_url,
        recipe_node_count=len(names),
        recipes=[
            NormalizedRecipe(
                name=name, ingredients=["1 cup flour"], instructions=["Mix it."]
            )
            for name in names
        ],
    )


def _run(post: CaptionPost, *, gemini, blog=None, mirror=False):
    with (
        patch(
            "app.services.social.caption_recipe.parse_caption_with_gemini", new=gemini
        ),
        patch(
            "app.services.social.caption_recipe.extract_blog_recipes_from_safe_url",
            new=blog or AsyncMock(),
        ),
    ):
        return asyncio.run(
            extract_recipe_from_caption(
                post,
                not_recipe_reason="No recipe here.",
                mirror_provider_thumbnail=mirror,
            )
        )


def test_caption_complete_post_never_follows_links():
    gemini = AsyncMock(return_value=_complete())
    blog = AsyncMock()

    result = _run(_post("Full recipe: https://blog.example/pasta"), gemini=gemini, blog=blog)

    assert result.parse_status == ParseStatus.RECIPE
    assert result.recipes[0].name == "Garlic Noodles"
    assert result.final_url == "https://social.example/@chef/post/1"
    blog.assert_not_awaited()


def test_single_matching_link_becomes_the_linked_recipe():
    gemini = AsyncMock(return_value=_incomplete("Miso Salmon Rice"))
    blog = AsyncMock(
        return_value=_page("https://blog.example/miso", "Miso Salmon Rice")
    )

    result = _run(_post("Recipe: https://blog.example/miso"), gemini=gemini, blog=blog)

    assert result.parse_status == ParseStatus.RECIPE
    assert result.recipes[0].name == "Miso Salmon Rice"
    assert result.final_url == "https://blog.example/miso"
    assert result.source_url == "https://social.example/post/1"


def test_two_plausible_links_are_no_match_at_all():
    # The rule that separates this from "first link wins": two candidates
    # naming the dish is ambiguous, and a guess is worse than no import.
    gemini = AsyncMock(return_value=_incomplete("Miso Salmon Rice"))
    blog = AsyncMock(
        side_effect=[
            _page("https://a.example/miso", "Miso Salmon Rice"),
            _page("https://b.example/miso", "Easy Miso Salmon Rice"),
        ]
    )
    caption = "Recipe: https://a.example/miso and https://b.example/miso"

    result = _run(_post(caption), gemini=gemini, blog=blog)

    assert result.parse_status == ParseStatus.NOT_RECIPE
    assert result.recipes == []
    assert blog.await_count == 2


def test_only_the_matched_recipe_is_returned_from_a_multi_recipe_page():
    gemini = AsyncMock(return_value=_incomplete("Miso Salmon Rice"))
    blog = AsyncMock(
        return_value=_page(
            "https://blog.example/roundup", "Miso Salmon Rice", "Chocolate Cake"
        )
    )

    result = _run(_post("Recipe: https://blog.example/roundup"), gemini=gemini, blog=blog)

    assert [recipe.name for recipe in result.recipes] == ["Miso Salmon Rice"]


def test_no_dish_name_means_no_link_resolution():
    gemini = AsyncMock(return_value=_incomplete(None))
    blog = AsyncMock()

    result = _run(_post("Recipe: https://blog.example/miso"), gemini=gemini, blog=blog)

    assert result.parse_status == ParseStatus.NOT_RECIPE
    assert result.parse_reason == "The recipe lives on a linked page."
    blog.assert_not_awaited()


def test_gemini_failure_reraises_without_following_links():
    gemini = AsyncMock(side_effect=HTTPException(status_code=503, detail="down"))
    blog = AsyncMock()

    with pytest.raises(HTTPException) as error:
        _run(_post("Recipe: https://blog.example/miso"), gemini=gemini, blog=blog)

    assert error.value.status_code == 503
    blog.assert_not_awaited()


def test_link_following_stops_at_the_cap():
    gemini = AsyncMock(return_value=_incomplete("Miso Salmon Rice"))
    blog = AsyncMock(return_value=_page("https://blog.example/x", "Something Else"))
    caption = "Recipe: " + " ".join(
        f"https://blog{index}.example/miso" for index in range(MAX_CAPTION_LINKS + 4)
    )

    result = _run(_post(caption), gemini=gemini, blog=blog)

    assert blog.await_count == MAX_CAPTION_LINKS
    assert result.parse_status == ParseStatus.NOT_RECIPE


def test_a_failing_link_does_not_abort_the_others():
    gemini = AsyncMock(return_value=_incomplete("Miso Salmon Rice"))
    blog = AsyncMock(
        side_effect=[
            HTTPException(status_code=502, detail="bad gateway"),
            _page("https://b.example/miso", "Miso Salmon Rice"),
        ]
    )
    caption = "Recipe: https://a.example/miso and https://b.example/miso"

    result = _run(_post(caption), gemini=gemini, blog=blog)

    assert result.recipes[0].name == "Miso Salmon Rice"


def test_post_thumbnail_is_mirrored_only_when_the_page_brought_none():
    gemini = AsyncMock(return_value=_incomplete("Miso Salmon Rice"))
    post = _post("Recipe: https://blog.example/miso", image_url="https://cdn.example/t.jpg")

    bare_page = AsyncMock(
        return_value=_page("https://blog.example/miso", "Miso Salmon Rice")
    )
    result = _run(post, gemini=gemini, blog=bare_page, mirror=True)
    assert result.provider_thumbnail_url == "https://cdn.example/t.jpg"
    assert result.image_url == "https://cdn.example/t.jpg"

    imaged_page = AsyncMock(
        return_value=_page(
            "https://blog.example/miso",
            "Miso Salmon Rice",
            image_url="https://blog.example/hero.jpg",
        )
    )
    result = _run(post, gemini=gemini, blog=imaged_page, mirror=True)
    assert result.provider_thumbnail_url is None
    assert result.image_url == "https://blog.example/hero.jpg"


def test_thumbnail_is_not_mirrored_when_the_caller_did_not_ask():
    gemini = AsyncMock(return_value=_complete())
    post = _post("Ingredients: ...", image_url="https://cdn.example/t.jpg")

    result = _run(post, gemini=gemini)

    assert result.provider_thumbnail_url is None
