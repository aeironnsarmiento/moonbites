from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from app.repositories.recipe_imports import SitemapEntry

client = TestClient(app)


def test_sitemap_lists_static_pages_and_recipes():
    entries = [
        SitemapEntry(id="abc-123", created_at="2026-09-30T12:00:00+00:00"),
        SitemapEntry(id="def-456", created_at="2026-08-01T08:30:00+00:00"),
    ]
    with patch(
        "backend.app.api.routes.sitemap.list_recipe_sitemap_entries",
        return_value=entries,
    ):
        response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "max-age=3600" in response.headers["cache-control"]
    body = response.text
    assert body.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<loc>https://moonbites-blue.vercel.app/</loc>" in body
    assert "<loc>https://moonbites-blue.vercel.app/recipes</loc>" in body
    assert (
        "<url><loc>https://moonbites-blue.vercel.app/recipes/abc-123</loc>"
        "<lastmod>2026-09-30</lastmod></url>"
    ) in body
    assert "<loc>https://moonbites-blue.vercel.app/recipes/def-456</loc>" in body


def test_sitemap_returns_503_when_not_configured():
    with patch(
        "backend.app.api.routes.sitemap.list_recipe_sitemap_entries",
        side_effect=RuntimeError("Supabase is not configured yet."),
    ):
        response = client.get("/sitemap.xml")

    assert response.status_code == 503
