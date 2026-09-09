from dataclasses import replace
from hashlib import sha256
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.core.config import get_settings
from backend.app.core.rate_limit import limiter
from backend.app.api.auth import AuthenticatedAdmin
from backend.app.repositories.recipe_imports import SaveRecipeImportResult
from backend.app.schemas.extract import NormalizedRecipe
from backend.app.services.extraction_types import ExtractionResult

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_limits():
    limiter.reset()


@pytest.mark.parametrize('enabled', [True, False])
def test_access_reports_backend_toggle(enabled):
    with patch('backend.app.api.routes.extract.get_settings', return_value=replace(get_settings(), public_recipe_parser_enabled=enabled)):
        response = client.get('/api/extract/access')
    assert response.json() == {'public_enabled': enabled}
    assert response.headers['cache-control'] == 'no-store'


def test_public_import_saves_without_user_token():
    recipe = NormalizedRecipe(name='Soup', ingredients=['Stock'], instructions=['Heat'])
    extraction = ExtractionResult(source_url='https://example.com/soup', final_url='https://example.com/soup', title='Soup', image_url=None, recipes=[recipe], recipe_node_count=1)
    with (
        patch('backend.app.api.parser_access.get_settings', return_value=replace(get_settings(), public_recipe_parser_enabled=True)),
        patch('backend.app.api.routes.extract.extract_recipes_from_url', new=AsyncMock(return_value=extraction)),
        patch('backend.app.api.routes.extract.save_recipe_import', new=AsyncMock(return_value=SaveRecipeImportResult(saved=True, message='Saved', image_url=None))) as save,
    ):
        response = client.post('/api/extract', json={'url': extraction.source_url}, headers={'X-Parser-Session': str(uuid4())})
    assert response.status_code == 200
    assert response.json()['database_saved'] is True
    assert save.call_args.kwargs['access_token'] is None


@pytest.mark.parametrize('path', ['/api/extract', '/api/extract/jobs/job-1/advance'])
def test_disabled_public_access_rejects_guest_before_work(path):
    with patch('backend.app.api.parser_access.get_settings', return_value=replace(get_settings(), public_recipe_parser_enabled=False)):
        response = client.post(path, json={'url': 'https://example.com/soup'}, headers={'X-Parser-Session': str(uuid4())})
    assert response.status_code == 401


def test_disabled_parser_still_authenticates_admins():
    with (
        patch('backend.app.api.parser_access.get_settings', return_value=replace(get_settings(), public_recipe_parser_enabled=False)),
        patch('backend.app.api.parser_access.require_admin_user', return_value=AuthenticatedAdmin('admin@example.com', 'token')) as authenticate,
        patch('backend.app.api.routes.import_jobs.get_job_for_owner', return_value=None) as lookup,
    ):
        response = client.post('/api/extract/jobs/missing/advance', headers={'Authorization': 'Bearer token', 'X-Parser-Session': str(uuid4())})
    assert response.status_code == 404
    authenticate.assert_called_once_with('Bearer token')
    lookup.assert_called_once_with('missing', 'admin@example.com')


def test_guest_job_access_uses_hashed_session_owner():
    session = str(uuid4())
    with (
        patch('backend.app.api.parser_access.get_settings', return_value=replace(get_settings(), public_recipe_parser_enabled=True)),
        patch('backend.app.api.routes.import_jobs.get_job_for_owner', return_value=None) as lookup,
    ):
        response = client.post('/api/extract/jobs/missing/advance', headers={'X-Parser-Session': session})
    assert response.status_code == 404
    lookup.assert_called_once_with('missing', f'public:{sha256(session.encode()).hexdigest()}')


def test_public_session_does_not_grant_recipe_editing():
    response = client.patch('/api/recipes/abc/favorite', headers={'X-Parser-Session': str(uuid4())})
    assert response.status_code == 401


def test_invalid_session_is_rejected():
    with patch('backend.app.api.parser_access.get_settings', return_value=replace(get_settings(), public_recipe_parser_enabled=True)):
        response = client.post('/api/extract', json={'url': 'https://example.com/soup'}, headers={'X-Parser-Session': 'invalid'})
    assert response.status_code == 400
