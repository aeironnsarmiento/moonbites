from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.repositories.recipe_imports import SitemapEntry, list_recipe_sitemap_entries


def _client_returning(*pages):
    client = MagicMock()
    query = client.table.return_value.select.return_value.order.return_value
    query.range.return_value.execute.side_effect = [
        SimpleNamespace(data=page) for page in pages
    ]
    return client, query


def test_list_recipe_sitemap_entries_pages_until_short_batch():
    client, query = _client_returning(
        [{"id": "a", "created_at": "2026-09-30"}, {"id": "b", "created_at": "2026-09-29"}],
        [{"id": "c", "created_at": "2026-09-28"}],
    )
    with patch("app.repositories.recipe_imports._get_read_client", return_value=client):
        entries = list_recipe_sitemap_entries(batch_size=2)

    assert entries == [
        SitemapEntry(id="a", created_at="2026-09-30"),
        SitemapEntry(id="b", created_at="2026-09-29"),
        SitemapEntry(id="c", created_at="2026-09-28"),
    ]
    assert [call.args for call in query.range.call_args_list] == [(0, 1), (2, 3)]


def test_list_recipe_sitemap_entries_raises_when_not_configured():
    with patch("app.repositories.recipe_imports._get_read_client", return_value=None):
        with pytest.raises(RuntimeError, match="not configured"):
            list_recipe_sitemap_entries()
