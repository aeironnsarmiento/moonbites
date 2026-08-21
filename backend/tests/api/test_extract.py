from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.api.auth import AuthenticatedAdmin, require_admin_user
from backend.app.core.rate_limit import limiter
from backend.app.repositories.import_jobs import ImportJobStorageError, JobCreationOutcome
from backend.app.repositories.recipe_imports import SaveRecipeImportResult
from backend.app.schemas.extract import NormalizedRecipe
from backend.app.schemas.import_jobs import ImportJobRecord, ImportJobState
from backend.app.services.extraction_types import ExtractionResult, ParseStatus


client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_extract_rate_limit():
    limiter.reset()
    yield


def _import_job(**overrides) -> ImportJobRecord:
    now = datetime.now(timezone.utc)
    fields = {
        "id": "job-1",
        "owner_email": "admin@example.com",
        "canonical_reel_url": "https://www.instagram.com/reel/DZuzc9PNedT/",
        "state": ImportJobState.QUEUED,
        "version": 0,
        "next_advance_at": now,
        "stale_deadline": now,
        "created_at": now,
        "updated_at": now,
    }
    fields.update(overrides)
    return ImportJobRecord(**fields)


def test_extract_instagram_url_returns_existing_recipe_without_creating_a_job():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com", access_token="admin-token"
    )

    try:
        with (
            patch(
                "backend.app.api.routes.extract.find_existing_recipe_by_canonical_url",
                return_value={
                    "id": "recipe-1",
                    "submitted_url": "https://www.instagram.com/reel/DZuzc9PNedT/",
                    "final_url": "https://www.instagram.com/reel/DZuzc9PNedT/",
                    "page_title": "Chia Pudding",
                    "image_url": "https://cdn.example/thumb.jpg",
                    "recipes_json": [
                        {
                            "name": "Chia Pudding",
                            "ingredients": ["1 cup chia"],
                            "instructions": ["Soak overnight."],
                        }
                    ],
                },
            ) as find_existing,
            patch("backend.app.api.routes.extract.create_or_reuse_job") as create_job,
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://www.instagram.com/reel/DZuzc9PNedT/"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "result"
    assert body["result"]["recipes"][0]["name"] == "Chia Pudding"
    assert body["result"]["database_saved"] is True
    find_existing.assert_called_once_with(
        "https://www.instagram.com/reel/DZuzc9PNedT/"
    )
    create_job.assert_not_called()


def test_extract_instagram_url_creates_job_and_returns_pending():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com", access_token="admin-token"
    )

    try:
        with (
            patch(
                "backend.app.api.routes.extract.find_existing_recipe_by_canonical_url",
                return_value=None,
            ),
            patch(
                "backend.app.api.routes.extract.create_or_reuse_job",
                return_value=JobCreationOutcome(job=_import_job(), outcome="created"),
            ) as create_job,
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://www.instagram.com/reel/DZuzc9PNedT/"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    body = response.json()
    assert body["kind"] == "pending"
    assert body["job_id"] == "job-1"
    assert body["state"] == "queued"
    assert body["retry_after_ms"] >= 7000
    create_job.assert_called_once_with(
        "admin@example.com", "https://www.instagram.com/reel/DZuzc9PNedT/"
    )


def test_extract_instagram_url_reuses_active_job_for_same_owner():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com", access_token="admin-token"
    )

    try:
        with (
            patch(
                "backend.app.api.routes.extract.find_existing_recipe_by_canonical_url",
                return_value=None,
            ),
            patch(
                "backend.app.api.routes.extract.create_or_reuse_job",
                return_value=JobCreationOutcome(
                    job=_import_job(state=ImportJobState.WAITING_REEL), outcome="reused"
                ),
            ),
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://www.instagram.com/reel/DZuzc9PNedT/"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["state"] == "waiting_reel"


def test_extract_instagram_url_rejects_when_active_job_ceiling_exceeded():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com", access_token="admin-token"
    )

    try:
        with (
            patch(
                "backend.app.api.routes.extract.find_existing_recipe_by_canonical_url",
                return_value=None,
            ),
            patch(
                "backend.app.api.routes.extract.create_or_reuse_job",
                return_value=JobCreationOutcome(job=None, outcome="owner_ceiling"),
            ),
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://www.instagram.com/reel/DZuzc9PNedT/"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429


def test_extract_instagram_url_rejects_non_reel_paths():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com", access_token="admin-token"
    )

    try:
        response = client.post(
            "/api/extract",
            json={"url": "https://www.instagram.com/someprofile/"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_extract_instagram_url_returns_503_when_job_storage_unavailable():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com", access_token="admin-token"
    )

    try:
        with patch(
            "backend.app.api.routes.extract.find_existing_recipe_by_canonical_url",
            side_effect=ImportJobStorageError("down"),
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://www.instagram.com/reel/DZuzc9PNedT/"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


def test_extract_returns_incomplete_recipe_message_when_recipe_nodes_fail_to_normalize():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com",
        access_token="admin-token",
    )

    try:
        extraction = Mock(
            source_url="https://example.com/submitted",
            final_url="https://example.com/final",
            title="Recipe Page",
            image_url=None,
            recipe_node_count=1,
            recipes=[],
        )

        with patch(
            "backend.app.api.routes.extract.extract_recipes_from_url",
            return_value=extraction,
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://example.com/submitted"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["database_saved"] is False
    assert (
        response.json()["database_message"]
        == "Nothing was saved because recipe objects were found on that page, but they did not include enough data to extract a complete recipe."
    )


def test_extract_success_message_does_not_expose_supabase_table_name():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com",
        access_token="admin-token",
    )

    try:
        extraction = Mock(
            source_url="https://example.com/submitted",
            final_url="https://example.com/final",
            title="Recipe Page",
            image_url=None,
            recipe_node_count=1,
            recipes=[
                NormalizedRecipe(
                    name="Soup",
                    ingredients=["1 cup stock"],
                    instructions=["Warm stock."],
                )
            ],
        )

        with (
            patch(
                "backend.app.api.routes.extract.extract_recipes_from_url",
                return_value=extraction,
            ),
            patch(
                "backend.app.api.routes.extract.save_recipe_import",
                new=AsyncMock(
                    return_value=SaveRecipeImportResult(
                        saved=True,
                        message="Saved to Supabase table 'recipe_imports'.",
                        image_url=None,
                    )
                ),
            ),
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://example.com/submitted"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["database_saved"] is True
    assert response.json()["database_message"] == "Recipe saved to your collection."
    assert "Supabase" not in response.json()["database_message"]
    assert "recipe_imports" not in response.json()["database_message"]


def test_extract_response_includes_image_url():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com",
        access_token="admin-token",
    )

    try:
        extraction = Mock(
            source_url="https://youtu.be/abc123XYZ09",
            final_url="https://youtu.be/abc123XYZ09",
            title="Video Soup",
            image_url="https://img.youtube.com/soup.jpg",
            recipe_node_count=0,
            recipes=[],
        )

        with (
            patch(
                "backend.app.api.routes.extract.extract_recipes_from_url",
                return_value=extraction,
            ),
            patch("backend.app.api.routes.extract.save_recipe_import") as save,
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://youtu.be/abc123XYZ09"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["image_url"] == "https://img.youtube.com/soup.jpg"
    assert "_".join(("recipe", "count")) not in response.json()
    save.assert_not_called()


def test_extract_not_recipe_response_skips_db_write():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com",
        access_token="admin-token",
    )

    try:
        extraction = ExtractionResult(
            source_url="https://youtu.be/shroud123",
            final_url="https://youtu.be/shroud123",
            title="Shroud CS LAN",
            image_url="https://img.youtube.com/shroud.jpg",
            recipe_node_count=0,
            recipes=[],
            parse_status=ParseStatus.NOT_RECIPE,
            parse_reason="Description lacks recipe signals.",
        )

        with (
            patch(
                "backend.app.api.routes.extract.extract_recipes_from_url",
                return_value=extraction,
            ),
            patch("backend.app.api.routes.extract.save_recipe_import") as save,
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://youtu.be/shroud123"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["parse_status"] == "not_recipe"
    assert body["parse_reason"] == "Description lacks recipe signals."
    assert body["recipes"] == []
    assert "_".join(("recipe", "count")) not in body
    assert body["database_saved"] is False
    assert body["database_message"] == "Skipped — not a recipe."
    assert body["title"] == "Shroud CS LAN"
    save.assert_not_called()


def test_extract_recipe_response_includes_parse_status_recipe():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com",
        access_token="admin-token",
    )

    try:
        extraction = ExtractionResult(
            source_url="https://example.com/soup",
            final_url="https://example.com/soup",
            title="Soup",
            image_url=None,
            recipe_node_count=1,
            recipes=[
                NormalizedRecipe(
                    name="Soup",
                    ingredients=["1 cup stock"],
                    instructions=["Warm stock."],
                )
            ],
            parse_status=ParseStatus.RECIPE,
        )

        with (
            patch(
                "backend.app.api.routes.extract.extract_recipes_from_url",
                return_value=extraction,
            ),
            patch(
                "backend.app.api.routes.extract.save_recipe_import",
                new=AsyncMock(
                    return_value=SaveRecipeImportResult(
                        saved=True,
                        message="Recipe saved to your collection.",
                        image_url=None,
                    )
                ),
            ),
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://example.com/soup"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["parse_status"] == "recipe"
    assert body["parse_reason"] is None


def test_extract_success_passes_image_url_to_save_recipe_import():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com",
        access_token="admin-token",
    )

    try:
        extraction = Mock(
            source_url="https://youtu.be/abc123XYZ09",
            final_url="https://example.com/soup",
            title="Soup",
            image_url="https://example.com/soup.jpg",
            recipe_node_count=1,
            recipes=[
                NormalizedRecipe(
                    name="Soup",
                    ingredients=["1 cup stock"],
                    instructions=["Warm stock."],
                )
            ],
        )

        with (
            patch(
                "backend.app.api.routes.extract.extract_recipes_from_url",
                return_value=extraction,
            ),
            patch(
                "backend.app.api.routes.extract.save_recipe_import",
                new=AsyncMock(
                    return_value=SaveRecipeImportResult(
                        saved=True,
                        message="Recipe saved to your collection.",
                        image_url="https://example.com/soup.jpg",
                    )
                ),
            ) as save,
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://youtu.be/abc123XYZ09"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["image_url"] == "https://example.com/soup.jpg"
    assert save.call_args.kwargs["image_url"] == "https://example.com/soup.jpg"
