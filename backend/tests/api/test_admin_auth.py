from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.api.auth import (
    AuthenticatedAdmin,
    authenticate_admin_token,
    require_admin_user,
)
from backend.app.core.config import Settings
from app.schemas.extract import RecipeImportRecord


client = TestClient(app)


def _settings(admin_emails: tuple[str, ...] = ("admin@example.com",)) -> Settings:
    return Settings(
        request_timeout_seconds=15.0,
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_service_role_key=None,
        supabase_table_name="recipe_imports",
        admin_emails=admin_emails,
        cors_origins=("http://localhost:5173",),
        user_agent="test",
        accept_header="text/html",
        accept_language_header="en-US",
    )


@dataclass
class _User:
    email: str


@dataclass
class _UserResponse:
    user: _User


class _AuthClient:
    def __init__(self, email: str):
        self.auth = self
        self.email = email

    def get_user(self, jwt: str) -> _UserResponse:
        assert jwt == "valid-token"
        return _UserResponse(user=_User(email=self.email))


def _record() -> RecipeImportRecord:
    return RecipeImportRecord(
        id="abc",
        submitted_url="https://x.test",
        final_url="https://x.test",
        page_title="Test Recipe",
        recipe_count=1,
        times_cooked=0,
        recipes_json=[],
        recipe_overrides_json={},
        image_url=None,
        is_favorite=True,
        servings=None,
        created_at=datetime.now(timezone.utc),
    )


def test_write_endpoint_requires_bearer_token():
    response = client.patch("/api/recipes/abc/favorite")

    assert response.status_code == 401


def test_authenticate_admin_token_rejects_non_admin_email():
    with patch(
        "backend.app.api.auth.get_supabase_auth_client",
        return_value=_AuthClient("guest@example.com"),
    ):
        with pytest.raises(HTTPException) as error:
            authenticate_admin_token("valid-token", _settings())

    assert error.value.status_code == 403


def test_authenticate_admin_token_accepts_allowlisted_email_case_insensitive():
    with patch(
        "backend.app.api.auth.get_supabase_auth_client",
        return_value=_AuthClient("ADMIN@example.com"),
    ):
        admin = authenticate_admin_token("valid-token", _settings())

    assert admin == AuthenticatedAdmin(
        email="admin@example.com",
        access_token="valid-token",
    )


def test_admin_write_endpoint_passes_access_token_to_repository():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com",
        access_token="admin-token",
    )

    try:
        with patch(
            "backend.app.api.routes.recipes.toggle_favorite",
            return_value=_record(),
        ) as toggle_favorite:
            response = client.patch("/api/recipes/abc/favorite")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    toggle_favorite.assert_called_once_with("abc", access_token="admin-token")


def test_public_recipe_reads_do_not_require_auth():
    with patch(
        "backend.app.api.routes.recipes.get_recipe_import",
        return_value=_record(),
    ):
        response = client.get("/api/recipes/abc")

    assert response.status_code == 200
