from __future__ import annotations

import asyncio

from app.services.instagram.creator_site_lookup import (
    FetchedPage,
    build_search_urls,
    find_creator_site_recipe,
    is_link_hub,
    is_social_or_storefront,
    rank_candidate_anchors,
    rank_profile_links,
    unwrap_instagram_redirect,
)
from app.services.public_web import PublicWebError


# --- Pure function behavior -------------------------------------------------


def test_rank_profile_links_excludes_social_and_storefront_hosts():
    links = [
        "https://www.instagram.com/tasty/",
        "https://facebook.com/tasty",
        "https://www.amazon.com/shop/tasty",
        "https://tasty.co/",
    ]
    assert rank_profile_links(links) == ["https://tasty.co/"]


def test_rank_profile_links_prefers_food_signal_domains_over_hubs_and_generic():
    links = [
        "https://janesmith.com/",
        "https://linktr.ee/janesmith",
        "https://janeskitchen.com/",
    ]
    ranked = rank_profile_links(links)
    assert ranked == [
        "https://janeskitchen.com/",
        "https://linktr.ee/janesmith",
        "https://janesmith.com/",
    ]


def test_rank_profile_links_dedupes_and_caps_at_three():
    links = [
        "https://cook.example/",
        "https://cook.example/",
        "https://bake.example/",
        "https://eats.example/",
        "https://food.example/",
    ]
    ranked = rank_profile_links(links)
    assert len(ranked) == 3
    assert len(set(ranked)) == 3


def test_rank_profile_links_rejects_non_https_and_malformed_entries():
    links = ["http://insecure.example/", "not a url", 42, "  ", "https://ok.example/"]
    assert rank_profile_links(links) == ["https://ok.example/"]


def test_unwrap_instagram_redirect_extracts_recognized_target():
    wrapped = "https://l.instagram.com/?u=https%3A%2F%2Ftasty.co%2Frecipe&e=1"
    assert unwrap_instagram_redirect(wrapped) == "https://tasty.co/recipe"


def test_unwrap_instagram_redirect_leaves_unrecognized_urls_untouched():
    plain = "https://tasty.co/recipe"
    assert unwrap_instagram_redirect(plain) == plain
    weird = "https://l.instagram.com/no-query"
    assert unwrap_instagram_redirect(weird) == weird


def test_is_social_or_storefront_and_is_link_hub_recognize_known_hosts():
    assert is_social_or_storefront("https://www.instagram.com/tasty/")
    assert is_social_or_storefront("https://sub.amazon.com/x")
    assert not is_social_or_storefront("https://tasty.co/")
    assert is_link_hub("https://linktr.ee/tasty")
    assert is_link_hub("https://bio.site/tasty")
    assert not is_link_hub("https://tasty.co/")


def test_build_search_urls_are_bounded_to_two_known_patterns():
    urls = build_search_urls("tasty.co", "Miso Salmon Rice")
    assert urls == [
        "https://tasty.co/?s=Miso%20Salmon%20Rice",
        "https://tasty.co/search?q=Miso%20Salmon%20Rice",
    ]


# --- Candidate anchor ranking -----------------------------------------------


def test_rank_candidate_anchors_keeps_recipe_permalinks_and_drops_navigation():
    # Mirrors the real Tiffy Cooks search page: the recipe permalink contains no
    # generic food word, while the category listings are full of them.
    html = """
    <html><body>
      <a href="/category/blog/recipes/">Recipes</a>
      <a href="/category/blog/recipes/recipe-by-ingredients/chicken/">Chicken</a>
      <a href="/how-much-money-do-i-make-as-a-food-blogger/">Food blogging</a>
      <a href="/miso-salmon-brothy-rice/">15 Minute Miso Salmon Brothy Rice</a>
    </body></html>
    """

    ranked = rank_candidate_anchors(
        html, "https://tiffycooks.com/", "Miso Salmon Brothy Rice"
    )

    assert ranked == ["https://tiffycooks.com/miso-salmon-brothy-rice/"]


def test_rank_candidate_anchors_orders_by_dish_token_overlap():
    html = """
    <html><body>
      <a href="/salmon-toast/">Salmon Toast</a>
      <a href="/miso-salmon-brothy-rice/">Miso Salmon Brothy Rice</a>
      <a href="/miso-salmon-bowl/">Miso Salmon Bowl</a>
    </body></html>
    """

    ranked = rank_candidate_anchors(
        html, "https://tiffycooks.com/", "Miso Salmon Brothy Rice"
    )

    assert ranked == [
        "https://tiffycooks.com/miso-salmon-brothy-rice/",
        "https://tiffycooks.com/miso-salmon-bowl/",
        "https://tiffycooks.com/salmon-toast/",
    ]


def test_rank_candidate_anchors_drops_zero_overlap_and_requires_a_dish_name():
    html = '<html><body><a href="/pantry-staples/">Pantry Staples</a></body></html>'

    assert rank_candidate_anchors(html, "https://tiffycooks.com/", "Miso Salmon") == []
    assert rank_candidate_anchors(html, "https://tiffycooks.com/", "  ") == []


# --- Orchestrator ------------------------------------------------------------


def _fetcher(pages: dict[str, str], calls: list[str]):
    async def fetch_html(url: str) -> FetchedPage:
        calls.append(url)
        if url not in pages:
            raise PublicWebError("not found")
        return FetchedPage(final_url=url, html=pages[url])

    return fetch_html


def _recipe_page(name: str) -> str:
    return f"""
    <html><head>
    <script type="application/ld+json">
    {{"@context":"https://schema.org","@type":"Recipe","name":"{name}",
      "recipeIngredient":["1 cup flour"],"recipeInstructions":["Mix it."]}}
    </script>
    </head><body></body></html>
    """


def test_find_creator_site_recipe_matches_via_direct_profile_link_search():
    calls: list[str] = []
    pages = {
        "https://tasty.co/?s=Miso%20Salmon%20Rice": (
            '<html><body><a href="https://tasty.co/recipe/miso-salmon-rice">'
            "Miso Salmon Rice</a></body></html>"
        ),
        "https://tasty.co/recipe/miso-salmon-rice": _recipe_page("Miso Salmon Rice"),
    }
    fetch_html = _fetcher(pages, calls)

    result = asyncio.run(
        find_creator_site_recipe(
            ["https://tasty.co/"], "Miso Salmon Rice", fetch_html=fetch_html
        )
    )

    assert result is not None
    assert result.recipes[0].name == "Miso Salmon Rice"
    assert result.final_url == "https://tasty.co/recipe/miso-salmon-rice"


def test_find_creator_site_recipe_traverses_one_hub_page():
    calls: list[str] = []
    pages = {
        "https://linktr.ee/tasty": (
            '<html><body><a href="https://tasty.co/recipe/miso">Miso Recipe</a>'
            '<a href="https://instagram.com/tasty">Instagram</a></body></html>'
        ),
        "https://tasty.co/recipe/miso": _recipe_page("Miso Salmon Brothy Rice"),
    }
    fetch_html = _fetcher(pages, calls)

    result = asyncio.run(
        find_creator_site_recipe(
            ["https://linktr.ee/tasty"],
            "Miso Salmon Brothy Rice",
            fetch_html=fetch_html,
        )
    )

    assert result is not None
    assert result.recipes[0].name == "Miso Salmon Brothy Rice"
    assert "https://instagram.com/tasty" not in calls


def test_find_creator_site_recipe_never_fetches_off_domain_or_unregistered_hosts():
    calls: list[str] = []
    pages = {
        "https://tasty.co/?s=Rice%20Bowl": (
            '<html><body>'
            '<a href="https://tasty.co/recipe/rice-bowl">Rice Bowl Recipe</a>'
            '<a href="https://evil.example/recipe/rice-bowl">Rice Bowl Recipe</a>'
            "</body></html>"
        ),
        "https://tasty.co/recipe/rice-bowl": _recipe_page("Rice Bowl"),
        "https://evil.example/recipe/rice-bowl": _recipe_page("Rice Bowl"),
    }
    fetch_html = _fetcher(pages, calls)

    asyncio.run(
        find_creator_site_recipe(
            ["https://tasty.co/"], "Rice Bowl", fetch_html=fetch_html
        )
    )

    assert "https://evil.example/recipe/rice-bowl" not in calls
    assert all("sitemap" not in call for call in calls)


def test_find_creator_site_recipe_returns_none_when_multiple_pages_match():
    calls: list[str] = []
    pages = {
        "https://tasty.co/?s=Rice%20Bowl": (
            '<html><body>'
            '<a href="https://tasty.co/recipe/rice-bowl-1">Rice Bowl Recipe</a>'
            '<a href="https://tasty.co/recipe/rice-bowl-2">Rice Bowl Recipe</a>'
            "</body></html>"
        ),
        "https://tasty.co/recipe/rice-bowl-1": _recipe_page("Rice Bowl"),
        "https://tasty.co/recipe/rice-bowl-2": _recipe_page("Rice Bowl"),
    }
    fetch_html = _fetcher(pages, calls)

    result = asyncio.run(
        find_creator_site_recipe(
            ["https://tasty.co/"], "Rice Bowl", fetch_html=fetch_html
        )
    )

    assert result is None


def test_find_creator_site_recipe_returns_none_when_no_dish_name():
    calls: list[str] = []
    fetch_html = _fetcher({}, calls)

    result = asyncio.run(
        find_creator_site_recipe(["https://tasty.co/"], "  ", fetch_html=fetch_html)
    )

    assert result is None
    assert calls == []


def test_find_creator_site_recipe_respects_candidate_page_cap():
    calls: list[str] = []
    search_anchors = "".join(
        f'<a href="https://tasty.co/recipe/r{i}">Rice Bowl Recipe {i}</a>'
        for i in range(10)
    )
    pages = {
        "https://tasty.co/?s=Rice%20Bowl": f"<html><body>{search_anchors}</body></html>",
    }
    for i in range(10):
        pages[f"https://tasty.co/recipe/r{i}"] = _recipe_page(f"Rice Bowl Recipe {i}")

    fetch_html = _fetcher(pages, calls)

    asyncio.run(
        find_creator_site_recipe(
            ["https://tasty.co/"], "Rice Bowl", fetch_html=fetch_html
        )
    )

    assert len(calls) <= 5


def test_find_creator_site_recipe_prefers_search_pages_over_landing_page_anchors():
    calls: list[str] = []
    hub_anchors = "".join(
        f'<a href="https://tasty.co/recipe/unrelated-{i}">Some Recipe {i}</a>'
        for i in range(5)
    )
    pages = {
        "https://linktr.ee/tasty": f"<html><body>{hub_anchors}</body></html>",
        # The search page carries the real match; landing-page anchors alone
        # (5 of them) exhaust the page-budget before ever reaching it if
        # landing links are queued ahead of search links.
        "https://tasty.co/?s=Rice%20Bowl": _recipe_page("Rice Bowl"),
    }
    for i in range(5):
        pages[f"https://tasty.co/recipe/unrelated-{i}"] = _recipe_page(f"Some Recipe {i}")

    fetch_html = _fetcher(pages, calls)

    result = asyncio.run(
        find_creator_site_recipe(
            ["https://linktr.ee/tasty"], "Rice Bowl", fetch_html=fetch_html
        )
    )

    assert result is not None
    assert result.recipes[0].name == "Rice Bowl"


def test_find_creator_site_recipe_returns_none_when_profile_links_are_only_social():
    calls: list[str] = []
    fetch_html = _fetcher({}, calls)

    result = asyncio.run(
        find_creator_site_recipe(
            ["https://www.instagram.com/tasty/", "https://facebook.com/tasty"],
            "Rice Bowl",
            fetch_html=fetch_html,
        )
    )

    assert result is None
    assert calls == []
