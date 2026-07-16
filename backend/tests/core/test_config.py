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


def test_gemini_settings_fall_back_to_defaults(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("GEMINI_RATE_LIMIT_PER_MINUTE", raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert not settings.gemini_api_key
        assert settings.gemini_model == "gemini-3.1-flash-lite"
        assert settings.gemini_timeout_seconds == 30.0
        assert settings.gemini_rate_limit_per_minute == 3
    finally:
        get_settings.cache_clear()


def test_gemini_settings_parse_env_values(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("GEMINI_RATE_LIMIT_PER_MINUTE", "5")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.gemini_api_key == "test-key"
        assert settings.gemini_model == "gemini-custom"
        assert settings.gemini_timeout_seconds == 12.5
        assert settings.gemini_rate_limit_per_minute == 5
    finally:
        get_settings.cache_clear()
