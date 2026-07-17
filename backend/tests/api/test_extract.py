from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.app.api.auth import AuthenticatedAdmin, require_admin_user
from backend.app.schemas.extract import DisplayTitleSource, NormalizedRecipe
from backend.app.services.display_titles import DisplayTitle
from backend.app.services.extraction_types import ExtractionResult, ParseStatus


client = TestClient(app)


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
                return_value=(True, "Saved to Supabase table 'recipe_imports'."),
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
                return_value=(True, "Recipe saved to your collection."),
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
                return_value=(True, "Recipe saved to your collection."),
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


def _admin_override():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com",
        access_token="admin-token",
    )


def _extraction_with_recipes():
    return Mock(
        source_url="https://example.com/submitted",
        final_url="https://example.com/final",
        title="The BEST Soup You'll EVER Make!!",
        image_url=None,
        recipe_node_count=1,
        recipes=[
            NormalizedRecipe(
                name="Chicken Soup",
                ingredients=["1 cup stock", "2 chicken thighs"],
                instructions=["Warm stock."],
            )
        ],
        parse_status=ParseStatus.RECIPE,
        parse_reason=None,
    )


def test_extract_forwards_the_generated_display_title_to_the_save():
    _admin_override()

    try:
        with (
            patch(
                "backend.app.api.routes.extract.extract_recipes_from_url",
                return_value=_extraction_with_recipes(),
            ),
            patch(
                "backend.app.api.routes.extract.generate_display_title",
                return_value=DisplayTitle(value="Chicken Soup", source="ai"),
            ) as generate,
            patch(
                "backend.app.api.routes.extract.save_recipe_import",
                return_value=(True, "Saved."),
            ) as save,
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://example.com/submitted"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    generate.assert_called_once()
    assert generate.call_args.kwargs["source_title"] == "The BEST Soup You'll EVER Make!!"
    assert save.call_args.kwargs["display_title"] == "Chicken Soup"
    assert save.call_args.kwargs["display_title_source"] == DisplayTitleSource.ai


def test_extract_still_saves_when_title_generation_degrades():
    # Covers AE4: the AI service being unavailable must not fail the import.
    _admin_override()

    try:
        with (
            patch(
                "backend.app.api.routes.extract.extract_recipes_from_url",
                return_value=_extraction_with_recipes(),
            ),
            patch(
                "backend.app.api.routes.extract.generate_display_title",
                return_value=DisplayTitle(
                    value="Soup", source="fallback", reason="unreachable"
                ),
            ),
            patch(
                "backend.app.api.routes.extract.save_recipe_import",
                return_value=(True, "Saved."),
            ) as save,
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://example.com/submitted"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["database_saved"] is True
    assert save.call_args.kwargs["display_title"] == "Soup"
    assert save.call_args.kwargs["display_title_source"] == DisplayTitleSource.fallback


def test_extract_does_not_generate_a_title_for_a_non_recipe():
    _admin_override()

    try:
        extraction = Mock(
            source_url="https://example.com/submitted",
            final_url="https://example.com/final",
            title="Vlog",
            image_url=None,
            recipe_node_count=0,
            recipes=[],
            parse_status=ParseStatus.NOT_RECIPE,
            parse_reason="Not a recipe.",
        )

        with (
            patch(
                "backend.app.api.routes.extract.extract_recipes_from_url",
                return_value=extraction,
            ),
            patch(
                "backend.app.api.routes.extract.generate_display_title"
            ) as generate,
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://example.com/submitted"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    generate.assert_not_called()


def test_extract_does_not_generate_a_title_when_nothing_normalized():
    _admin_override()

    try:
        extraction = Mock(
            source_url="https://example.com/submitted",
            final_url="https://example.com/final",
            title="Recipe Page",
            image_url=None,
            recipe_node_count=1,
            recipes=[],
            parse_status=ParseStatus.RECIPE,
            parse_reason=None,
        )

        with (
            patch(
                "backend.app.api.routes.extract.extract_recipes_from_url",
                return_value=extraction,
            ),
            patch(
                "backend.app.api.routes.extract.generate_display_title"
            ) as generate,
        ):
            response = client.post(
                "/api/extract",
                json={"url": "https://example.com/submitted"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    generate.assert_not_called()
