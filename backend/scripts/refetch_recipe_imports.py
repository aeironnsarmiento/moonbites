from __future__ import annotations

import argparse
import asyncio
from typing import Optional

try:
    from backend.app.services.recipe_refresher import refetch_recipe_imports
except ImportError:
    from app.services.recipe_refresher import refetch_recipe_imports


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refetch saved recipe imports from their source URLs."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and report changes without updating Supabase.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of saved imports to process.",
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
        "Refetch summary: "
        f"total={summary.total} "
        f"updated={summary.updated} "
        f"skipped={summary.skipped} "
        f"failed={summary.failed} "
        f"no_recipe_found={summary.no_recipe_found}"
    )

    for result in summary.results:
        parts = [
            result.recipe_import_id,
            result.status,
        ]
        if result.url:
            parts.append(result.url)
        if result.message:
            parts.append(result.message)
        print(" - " + " | ".join(parts))


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than 0")

    summary = asyncio.run(
        refetch_recipe_imports(
            dry_run=args.dry_run,
            limit=args.limit,
            recipe_import_id=args.recipe_import_id,
        )
    )
    _print_summary(summary)
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
