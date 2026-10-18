from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.extract import NormalizedRecipe
from app.services.extraction_types import ExtractionResult, ParseStatus
from app.services.gemini.recipe_parser import ParsedCaption
from app.services.import_deadline import Deadline
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


def test_a_link_raising_a_non_http_error_is_skipped():
    gemini = AsyncMock(return_value=_incomplete("Miso Salmon Rice"))
    blog = AsyncMock(
        side_effect=[
            RuntimeError("parser blew up"),
            _page("https://b.example/miso", "Miso Salmon Rice"),
        ]
    )
    caption = "Recipe: https://a.example/miso and https://b.example/miso"

    result = _run(_post(caption), gemini=gemini, blog=blog)

    assert result.recipes[0].name == "Miso Salmon Rice"


# --- Blog Gemini fallback on the matched Linked Recipe page ------------------


def _pages_by_url(pages: dict[str, ExtractionResult]):
    async def fetch(url: str) -> ExtractionResult:
        return pages[url]

    return AsyncMock(side_effect=fetch)


def _gathering_linked_pages():
    from app.services.blog.extractor import parse_recipes_from_html
    from backend.tests.fixtures.gathering_page import GATHERING_URL, gathering_html

    return {
        "https://bakes.example/lemon-bars": _page(
            "https://bakes.example/lemon-bars", "Lemon Bars"
        ),
        GATHERING_URL: parse_recipes_from_html(
            gathering_html(), source_url=GATHERING_URL, final_url=GATHERING_URL
        ),
        "https://shop.example/skillet": parse_recipes_from_html(
            "<html><head><title>Cast Iron Skillet | Shop</title></head>"
            "<body><main><p>Buy a skillet.</p></main></body></html>",
            source_url="https://shop.example/skillet",
            final_url="https://shop.example/skillet",
        ),
    }


def test_ae5_tiktok_caption_linked_page_without_json_ld_becomes_the_linked_recipe():
    """Covers AE5 (R4, R5): three caption links, Gemini runs once, on the match."""
    from app.core.config import Settings
    from backend.tests.fixtures.gathering_page import (
        GATHERING_DISH,
        GATHERING_SECTION_TITLES,
        GATHERING_URL,
        gathering_payload_verbatim,
        gemini_body,
    )

    class _GeminiResponse:
        def json(self):
            return gemini_body(gathering_payload_verbatim())

    settings = Settings(
        request_timeout_seconds=15.0,
        supabase_url=None,
        supabase_publishable_key=None,
        supabase_service_role_key=None,
        supabase_table_name="recipe_imports",
        admin_emails=(),
        cors_origins=(),
        user_agent="test-agent",
        accept_header="text/html",
        accept_language_header="en-US",
        youtube_api_key=None,
        gemini_api_key="gemini-key",
        gemini_rate_limit_per_minute=10,
    )
    gemini_http = AsyncMock(return_value=_GeminiResponse())
    blog = _pages_by_url(_gathering_linked_pages())
    caption = (
        "Lemon bars: https://bakes.example/lemon-bars\n"
        f"Full recipe here: {GATHERING_URL}\n"
        "My skillet: https://shop.example/skillet"
    )

    with (
        patch("app.services.gemini.recipe_parser.get_settings", return_value=settings),
        patch("app.services.gemini.recipe_parser._post_generate_content", new=gemini_http),
    ):
        result = _run(
            _post(caption),
            gemini=AsyncMock(return_value=_incomplete(GATHERING_DISH)),
            blog=blog,
        )

    assert blog.await_count == 3
    gemini_http.assert_awaited_once()
    prompt = gemini_http.await_args.args[1]["contents"][0]["parts"][0]["text"]
    assert f"Page title: {GATHERING_DISH}" in prompt
    assert result.parse_status == ParseStatus.RECIPE
    assert result.final_url == GATHERING_URL
    (recipe,) = result.recipes
    assert recipe.name == GATHERING_DISH
    assert [section.title for section in recipe.ingredientSections] == GATHERING_SECTION_TITLES
    assert len(recipe.instructions) == 8


@pytest.mark.parametrize(
    "page_parse",
    [
        AsyncMock(
            return_value=ParsedCaption(
                raw_recipe={},
                ingredients=[],
                instructions=[],
                is_complete=False,
                parse_status="not_recipe",
                parse_reason="Not a recipe.",
            )
        ),
        AsyncMock(side_effect=HTTPException(status_code=503, detail="not configured")),
    ],
    ids=["not-recipe", "gemini-unavailable"],
)
def test_failed_fallback_on_the_matched_page_ends_as_todays_not_recipe(page_parse):
    """R11: never a new error; the post ends exactly as with no Linked Recipe."""
    from backend.tests.fixtures.gathering_page import GATHERING_DISH, GATHERING_URL

    page_parse.reset_mock()
    with patch("app.services.blog.page_fallback.parse_page_text_with_gemini", new=page_parse):
        result = _run(
            _post(f"Full recipe here: {GATHERING_URL}"),
            gemini=AsyncMock(return_value=_incomplete(GATHERING_DISH)),
            blog=_pages_by_url(_gathering_linked_pages()),
        )

    page_parse.assert_awaited_once()
    assert result.parse_status == ParseStatus.NOT_RECIPE
    assert result.parse_reason == "The recipe lives on a linked page."
    assert result.recipes == []


def test_unmatched_pages_without_json_ld_never_reach_gemini():
    from backend.tests.fixtures.gathering_page import GATHERING_URL

    page_parse = AsyncMock()
    with patch("app.services.blog.page_fallback.parse_page_text_with_gemini", new=page_parse):
        result = _run(
            _post(f"Full recipe here: {GATHERING_URL}"),
            gemini=AsyncMock(return_value=_incomplete("Garlic Noodles")),
            blog=_pages_by_url(_gathering_linked_pages()),
        )

    page_parse.assert_not_called()
    assert result.parse_status == ParseStatus.NOT_RECIPE


def _run_linked_fallback(page_parse, *, deadline, blog=None):
    from backend.tests.fixtures.gathering_page import GATHERING_DISH, GATHERING_URL

    with (
        patch("app.services.blog.page_fallback.parse_page_text_with_gemini", new=page_parse),
        patch(
            "app.services.social.caption_recipe.parse_caption_with_gemini",
            new=AsyncMock(return_value=_incomplete(GATHERING_DISH)),
        ),
        patch(
            "app.services.social.caption_recipe.extract_blog_recipes_from_safe_url",
            new=blog or _pages_by_url(_gathering_linked_pages()),
        ),
    ):
        return asyncio.run(
            extract_recipe_from_caption(
                _post(f"Full recipe here: {GATHERING_URL}"),
                not_recipe_reason="No recipe here.",
                deadline=deadline,
            )
        )


def test_linked_recipe_fallback_is_capped_by_the_request_deadline():
    page_parse = AsyncMock(return_value=_complete())

    result = _run_linked_fallback(page_parse, deadline=Deadline.start(25.0))

    assert result.parse_status == ParseStatus.RECIPE
    # 25s left, 5s held back for persistence, split over two attempts.
    assert 9.0 < page_parse.await_args.kwargs["timeout_seconds"] <= 10.0


def test_slow_link_fetches_leave_no_budget_so_the_post_ends_as_todays_not_recipe():
    """R11: link fetches that spend the budget skip Gemini; no new error."""
    pages = _gathering_linked_pages()

    async def slow_fetch(url: str) -> ExtractionResult:
        await asyncio.sleep(0.2)
        return pages[url]

    page_parse = AsyncMock(return_value=_complete())
    # 1.1s of budget past the 5s persistence reserve, then a 0.2s fetch.
    result = _run_linked_fallback(
        page_parse, deadline=Deadline.start(6.1), blog=AsyncMock(side_effect=slow_fetch)
    )

    page_parse.assert_not_called()
    assert result.parse_status == ParseStatus.NOT_RECIPE
    assert result.parse_reason == "The recipe lives on a linked page."
    assert result.recipes == []


def test_without_a_deadline_the_request_budget_starts_in_the_pipeline():
    page_parse = AsyncMock(return_value=_complete())

    _run_linked_fallback(page_parse, deadline=None)

    # The default 45s budget: 5s held back, split over two attempts.
    assert 19.0 < page_parse.await_args.kwargs["timeout_seconds"] <= 20.0
