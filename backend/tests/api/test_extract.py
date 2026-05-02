from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.app.api.auth import AuthenticatedAdmin, require_admin_user
from backend.app.schemas.extract import NormalizedRecipe


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
