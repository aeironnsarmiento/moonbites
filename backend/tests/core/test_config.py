from app.core.config import DEFAULT_CORS_ORIGINS, get_settings, normalize_cors_origins


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


def test_gemini_normalization_is_disabled_when_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_NORMALIZATION_ENABLED", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.gemini_normalization_enabled is False


def test_gemini_normalization_is_disabled_when_blank(monkeypatch):
    monkeypatch.setenv("GEMINI_NORMALIZATION_ENABLED", "")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.gemini_normalization_enabled is False


def test_gemini_normalization_accepts_truthy_values(monkeypatch):
    monkeypatch.setenv("GEMINI_NORMALIZATION_ENABLED", "true")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.gemini_normalization_enabled is True


def test_gemini_defaults(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("GEMINI_RATE_LIMIT_PER_MINUTE", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.gemini_model == "gemini-3-flash-preview"
    assert settings.gemini_timeout_seconds == 10.0
    assert settings.gemini_rate_limit_per_minute == 3
