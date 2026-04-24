import os

# Prevent the application settings cache from picking up any Supabase creds
# during test runs. Individual tests that need settings will patch explicitly.
os.environ.setdefault("SUPABASE_URL", "")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "")
