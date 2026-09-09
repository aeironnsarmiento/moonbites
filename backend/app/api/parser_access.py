"""Access policy shared by recipe extraction and Instagram job advancement."""
from dataclasses import dataclass
from hashlib import sha256
from typing import Optional
from uuid import UUID

from fastapi import Header, HTTPException

from .auth import AuthenticatedAdmin, require_admin_user
from ..core.config import get_settings


@dataclass(frozen=True)
class ParserUser:
    email: str
    access_token: Optional[str] = None


def require_parser_user(
    authorization: Optional[str] = Header(default=None),
    x_parser_session: Optional[str] = Header(default=None),
) -> ParserUser | AuthenticatedAdmin:
    if get_settings().public_recipe_parser_enabled and x_parser_session:
        try:
            session = UUID(x_parser_session)
            if session.version != 4:
                raise ValueError("Expected UUID4")
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Invalid parser session") from error
        # Store only a digest; a job record must not reveal its owner's session secret.
        owner = sha256(str(session).encode()).hexdigest()
        return ParserUser(email=f"public:{owner}")
    return require_admin_user(authorization)
