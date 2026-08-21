from __future__ import annotations

from unittest.mock import patch

from backend.scripts.audit_social_thumbnails import find_orphaned_thumbnails, main


class _Response:
    def __init__(self, data):
        self.data = data


class _FakeTableQuery:
    def __init__(self, data):
        self._data = data
        self.not_ = self

    def select(self, _cols):
        return self

    def is_(self, _column, _value):
        return self

    def execute(self):
        return _Response(self._data)


class _FakeBucket:
    def __init__(self, listing: dict[str, list[dict]]):
        self._listing = listing

    def list(self, prefix):
        return self._listing.get(prefix, [])


class _FakeStorage:
    def __init__(self, bucket):
        self._bucket = bucket

    def from_(self, _bucket_name):
        return self._bucket


class _FakeClient:
    def __init__(self, referenced_rows, listing):
        self._referenced_rows = referenced_rows
        self.storage = _FakeStorage(_FakeBucket(listing))

    def table(self, _name):
        return _FakeTableQuery(self._referenced_rows)


def test_find_orphaned_thumbnails_reports_objects_with_no_referencing_row():
    referenced_rows = [{"image_storage_path": "tiktok/recipe-1/digesta.jpg"}]
    listing = {
        "tiktok": [{"name": "recipe-1"}, {"name": "recipe-2"}],
        "tiktok/recipe-1": [{"name": "digesta.jpg"}],
        "tiktok/recipe-2": [{"name": "digestb.jpg"}],
        "instagram": [],
    }
    client = _FakeClient(referenced_rows, listing)

    with (
        patch("backend.scripts.audit_social_thumbnails.get_settings") as get_settings,
        patch(
            "backend.scripts.audit_social_thumbnails.get_supabase_client",
            return_value=client,
        ),
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        orphans = find_orphaned_thumbnails()

    assert orphans == ["tiktok/recipe-2/digestb.jpg"]


def test_find_orphaned_thumbnails_raises_when_supabase_not_configured():
    with (
        patch("backend.scripts.audit_social_thumbnails.get_settings"),
        patch(
            "backend.scripts.audit_social_thumbnails.get_supabase_client",
            return_value=None,
        ),
    ):
        try:
            find_orphaned_thumbnails()
        except RuntimeError:
            return
    raise AssertionError("expected RuntimeError")


def test_cli_defaults_to_dry_run_and_deletes_nothing(capsys):
    with (
        patch(
            "backend.scripts.audit_social_thumbnails.find_orphaned_thumbnails",
            return_value=["tiktok/recipe-2/digestb.jpg"],
        ),
        patch(
            "backend.scripts.audit_social_thumbnails.delete_social_thumbnail"
        ) as delete_thumb,
    ):
        exit_code = main([])

    assert exit_code == 0
    delete_thumb.assert_not_called()
    output = capsys.readouterr().out
    assert "Orphaned thumbnails found: 1" in output
    assert "tiktok/recipe-2/digestb.jpg" in output
    assert "Dry run" in output


def test_cli_apply_flag_deletes_orphans(capsys):
    with (
        patch(
            "backend.scripts.audit_social_thumbnails.find_orphaned_thumbnails",
            return_value=["tiktok/recipe-2/digestb.jpg"],
        ),
        patch(
            "backend.scripts.audit_social_thumbnails.delete_social_thumbnail"
        ) as delete_thumb,
    ):
        exit_code = main(["--apply"])

    assert exit_code == 0
    delete_thumb.assert_called_once_with("tiktok/recipe-2/digestb.jpg")
    assert "Deleted 1 orphaned thumbnail" in capsys.readouterr().out
