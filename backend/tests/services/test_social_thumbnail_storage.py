from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest
from storage3.exceptions import StorageApiError

from app.services.social.thumbnail_storage import (
    SocialThumbnailStorageError,
    build_storage_path,
    delete_social_thumbnail,
    store_social_thumbnail,
)


class _FakeBucket:
    def __init__(self, *, upload_error=None):
        self.uploaded: list[tuple] = []
        self.removed: list[str] = []
        self.upload_error = upload_error

    def upload(self, *, path, file, file_options):
        self.uploaded.append((path, file, file_options))
        if self.upload_error is not None:
            raise self.upload_error

    def get_public_url(self, path):
        return f"https://cdn.example/{path}"

    def remove(self, paths):
        self.removed.extend(paths)


class _FakeStorage:
    def __init__(self, bucket):
        self._bucket = bucket

    def from_(self, _bucket_name):
        return self._bucket


class _FakeClient:
    def __init__(self, bucket):
        self.storage = _FakeStorage(bucket)


def _patched(client):
    return (
        patch("app.services.social.thumbnail_storage.get_settings"),
        patch(
            "app.services.social.thumbnail_storage.get_supabase_client",
            return_value=client,
        ),
    )


def test_build_storage_path_uses_allowlisted_platform_segment():
    assert build_storage_path("tiktok", "recipe-1", "abc123", "jpg") == (
        "tiktok/recipe-1/abc123.jpg"
    )
    assert build_storage_path("instagram", "recipe-1", "abc123", "webp") == (
        "instagram/recipe-1/abc123.webp"
    )


def test_build_storage_path_rejects_unknown_platform():
    with pytest.raises(SocialThumbnailStorageError):
        build_storage_path("youtube", "recipe-1", "abc123", "jpg")


def test_store_social_thumbnail_uploads_and_returns_public_url():
    bucket = _FakeBucket()
    client = _FakeClient(bucket)

    with patch("app.services.social.thumbnail_storage.get_settings"), patch(
        "app.services.social.thumbnail_storage.get_supabase_client",
        return_value=client,
    ):
        result = store_social_thumbnail(
            "instagram", "recipe-1", b"binary-content", "image/webp"
        )

    digest = hashlib.sha256(b"binary-content").hexdigest()
    expected_path = f"instagram/recipe-1/{digest}.webp"
    assert result.storage_path == expected_path
    assert result.image_url == f"https://cdn.example/{expected_path}"
    path, file, file_options = bucket.uploaded[0]
    assert path == expected_path
    assert file == b"binary-content"
    assert file_options["content-type"] == "image/webp"
    assert file_options["upsert"] == "false"


def test_store_social_thumbnail_rejects_unsupported_content_type():
    bucket = _FakeBucket()
    client = _FakeClient(bucket)

    with patch("app.services.social.thumbnail_storage.get_settings"), patch(
        "app.services.social.thumbnail_storage.get_supabase_client",
        return_value=client,
    ):
        with pytest.raises(SocialThumbnailStorageError):
            store_social_thumbnail("instagram", "recipe-1", b"data", "image/gif")

    assert bucket.uploaded == []


def test_store_social_thumbnail_rejects_oversized_and_empty_content():
    bucket = _FakeBucket()
    client = _FakeClient(bucket)

    with patch("app.services.social.thumbnail_storage.get_settings"), patch(
        "app.services.social.thumbnail_storage.get_supabase_client",
        return_value=client,
    ):
        with pytest.raises(SocialThumbnailStorageError):
            store_social_thumbnail(
                "instagram", "recipe-1", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg"
            )
        with pytest.raises(SocialThumbnailStorageError):
            store_social_thumbnail("instagram", "recipe-1", b"", "image/jpeg")

    assert bucket.uploaded == []


def test_store_social_thumbnail_rejects_unknown_platform_before_touching_client():
    bucket = _FakeBucket()
    client = _FakeClient(bucket)

    with patch("app.services.social.thumbnail_storage.get_settings"), patch(
        "app.services.social.thumbnail_storage.get_supabase_client",
        return_value=client,
    ):
        with pytest.raises(SocialThumbnailStorageError):
            store_social_thumbnail("youtube", "recipe-1", b"data", "image/jpeg")

    assert bucket.uploaded == []


def test_store_social_thumbnail_swallows_existing_object_conflict():
    bucket = _FakeBucket(
        upload_error=StorageApiError("The resource already exists", "Duplicate", 409)
    )
    client = _FakeClient(bucket)

    with patch("app.services.social.thumbnail_storage.get_settings"), patch(
        "app.services.social.thumbnail_storage.get_supabase_client",
        return_value=client,
    ):
        result = store_social_thumbnail(
            "tiktok", "recipe-1", b"binary-content", "image/jpeg"
        )

    assert result.storage_path.startswith("tiktok/recipe-1/")


def test_store_social_thumbnail_raises_on_other_upload_failures():
    bucket = _FakeBucket(upload_error=StorageApiError("Internal error", "Error", 500))
    client = _FakeClient(bucket)

    with patch("app.services.social.thumbnail_storage.get_settings"), patch(
        "app.services.social.thumbnail_storage.get_supabase_client",
        return_value=client,
    ):
        with pytest.raises(SocialThumbnailStorageError):
            store_social_thumbnail("tiktok", "recipe-1", b"data", "image/jpeg")


def test_store_social_thumbnail_raises_when_supabase_not_configured():
    with patch("app.services.social.thumbnail_storage.get_settings"), patch(
        "app.services.social.thumbnail_storage.get_supabase_client",
        return_value=None,
    ):
        with pytest.raises(SocialThumbnailStorageError):
            store_social_thumbnail("tiktok", "recipe-1", b"data", "image/jpeg")


def test_delete_social_thumbnail_removes_the_object():
    bucket = _FakeBucket()
    client = _FakeClient(bucket)

    with patch("app.services.social.thumbnail_storage.get_settings"), patch(
        "app.services.social.thumbnail_storage.get_supabase_client",
        return_value=client,
    ):
        delete_social_thumbnail("tiktok/recipe-1/abc.jpg")

    assert bucket.removed == ["tiktok/recipe-1/abc.jpg"]


def test_delete_social_thumbnail_is_a_noop_for_empty_path():
    with patch("app.services.social.thumbnail_storage.get_settings"), patch(
        "app.services.social.thumbnail_storage.get_supabase_client",
    ) as get_client:
        delete_social_thumbnail("")

    get_client.assert_not_called()


def test_delete_social_thumbnail_raises_when_supabase_not_configured():
    with patch("app.services.social.thumbnail_storage.get_settings"), patch(
        "app.services.social.thumbnail_storage.get_supabase_client",
        return_value=None,
    ):
        with pytest.raises(SocialThumbnailStorageError):
            delete_social_thumbnail("tiktok/recipe-1/abc.jpg")
