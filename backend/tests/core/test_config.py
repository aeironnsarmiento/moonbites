from app.core.config import DEFAULT_CORS_ORIGINS, normalize_cors_origins


def test_normalize_cors_origins_removes_trailing_slashes():
    assert normalize_cors_origins("https://moonbites-blue.vercel.app/") == (
        "https://moonbites-blue.vercel.app",
    )


def test_normalize_cors_origins_trims_and_ignores_empty_entries():
    origins = normalize_cors_origins(
        " https://moonbites-blue.vercel.app/ , , http://localhost:5173/ "
    )

    assert origins == (
        "https://moonbites-blue.vercel.app",
        "http://localhost:5173",
    )


def test_normalize_cors_origins_uses_local_dev_defaults_when_missing():
    assert normalize_cors_origins("") == DEFAULT_CORS_ORIGINS
