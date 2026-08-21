from __future__ import annotations

import argparse
from typing import Optional

try:
    from backend.app.repositories.import_jobs import (
        delete_expired_terminal_jobs,
        reconcile_provider_admission,
        terminalize_stale_jobs,
    )
except ImportError:
    from app.repositories.import_jobs import (
        delete_expired_terminal_jobs,
        reconcile_provider_admission,
        terminalize_stale_jobs,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Terminalize stale Instagram import jobs, reconcile the provider "
            "admission slot, and delete expired terminal jobs."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag, the cleanup runs in dry-run mode.",
    )
    return parser


def _print_jobs(label: str, jobs) -> None:
    print(f"{label}: {len(jobs)}")
    for job in jobs:
        print(f" - {job.id} ({job.state.value})")


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    dry_run = not args.apply

    terminalized = terminalize_stale_jobs(dry_run=dry_run)
    _print_jobs("Stale jobs terminalized", terminalized)

    reconciled = reconcile_provider_admission(dry_run=dry_run)
    print(f"Provider admission slots reconciled: {len(reconciled)}")

    deleted = delete_expired_terminal_jobs(dry_run=dry_run)
    _print_jobs("Expired terminal jobs deleted", deleted)

    if dry_run:
        print("Dry run: no changes were applied. Re-run with --apply to apply them.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
