from __future__ import annotations

from unittest.mock import AsyncMock, patch

from backend.scripts.refetch_recipe_imports import main


def test_refetch_cli_prints_summary(capsys):
    summary = AsyncMock()
    summary.total = 2
    summary.updated = 1
    summary.skipped = 1
    summary.failed = 0
    summary.no_recipe_found = 0
    summary.results = []

    with patch(
        "backend.scripts.refetch_recipe_imports.refetch_recipe_imports",
        new=AsyncMock(return_value=summary),
    ) as refetch:
        exit_code = main(["--dry-run", "--limit", "2"])

    assert exit_code == 0
    refetch.assert_awaited_once_with(dry_run=True, limit=2, recipe_import_id=None)
    assert "updated=1" in capsys.readouterr().out
