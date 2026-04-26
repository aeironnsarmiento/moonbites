from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.app.api.auth import AuthenticatedAdmin, require_admin_user


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
