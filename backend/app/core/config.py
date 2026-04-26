import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
DEFAULT_SUPABASE_TABLE = "recipe_imports"


@dataclass(frozen=True)
class Settings:
    request_timeout_seconds: float
    supabase_url: Optional[str]
    supabase_publishable_key: Optional[str]
    supabase_service_role_key: Optional[str]
    supabase_table_name: str
    admin_emails: tuple[str, ...]
    cors_origins: tuple[str, ...]
    user_agent: str
    accept_header: str
    accept_language_header: str


def normalize_cors_origins(value: str) -> tuple[str, ...]:
    origins = tuple(
        normalized_origin
        for origin in value.split(",")
        if (normalized_origin := origin.strip().rstrip("/"))
    )
    return origins or DEFAULT_CORS_ORIGINS


def normalize_admin_emails(value: str) -> tuple[str, ...]:
    return tuple(
        normalized_email
        for email in value.split(",")
        if (normalized_email := email.strip().casefold())
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    cors_origins_value = os.getenv("BACKEND_CORS_ORIGINS", "")
    cors_origins = normalize_cors_origins(cors_origins_value)

    return Settings(
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15.0")),
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_publishable_key=os.getenv("SUPABASE_PUBLISHABLE_KEY"),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        supabase_table_name=os.getenv("SUPABASE_TABLE_NAME", DEFAULT_SUPABASE_TABLE),
        admin_emails=normalize_admin_emails(os.getenv("ADMIN_EMAILS", "")),
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
