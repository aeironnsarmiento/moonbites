from __future__ import annotations

import asyncio
import hashlib
from unittest.mock import patch

import httpx
import pytest

from app.core.config import Settings
from app.services.tiktok.thumbnail_storage import (
    TikTokThumbnailStorageError,
    delete_tiktok_thumbnail,
    mirror_tiktok_thumbnail,
)


class _FakeBucket:
    def __init__(self):
        self.uploaded: list[tuple] = []
        self.removed: list[str] = []

    def upload(self, *, path, file, file_options):
        self.uploaded.append((path, file, file_options))

    def get_public_url(self, path):
        return f"https://cdn.example/{path}"

    def remove(self, paths):
        self.removed.extend(paths)


class _FakeStorage:
    def __init__(self, bucket):
        self._bucket = bucket

    def from_(self, _bucket_name):
        return self._bucket


class _FakeSupabaseClient:
    def __init__(self, bucket):
        self.storage = _FakeStorage(bucket)


def _settings() -> Settings:
    return Settings(
        request_timeout_seconds=15.0,
        supabase_url=None,
        supabase_publishable_key=None,
        supabase_service_role_key=None,
        supabase_table_name="recipe_imports",
        admin_emails=(),
        cors_origins=("http://localhost:5173",),
        user_agent="test-agent",
        accept_header="text/html",
        accept_language_header="en-US",
        youtube_api_key=None,
    )


_RealAsyncClient = httpx.AsyncClient


def _client_factory(handler):
    def factory(**kwargs):
        return _RealAsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory


def test_mirror_tiktok_thumbnail_uses_the_tiktok_platform_path():
    bucket = _FakeBucket()
    client = _FakeSupabaseClient(bucket)

    def handler(_request):
        return httpx.Response(
            200, content=b"jpeg-bytes", headers={"content-type": "image/jpeg"}
        )

    with (
        patch(
            "app.services.tiktok.thumbnail_storage.get_settings",
            return_value=_settings(),
        ),
        patch(
            "app.services.social.thumbnail_storage.get_settings",
            return_value=_settings(),
        ),
        patch(
            "app.services.social.thumbnail_storage.get_supabase_client",
            return_value=client,
        ),
        patch(
            "app.services.tiktok.thumbnail_storage.httpx.AsyncClient",
            _client_factory(handler),
        ),
    ):
        result = asyncio.run(
            mirror_tiktok_thumbnail("recipe-1", "https://tiktok.example/thumb.jpg")
        )

    digest = hashlib.sha256(b"jpeg-bytes").hexdigest()
    expected_path = f"tiktok/recipe-1/{digest}.jpg"
    assert result.storage_path == expected_path
    assert result.image_url == f"https://cdn.example/{expected_path}"
    assert bucket.uploaded[0][0] == expected_path


def test_mirror_tiktok_thumbnail_rejects_unsupported_content_type_before_upload():
    bucket = _FakeBucket()
    client = _FakeSupabaseClient(bucket)

    def handler(_request):
        return httpx.Response(200, content=b"data", headers={"content-type": "image/gif"})

    with (
        patch(
            "app.services.tiktok.thumbnail_storage.get_settings",
            return_value=_settings(),
        ),
        patch(
            "app.services.social.thumbnail_storage.get_supabase_client",
            return_value=client,
        ),
        patch(
            "app.services.tiktok.thumbnail_storage.httpx.AsyncClient",
            _client_factory(handler),
        ),
    ):
        with pytest.raises(TikTokThumbnailStorageError):
            asyncio.run(
                mirror_tiktok_thumbnail("recipe-1", "https://tiktok.example/thumb.gif")
            )

    assert bucket.uploaded == []


def test_mirror_tiktok_thumbnail_wraps_storage_failures_as_tiktok_error():
    bucket = _FakeBucket()

    def handler(_request):
        return httpx.Response(
            200, content=b"jpeg-bytes", headers={"content-type": "image/jpeg"}
        )

    with (
        patch(
            "app.services.tiktok.thumbnail_storage.get_settings",
            return_value=_settings(),
        ),
        patch(
            "app.services.social.thumbnail_storage.get_supabase_client",
            return_value=None,
        ),
        patch(
            "app.services.tiktok.thumbnail_storage.httpx.AsyncClient",
            _client_factory(handler),
        ),
    ):
        with pytest.raises(TikTokThumbnailStorageError):
            asyncio.run(
                mirror_tiktok_thumbnail("recipe-1", "https://tiktok.example/thumb.jpg")
            )

    assert bucket.uploaded == []


def test_delete_tiktok_thumbnail_removes_the_object():
    bucket = _FakeBucket()
    client = _FakeSupabaseClient(bucket)

    with patch(
        "app.services.social.thumbnail_storage.get_supabase_client",
        return_value=client,
    ):
        delete_tiktok_thumbnail("tiktok/recipe-1/abc.jpg")

    assert bucket.removed == ["tiktok/recipe-1/abc.jpg"]


def test_delete_tiktok_thumbnail_wraps_storage_failures_as_tiktok_error():
    with patch(
        "app.services.social.thumbnail_storage.get_supabase_client",
        return_value=None,
    ):
        with pytest.raises(TikTokThumbnailStorageError):
            delete_tiktok_thumbnail("tiktok/recipe-1/abc.jpg")
