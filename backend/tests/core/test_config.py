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


def test_instagram_apify_settings_use_pinned_safe_defaults(monkeypatch):
    for name in (
        "INSTAGRAM_APIFY_TOKEN",
        "INSTAGRAM_REEL_ACTOR_ID",
        "INSTAGRAM_PROFILE_ACTOR_ID",
        "INSTAGRAM_REEL_ACTOR_BUILD",
        "INSTAGRAM_PROFILE_ACTOR_BUILD",
        "INSTAGRAM_REEL_MAX_CHARGE_USD",
        "INSTAGRAM_PROFILE_MAX_CHARGE_USD",
        "INSTAGRAM_MONTHLY_USAGE_STOP_USD",
        "INSTAGRAM_REEL_ACTOR_TIMEOUT_SECONDS",
        "INSTAGRAM_PROFILE_ACTOR_TIMEOUT_SECONDS",
        "INSTAGRAM_REQUEST_DEADLINE_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.instagram_apify_token is None
        assert settings.instagram_reel_actor_id == "xMc5Ga1oCONPmWJIa"
        assert settings.instagram_profile_actor_id == "dSCLg0C3YEZ83HzYX"
        assert settings.instagram_reel_actor_build == "0.0.542"
        assert settings.instagram_profile_actor_build == "0.0.580"
        assert settings.instagram_reel_max_charge_usd == 0.0073
        assert settings.instagram_profile_max_charge_usd == 0.0026
        assert settings.instagram_monthly_usage_stop_usd == 4.5
        assert settings.instagram_reel_actor_timeout_seconds == 120.0
        assert settings.instagram_profile_actor_timeout_seconds == 120.0
        assert settings.instagram_request_deadline_seconds == 45.0
    finally:
        get_settings.cache_clear()


def test_instagram_apify_settings_parse_env_values(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_APIFY_TOKEN", "token")
    monkeypatch.setenv("INSTAGRAM_REEL_ACTOR_ID", "reel")
    monkeypatch.setenv("INSTAGRAM_PROFILE_ACTOR_ID", "profile")
    monkeypatch.setenv("INSTAGRAM_REEL_ACTOR_BUILD", "1.2.3")
    monkeypatch.setenv("INSTAGRAM_PROFILE_ACTOR_BUILD", "2.3.4")
    monkeypatch.setenv("INSTAGRAM_REEL_MAX_CHARGE_USD", "0.001")
    monkeypatch.setenv("INSTAGRAM_PROFILE_MAX_CHARGE_USD", "0.002")
    monkeypatch.setenv("INSTAGRAM_MONTHLY_USAGE_STOP_USD", "4.25")
    monkeypatch.setenv("INSTAGRAM_REEL_ACTOR_TIMEOUT_SECONDS", "100")
    monkeypatch.setenv("INSTAGRAM_PROFILE_ACTOR_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("INSTAGRAM_REQUEST_DEADLINE_SECONDS", "40")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.instagram_apify_token == "token"
        assert settings.instagram_reel_actor_id == "reel"
        assert settings.instagram_profile_actor_id == "profile"
        assert settings.instagram_reel_actor_build == "1.2.3"
        assert settings.instagram_profile_actor_build == "2.3.4"
        assert settings.instagram_reel_max_charge_usd == 0.001
        assert settings.instagram_profile_max_charge_usd == 0.002
        assert settings.instagram_monthly_usage_stop_usd == 4.25
        assert settings.instagram_reel_actor_timeout_seconds == 100.0
        assert settings.instagram_profile_actor_timeout_seconds == 90.0
        assert settings.instagram_request_deadline_seconds == 40.0
    finally:
        get_settings.cache_clear()
