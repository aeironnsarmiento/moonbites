from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

from app.services.blog.extractor import extract_json_ld_blocks, parse_recipes_from_html
from app.services.blog.page_text import (
    MAX_PAGE_TEXT_CHARS,
    extract_main_text,
    extract_page_title,
)
from app.services.extraction_types import FallbackTrigger


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
GATHERING_URL = "https://thegatheringpage.com/recipes/creamy-tuscan-chicken-skillet"


def _gathering_html() -> str:
    return (FIXTURES / "thegatheringpage_creamy_tuscan_chicken_skillet.html").read_text()


def _title(html: str) -> str | None:
    _, blocks = extract_json_ld_blocks(html)
    return extract_page_title(BeautifulSoup(html, "html.parser"), blocks)


def _text(html: str) -> str:
    return extract_main_text(BeautifulSoup(html, "html.parser"))


def _json_ld(payload: dict) -> str:
    return f'<script type="application/ld+json">{json.dumps(payload)}</script>'


def test_gathering_page_title_is_the_article_headline_not_the_site_brand():
    html = _gathering_html()

    assert BeautifulSoup(html, "html.parser").title.string == "The Gathering Page"
    assert _title(html) == "Creamy Tuscan Chicken Skillet"


def test_gathering_page_main_text_holds_the_recipe_card_without_site_chrome():
    text = _text(_gathering_html())

    assert "Chickem" in text
    assert "Mushrooms & Sun Dried Tomato Sauce" in text
    assert "4 boneless, skinless chicken thighs (~2 lbs)" in text
    assert (
        "Place the chicken on top of the creamy vegetable mixture and serve. Enjoy!"
        in text
    )
    assert "Open Menu" not in text
    assert "Skip to Content" not in text
    assert "function(" not in text
    assert "Get free recipes & wellness tips" not in text


def test_gathering_page_parse_hands_off_page_text_for_the_fallback():
    result = parse_recipes_from_html(
        _gathering_html(), source_url=GATHERING_URL, final_url=GATHERING_URL
    )

    assert result.recipes == []
    assert result.recipe_node_count == 0
    assert result.page_text is not None
    assert result.page_text.title == "Creamy Tuscan Chicken Skillet"
    assert result.page_text.trigger is FallbackTrigger.MISSING_JSON_LD
    assert "Chickem" in result.page_text.text


def test_title_falls_back_to_og_title_then_document_title():
    with_og = (
        '<html><head><title>Doc Title</title>'
        '<meta property="og:title" content="OG Dish"></head><body></body></html>'
    )
    without_og = "<html><head><title>Doc Title</title></head><body></body></html>"

    assert _title(with_og) == "OG Dish"
    assert _title(without_og) == "Doc Title"


def test_title_reads_a_headline_nested_in_a_graph():
    html = (
        "<html><head><title>Brand</title>"
        + _json_ld(
            {
                "@context": "https://schema.org",
                "@graph": [
                    {"@type": "WebSite", "name": "Brand"},
                    {"@type": ["BlogPosting"], "headline": "Lemon Bars"},
                ],
            }
        )
        + "</head><body></body></html>"
    )

    assert _title(html) == "Lemon Bars"


def test_main_text_drops_navigation_asides_footers_and_comment_threads():
    html = """
    <html><body>
      <header><a>Home</a><a>Shop</a></header>
      <nav>Menu Link</nav>
      <article>
        <header><h1>Lemon Bars</h1></header>
        <p>Mix the lemon curd.</p>
        <aside>Related: Brownies</aside>
        <div id="comments"><p>Great recipe! Loved it.</p></div>
        <ol class="comment-list"><li>Another comment</li></ol>
        <footer>Filed under Desserts</footer>
      </article>
    </body></html>
    """

    text = _text(html)

    assert text.splitlines() == ["Lemon Bars", "Mix the lemon curd."]


def test_main_text_drops_the_site_header_when_reading_the_whole_body():
    html = "<html><body><header>Site Brand Menu</header><p>Mix it.</p></body></html>"

    assert _text(html) == "Mix it."


def test_main_text_prefers_main_over_the_rest_of_the_body():
    html = "<html><body><div>Outside</div><main><p>Inside</p></main></body></html>"

    assert _text(html) == "Inside"


def test_main_text_is_capped():
    html = f"<html><body><main><p>{'a' * (MAX_PAGE_TEXT_CHARS + 500)}</p></main></body></html>"

    assert len(_text(html)) == MAX_PAGE_TEXT_CHARS


def test_page_with_a_saveable_json_ld_recipe_carries_no_page_text():
    html = (
        "<html><head>"
        + _json_ld(
            {
                "@type": "Recipe",
                "name": "Lemon Bars",
                "recipeIngredient": ["1 cup flour", "2 lemons"],
                "recipeInstructions": ["Bake it."],
            }
        )
        + "</head><body></body></html>"
    )

    result = parse_recipes_from_html(html, source_url="https://x.test", final_url="https://x.test")

    assert [recipe.name for recipe in result.recipes] == ["Lemon Bars"]
    assert result.page_text is None


def test_incomplete_json_ld_recipe_hands_off_with_the_incomplete_trigger():
    html = (
        "<html><head><title>Lemon Bars</title>"
        + _json_ld(
            {
                "@type": "Recipe",
                "name": "Lemon Bars",
                "recipeIngredient": ["1 cup flour", "2 lemons"],
            }
        )
        + "</head><body><p>Lemon bars are tart.</p></body></html>"
    )

    result = parse_recipes_from_html(html, source_url="https://x.test", final_url="https://x.test")

    assert result.recipes == []
    assert result.recipe_node_count == 1
    assert result.page_text is not None
    assert result.page_text.trigger is FallbackTrigger.INCOMPLETE_JSON_LD
    assert result.page_text.title == "Lemon Bars"


def test_page_with_no_readable_text_carries_no_page_text():
    html = "<html><head><title>Lemon Bars</title></head><body><script>x()</script></body></html>"

    result = parse_recipes_from_html(html, source_url="https://x.test", final_url="https://x.test")

    assert result.recipes == []
    assert result.page_text is None
