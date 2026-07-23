"""Authentication dependencies.

Exposes a reusable FastAPI dependency that extracts a bearer token from the
``Authorization`` header, verifies it against Supabase, and returns the
authenticated user. This module is intentionally isolated from database and
routing logic so authentication concerns stay decoupled from persistence and
HTTP handling.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from supabase_client import get_supabase_client

# auto_error=False lets us return a 401 (instead of FastAPI's default 403)
# when the Authorization header is missing or malformed.
bearer_scheme = HTTPBearer(
    scheme_name="SupabaseBearer",
    description="Supabase access token issued by POST /auth/login",
    auto_error=False,
)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired authentication credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Minimal representation of a user authenticated via Supabase.

    Attributes:
        id: The Supabase user id (UUID string).
        email: The user's email address, if available.
    """

    id: str
    email: str | None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """Resolve and validate the current user from a Supabase bearer token.

    Extracts the token from the ``Authorization: Bearer <token>`` header,
    verifies it via ``supabase.auth.get_user(token)``, and returns the
    corresponding authenticated user.

    Args:
        credentials: Parsed Authorization header credentials, injected by
            the ``HTTPBearer`` security scheme.

    Returns:
        AuthenticatedUser: The user associated with the verified token.

    Raises:
        HTTPException: With status 401 if the header is missing, malformed,
            or the token cannot be verified by Supabase.
    """
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED

    if credentials.scheme.lower() != "bearer":
        raise _UNAUTHORIZED

    token = credentials.credentials
    supabase = get_supabase_client()

    try:
        user_response = supabase.auth.get_user(token)
    except Exception as error:
        raise _UNAUTHORIZED from error

    if user_response is None or user_response.user is None:
        raise _UNAUTHORIZED

    return AuthenticatedUser(id=user_response.user.id, email=user_response.user.email)