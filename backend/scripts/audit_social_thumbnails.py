from __future__ import annotations

import argparse
from typing import Optional

try:
    from backend.app.clients.supabase_client import get_supabase_client
    from backend.app.core.config import get_settings
    from backend.app.services.social.thumbnail_storage import (
        THUMBNAIL_BUCKET,
        delete_social_thumbnail,
    )
except ImportError:
    from app.clients.supabase_client import get_supabase_client
    from app.core.config import get_settings
    from app.services.social.thumbnail_storage import (
        THUMBNAIL_BUCKET,
        delete_social_thumbnail,
    )


PLATFORM_PREFIXES = ("tiktok", "instagram")


def _list_referenced_paths(client, table_name: str) -> set[str]:
    response = (
        client.table(table_name)
        .select("image_storage_path")
        .not_.is_("image_storage_path", "null")
        .execute()
    )
    return {
        path
        for row in (response.data or [])
        if isinstance((path := row.get("image_storage_path")), str) and path
    }


def _list_stored_objects(client, platform: str) -> list[str]:
    bucket = client.storage.from_(THUMBNAIL_BUCKET)
    paths: list[str] = []
    for entry in bucket.list(platform) or []:
        recipe_import_id = entry.get("name") if isinstance(entry, dict) else None
        if not recipe_import_id:
            continue
        sub_prefix = f"{platform}/{recipe_import_id}"
        for object_entry in bucket.list(sub_prefix) or []:
            object_name = (
                object_entry.get("name") if isinstance(object_entry, dict) else None
            )
            if object_name:
                paths.append(f"{sub_prefix}/{object_name}")
    return paths


def find_orphaned_thumbnails() -> list[str]:
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to audit thumbnails."
        )

    referenced = _list_referenced_paths(client, settings.supabase_table_name)
    orphans: list[str] = []
    for platform in PLATFORM_PREFIXES:
        for path in _list_stored_objects(client, platform):
            if path not in referenced:
                orphans.append(path)
    return orphans


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Find managed social thumbnail objects with no referencing "
            "recipe_imports row and, optionally, delete them."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete orphaned thumbnail objects. Without this flag, the audit runs in dry-run mode.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    dry_run = not args.apply

    orphans = find_orphaned_thumbnails()
    print(f"Orphaned thumbnails found: {len(orphans)}")
    for path in orphans:
        print(f" - {path}")

    if dry_run:
        print("Dry run: no objects were deleted. Re-run with --apply to delete them.")
        return 0

    deleted = 0
    for path in orphans:
        try:
            delete_social_thumbnail(path)
            deleted += 1
        except Exception as error:
            print(f"Failed to delete {path}: {error}")
    print(f"Deleted {deleted} orphaned thumbnail(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
