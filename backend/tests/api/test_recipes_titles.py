from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.api.auth import AuthenticatedAdmin, require_admin_user
from backend.app.repositories.recipe_imports import (
    DisplayTitleApplyResult,
    RecipeWriteDeniedError,
)
from app.schemas.extract import (
    DisplayTitleSource,
    SkippedTitleCleanupItem,
    TitleCleanupPreviewResponse,
    TitleSuggestion,
)


client = TestClient(app)


@pytest.fixture(autouse=True)
def admin_override():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com",
        access_token="admin-token",
    )
    yield
    app.dependency_overrides.clear()


def _preview_response() -> TitleCleanupPreviewResponse:
    return TitleCleanupPreviewResponse(
        suggestions=[
            TitleSuggestion(
                recipe_import_id="abc",
                current_title="The BEST Garlic Noodles!!",
                suggested_title="Garlic Noodles",
                source=DisplayTitleSource.ai,
            )
        ],
        skipped=[
            SkippedTitleCleanupItem(
                recipe_import_id="edited",
                current_title="Mom's Adobo",
                reason="You titled this recipe, so it was left alone.",
            )
        ],
        next_cursor="2026-01-01T00:00:00+00:00",
    )


async def _fake_preview(**kwargs):
    _fake_preview.kwargs = kwargs
    return _preview_response()


# --- preview ----------------------------------------------------------------


def test_preview_returns_suggestions_and_skipped_items():
    with patch(
        "backend.app.api.routes.recipes.preview_title_cleanup",
        _fake_preview,
    ):
        response = client.post("/api/recipes/titles/preview", json={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["suggestions"][0]["suggested_title"] == "Garlic Noodles"
    assert body["skipped"][0]["recipe_import_id"] == "edited"
    assert body["next_cursor"] == "2026-01-01T00:00:00+00:00"


def test_preview_forwards_the_cursor_and_limit():
    with patch(
        "backend.app.api.routes.recipes.preview_title_cleanup",
        _fake_preview,
    ):
        client.post(
            "/api/recipes/titles/preview",
            json={"limit": 5, "cursor": "2026-02-02T00:00:00+00:00"},
        )

    assert _fake_preview.kwargs == {
        "cursor": "2026-02-02T00:00:00+00:00",
        "limit": 5,
    }


def test_preview_defaults_the_limit():
    with patch(
        "backend.app.api.routes.recipes.preview_title_cleanup",
        _fake_preview,
    ):
        client.post("/api/recipes/titles/preview", json={})

    assert _fake_preview.kwargs["limit"] == 10
    assert _fake_preview.kwargs["cursor"] is None


@pytest.mark.parametrize("limit", [0, 11, -1])
def test_preview_rejects_an_out_of_range_limit(limit):
    response = client.post("/api/recipes/titles/preview", json={"limit": limit})

    assert response.status_code == 422


def test_preview_translates_an_unconfigured_repository():
    async def _raise(**_kwargs):
        raise RuntimeError("Supabase is not configured yet.")

    with patch("backend.app.api.routes.recipes.preview_title_cleanup", _raise):
        response = client.post("/api/recipes/titles/preview", json={})

    assert response.status_code == 503


# --- apply ------------------------------------------------------------------


def test_apply_writes_only_the_submitted_items():
    # Covers AE5: rejected suggestions are simply absent from the payload.
    with patch(
        "backend.app.api.routes.recipes.apply_display_titles",
        return_value=[
            DisplayTitleApplyResult(recipe_import_id="a", status="applied"),
            DisplayTitleApplyResult(recipe_import_id="b", status="applied"),
        ],
    ) as apply:
        response = client.post(
            "/api/recipes/titles/apply",
            json={
                "items": [
                    {"recipe_import_id": "a", "title": "Garlic Noodles"},
                    {"recipe_import_id": "b", "title": "Chicken Adobo"},
                ]
            },
        )

    assert response.status_code == 200
    assert response.json()["applied_count"] == 2
    assert apply.call_args.args[0] == [
        ("a", "Garlic Noodles"),
        ("b", "Chicken Adobo"),
    ]
    assert apply.call_args.kwargs["access_token"] == "admin-token"


def test_apply_reports_a_row_the_repository_skipped():
    # Covers R13: the database is the authority, so a skip is surfaced honestly
    # rather than counted as applied.
    with patch(
        "backend.app.api.routes.recipes.apply_display_titles",
        return_value=[
            DisplayTitleApplyResult(recipe_import_id="a", status="applied"),
            DisplayTitleApplyResult(
                recipe_import_id="edited",
                status="skipped",
                reason="You titled this recipe, so it was left alone.",
            ),
        ],
    ):
        response = client.post(
            "/api/recipes/titles/apply",
            json={
                "items": [
                    {"recipe_import_id": "a", "title": "Garlic Noodles"},
                    {"recipe_import_id": "edited", "title": "Chicken Adobo"},
                ]
            },
        )

    body = response.json()
    assert body["applied_count"] == 1
    assert body["results"][1]["status"] == "skipped"


def test_apply_trims_a_padded_title():
    with patch(
        "backend.app.api.routes.recipes.apply_display_titles",
        return_value=[DisplayTitleApplyResult(recipe_import_id="a", status="applied")],
    ) as apply:
        client.post(
            "/api/recipes/titles/apply",
            json={"items": [{"recipe_import_id": "a", "title": "  Garlic Noodles  "}]},
        )

    assert apply.call_args.args[0] == [("a", "Garlic Noodles")]


@pytest.mark.parametrize(
    "items",
    [
        [],
        [{"recipe_import_id": "a", "title": ""}],
        [{"recipe_import_id": "", "title": "Garlic Noodles"}],
        [{"recipe_import_id": "a", "title": "x" * 201}],
    ],
)
def test_apply_rejects_invalid_payloads(items):
    response = client.post("/api/recipes/titles/apply", json={"items": items})

    assert response.status_code == 422


def test_apply_rejects_an_oversized_batch():
    items = [
        {"recipe_import_id": str(index), "title": "Garlic Noodles"}
        for index in range(51)
    ]

    response = client.post("/api/recipes/titles/apply", json={"items": items})

    assert response.status_code == 422


def test_apply_translates_a_write_denial():
    with patch(
        "backend.app.api.routes.recipes.apply_display_titles",
        side_effect=RecipeWriteDeniedError("Admin access required."),
    ):
        response = client.post(
            "/api/recipes/titles/apply",
            json={"items": [{"recipe_import_id": "a", "title": "Garlic Noodles"}]},
        )

    assert response.status_code == 403


# --- auth -------------------------------------------------------------------


def test_title_routes_require_an_admin():
    app.dependency_overrides.clear()

    preview = client.post("/api/recipes/titles/preview", json={})
    apply = client.post(
        "/api/recipes/titles/apply",
        json={"items": [{"recipe_import_id": "a", "title": "Garlic Noodles"}]},
    )

    assert preview.status_code in (401, 403)
    assert apply.status_code in (401, 403)


def test_title_routes_are_not_shadowed_by_the_recipe_id_route():
    # /recipes/titles/... are literal segments and must resolve to their own
    # handlers rather than the {recipe_import_id} matcher.
    paths = {route.path for route in app.routes}

    assert "/api/recipes/titles/preview" in paths
    assert "/api/recipes/titles/apply" in paths
