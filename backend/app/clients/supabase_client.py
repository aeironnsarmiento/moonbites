from functools import lru_cache
from typing import Optional

from supabase import Client, create_client

from ..core.config import Settings


@lru_cache(maxsize=1)
def get_supabase_client(settings: Settings) -> Optional[Client]:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None

    return create_client(settings.supabase_url, settings.supabase_service_role_key)
