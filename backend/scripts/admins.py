from __future__ import annotations

import argparse
from typing import Optional

try:
    from backend.app.clients.supabase_client import get_supabase_client
    from backend.app.core.config import get_settings
except ImportError:
    from app.clients.supabase_client import get_supabase_client
    from app.core.config import get_settings


def _normalize_email(value: str) -> str:
    email = value.strip().casefold()
    if not email or "@" not in email:
        raise ValueError("email must be a valid email address")
    return email


def _get_admin_client():
    client = get_supabase_client(get_settings())
    if client is None:
        raise RuntimeError(
            "Supabase admin client is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in backend/.env."
        )
    return client


def grant_admin(email: str) -> str:
    normalized_email = _normalize_email(email)
    (
        _get_admin_client()
        .table("recipe_admins")
        .upsert({"email": normalized_email}, on_conflict="email")
        .execute()
    )
    return normalized_email


def revoke_admin(email: str) -> str:
    normalized_email = _normalize_email(email)
    (
        _get_admin_client()
        .table("recipe_admins")
        .delete()
        .eq("email", normalized_email)
        .execute()
    )
    return normalized_email


def list_admins() -> list[str]:
    response = (
        _get_admin_client()
        .table("recipe_admins")
        .select("email")
        .order("email")
        .execute()
    )
    return [
        str(row["email"])
        for row in response.data or []
        if isinstance(row, dict) and row.get("email")
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Moonbites admin users.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    grant_parser = subparsers.add_parser("grant", help="Grant admin access.")
    grant_parser.add_argument("email")

    revoke_parser = subparsers.add_parser("revoke", help="Revoke admin access.")
    revoke_parser.add_argument("email")

    subparsers.add_parser("list", help="List admin emails.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "grant":
            email = grant_admin(args.email)
            print(f"Granted admin: {email}")
        elif args.command == "revoke":
            email = revoke_admin(args.email)
            print(f"Revoked admin: {email}")
        else:
            for email in list_admins():
                print(email)
    except (RuntimeError, ValueError) as error:
        parser.exit(status=1, message=f"{error}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
