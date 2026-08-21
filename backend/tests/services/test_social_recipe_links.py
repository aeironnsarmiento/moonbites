from app.services.social.recipe_links import extract_ranked_recipe_urls


def test_recipe_link_ranking_preserves_existing_order_and_cleanup():
    urls = extract_ranked_recipe_urls(
        """
Website: https://plain.example/page.
Recipe here: https://cookbook.test/soup,
Full recipe: https://example.com/best-soup?utm_source=social!
Duplicate: https://plain.example/page
"""
    )

    assert urls == [
        "https://cookbook.test/soup",
        "https://example.com/best-soup?utm_source=social",
        "https://plain.example/page",
    ]


def test_recipe_link_ranking_skips_social_and_commerce_hosts():
    urls = extract_ranked_recipe_urls(
        """
https://youtube.com/watch?v=123
https://youtu.be/123
https://instagram.com/cook
https://tiktok.com/@cook/video/123
https://facebook.com/cook
https://fb.me/cook
https://amazon.com/example
https://amzn.to/example
https://twitter.com/cook
https://x.com/cook
https://pinterest.com/cook
https://recipes.example/soup
"""
    )

    assert urls == ["https://recipes.example/soup"]
