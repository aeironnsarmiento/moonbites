from app.services.youtube.description_parser import extract_ranked_recipe_urls


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


def test_extract_ranked_recipe_urls_skips_tiktok_links():
    urls = extract_ranked_recipe_urls(
        "Recipe on my TikTok: https://www.tiktok.com/@cook/video/123"
    )

    assert urls == []


def test_extract_ranked_recipe_urls_deduplicates_and_orders_by_score():
    urls = extract_ranked_recipe_urls(
        """
https://plain.example/page
Full recipe here: https://recipes.example/pasta
https://plain.example/page
"""
    )

    assert urls == ["https://recipes.example/pasta", "https://plain.example/page"]
