import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
DEFAULT_SUPABASE_TABLE = "recipe_imports"


@dataclass(frozen=True)
class Settings:
    request_timeout_seconds: float
    supabase_url: str | None
    supabase_service_role_key: str | None
    supabase_table_name: str
    cors_origins: tuple[str, ...]
    user_agent: str
    accept_header: str
    accept_language_header: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    cors_origins_value = os.getenv("BACKEND_CORS_ORIGINS", "")
    cors_origins = tuple(
        origin.strip() for origin in cors_origins_value.split(",") if origin.strip()
    ) or DEFAULT_CORS_ORIGINS

    return Settings(
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15.0")),
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        supabase_table_name=os.getenv("SUPABASE_TABLE_NAME", DEFAULT_SUPABASE_TABLE),
        cors_origins=cors_origins,
        user_agent=os.getenv(
            "REQUEST_USER_AGENT",
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            ),
        ),
        accept_header=os.getenv(
            "REQUEST_ACCEPT_HEADER",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        ),
        accept_language_header=os.getenv(
            "REQUEST_ACCEPT_LANGUAGE_HEADER",
            "en-US,en;q=0.9",
        ),
    )