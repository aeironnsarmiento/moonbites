from __future__ import annotations

import argparse
import asyncio
from typing import Optional

try:
    from backend.app.services.tiktok.thumbnail_backfill import (
        backfill_tiktok_thumbnails,
    )
except ImportError:
    from app.services.tiktok.thumbnail_backfill import backfill_tiktok_thumbnails


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mirror temporary TikTok recipe thumbnails into Supabase Storage."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and report candidates without uploading or updating Supabase.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of TikTok recipe imports to process.",
    )
    parser.add_argument(
        "--id",
        dest="recipe_import_id",
        default=None,
        help="Process one recipe import id.",
    )
    return parser


def _print_summary(summary) -> None:
    print(
        "TikTok thumbnail backfill: "
        f"total={summary.total} "
        f"mirrored={summary.mirrored} "
        f"would_mirror={summary.would_mirror} "
        f"skipped={summary.skipped} "
        f"failed={summary.failed}"
    )
    for result in summary.results:
        parts = [result.recipe_import_id, result.status]
        if result.source_url:
            parts.append(result.source_url)
        if result.message:
            parts.append(result.message)
        print(" - " + " | ".join(parts))


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than 0")

    summary = asyncio.run(
        backfill_tiktok_thumbnails(
            dry_run=args.dry_run,
            limit=args.limit,
            recipe_import_id=args.recipe_import_id,
        )
    )
    _print_summary(summary)
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
