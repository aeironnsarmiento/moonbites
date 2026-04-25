from app.services.image_extraction import extract_image_url


def test_prefers_jsonld_recipe_image_string():
    jsonld = [{"@type": "Recipe", "image": "https://example.com/recipe.jpg"}]
    html = '<html><head><meta property="og:image" content="https://example.com/og.jpg"></head><body></body></html>'
    assert extract_image_url(html, jsonld) == "https://example.com/recipe.jpg"


def test_prefers_jsonld_recipe_image_array():
    jsonld = [
        {
            "@type": "Recipe",
            "image": ["https://example.com/a.jpg", "https://example.com/b.jpg"],
        }
    ]
    assert extract_image_url("", jsonld) == "https://example.com/a.jpg"


def test_falls_back_to_og_image():
    html = '<html><head><meta property="og:image" content="https://example.com/og.jpg"></head></html>'
    assert extract_image_url(html, []) == "https://example.com/og.jpg"


def test_falls_back_to_twitter_image():
    html = '<html><head><meta name="twitter:image" content="https://example.com/tw.jpg"></head></html>'
    assert extract_image_url(html, []) == "https://example.com/tw.jpg"


def test_returns_none_when_nothing_present():
    html = "<html><head></head><body></body></html>"
    assert extract_image_url(html, []) is None


def test_handles_jsonld_image_object():
    jsonld = [
        {
            "@type": "Recipe",
            "image": {
                "@type": "ImageObject",
                "url": "https://example.com/x.jpg",
            },
        }
    ]
    assert extract_image_url("", jsonld) == "https://example.com/x.jpg"
