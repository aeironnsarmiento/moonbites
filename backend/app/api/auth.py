from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from ..clients.supabase_client import get_supabase_auth_client, get_supabase_client
from ..core.config import Settings, get_settings


router = APIRouter(prefix="/api/auth", tags=["auth"])


@dataclass(frozen=True)
class AuthenticatedAdmin:
    email: str
    access_token: str


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    scheme, _, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Missing bearer token")

    return token.strip()


def authenticate_admin_token(
    access_token: str,
    settings: Optional[Settings] = None,
) -> AuthenticatedAdmin:
    resolved_settings = settings or get_settings()
    client = get_supabase_auth_client(resolved_settings)
    if client is None:
        raise HTTPException(status_code=503, detail="Supabase Auth is not configured")

    try:
        response = client.auth.get_user(access_token)
    except Exception as error:
        raise HTTPException(status_code=401, detail="Invalid bearer token") from error

    user = getattr(response, "user", None)
    email = getattr(user, "email", None)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    normalized_email = email.casefold()

    admin_client = get_supabase_client(resolved_settings)
    if admin_client is None:
        raise HTTPException(
            status_code=503,
            detail="Supabase admin lookup is not configured",
        )

    try:
        response = (
            admin_client.table("recipe_admins")
            .select("email")
            .eq("email", normalized_email)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="Supabase admin lookup failed",
        ) from error

    if not (response.data or []):
        raise HTTPException(status_code=403, detail="Admin access required")

    return AuthenticatedAdmin(email=normalized_email, access_token=access_token)


def require_admin_user(
    authorization: Optional[str] = Header(default=None),
) -> AuthenticatedAdmin:
    return authenticate_admin_token(_extract_bearer_token(authorization))


@router.get("/me")
async def get_admin_user(
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> dict[str, object]:
    return {"email": admin.email, "is_admin": True}
