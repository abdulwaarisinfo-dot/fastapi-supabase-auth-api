"""Supabase client initialization.

Provides a single, cached Supabase client instance configured from
environment variables. This module contains no business or HTTP logic —
its only responsibility is constructing and exposing the Supabase client
used for authentication.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
SUPABASE_KEY: str | None = os.getenv("SUPABASE_KEY")


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Return a cached Supabase client configured from environment variables.

    The client is created once and reused across requests for efficiency.

    Returns:
        Client: A ready-to-use Supabase client instance.

    Raises:
        RuntimeError: If ``SUPABASE_URL`` or ``SUPABASE_KEY`` is not set in
            the environment.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in the environment"
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)