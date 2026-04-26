from functools import lru_cache
from typing import Optional

from supabase import Client, create_client

from ..core.config import Settings


@lru_cache(maxsize=1)
def get_supabase_client(settings: Settings) -> Optional[Client]:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None

    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@lru_cache(maxsize=1)
def get_supabase_public_client(settings: Settings) -> Optional[Client]:
    if not settings.supabase_url or not settings.supabase_publishable_key:
        return None

    return create_client(settings.supabase_url, settings.supabase_publishable_key)


def get_supabase_auth_client(settings: Settings) -> Optional[Client]:
    return get_supabase_public_client(settings)


def get_supabase_user_client(
    settings: Settings, access_token: str
) -> Optional[Client]:
    public_client = get_supabase_public_client(settings)
    if public_client is None:
        return None

    client = create_client(settings.supabase_url, settings.supabase_publishable_key)
    client.postgrest.auth(access_token)
    return client
