"""FastAPI application entry point.

Contains HTTP routes only:
- Existing task CRUD routes, unchanged, delegating to the repository layer.
- New authentication routes (signup/login/logout) backed by Supabase Auth.
- A public route requiring no authentication.
- Protected routes requiring a valid Supabase bearer token.
"""

import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel

from database import run_init_script, wait_for_database
from dependencies import AuthenticatedUser, get_current_user
from models import StatsResponse, TaskCreate, TaskResponse, TaskUpdate
from repository import task_repository
from supabase_client import get_supabase_client

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 6


# --------------------------------------------------------------------------
# Auth request/response models
# --------------------------------------------------------------------------
class SignupRequest(BaseModel):
    """Payload required to register a new user."""

    email: str
    password: str


class LoginRequest(BaseModel):
    """Payload required to authenticate a user."""

    email: str
    password: str


class SignupResponse(BaseModel):
    """Representation of a newly created user."""

    id: str
    email: str | None


class TokenResponse(BaseModel):
    """Supabase session tokens returned after a successful login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ProfileResponse(BaseModel):
    """Authenticated user's profile information."""

    id: str
    email: str | None


class DashboardResponse(BaseModel):
    """Authenticated dashboard view combining identity and task statistics."""

    user_id: str
    email: str | None
    stats: StatsResponse


class PublicInfoResponse(BaseModel):
    """Public, unauthenticated service metadata."""

    service: str
    version: str
    status: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Wait for PostgreSQL to be ready and initialize the schema on startup."""
    wait_for_database()
    run_init_script()
    yield


app = FastAPI(
    title="Task API",
    description=(
        "A production-ready CRUD API for managing tasks, backed by "
        "PostgreSQL, with Supabase-authenticated routes."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


def _validate_credentials(email: str, password: str) -> None:
    """Validate that email and password are present and well-formed.

    Args:
        email: The email address to validate.
        password: The password to validate.

    Raises:
        HTTPException: 400 if either field is missing, empty, or invalid.
    """
    if not email or not email.strip():
        raise HTTPException(status_code=400, detail="email is required")
    if not password:
        raise HTTPException(status_code=400, detail="password is required")
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="invalid email format")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"password must be at least {MIN_PASSWORD_LENGTH} characters",
        )


# --------------------------------------------------------------------------
# Authentication routes
# --------------------------------------------------------------------------
@app.post("/auth/signup", response_model=SignupResponse, status_code=201)
def signup(payload: SignupRequest) -> SignupResponse:
    """Register a new user via Supabase Auth.

    Args:
        payload: The new user's email and password.

    Returns:
        SignupResponse: The id and email of the newly created user.

    Raises:
        HTTPException: 400 if input is missing/invalid or Supabase rejects
            the signup (e.g. malformed email, weak password, existing user).
    """
    _validate_credentials(payload.email, payload.password)
    supabase = get_supabase_client()

    try:
        result = supabase.auth.sign_up(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if result.user is None:
        raise HTTPException(status_code=400, detail="signup failed")

    return SignupResponse(id=result.user.id, email=result.user.email)


@app.post("/auth/login", response_model=TokenResponse, status_code=200)
def login(payload: LoginRequest) -> TokenResponse:
    """Authenticate a user and return Supabase session tokens.

    Args:
        payload: The user's email and password.

    Returns:
        TokenResponse: The access and refresh tokens for the new session.

    Raises:
        HTTPException: 400 if input is missing, 401 if credentials are
            invalid.
    """
    if not payload.email or not payload.email.strip():
        raise HTTPException(status_code=400, detail="email is required")
    if not payload.password:
        raise HTTPException(status_code=400, detail="password is required")

    supabase = get_supabase_client()

    try:
        result = supabase.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as error:
        raise HTTPException(
            status_code=401, detail="invalid email or password"
        ) from error

    if result.session is None:
        raise HTTPException(status_code=401, detail="invalid email or password")

    return TokenResponse(
        access_token=result.session.access_token,
        refresh_token=result.session.refresh_token,
    )


@app.post("/auth/logout", status_code=204)
def logout(current_user: AuthenticatedUser = Depends(get_current_user)) -> Response:
    """Sign the authenticated user out of their Supabase session.

    Args:
        current_user: The authenticated user, resolved from the bearer token.

    Returns:
        Response: An empty 204 No Content response.
    """
    supabase = get_supabase_client()
    try:
        supabase.auth.sign_out()
    except Exception as error:
        raise HTTPException(status_code=401, detail="logout failed") from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Public route
# --------------------------------------------------------------------------
@app.get("/public/info", response_model=PublicInfoResponse)
def public_info() -> PublicInfoResponse:
    """Return public service metadata. Requires no authentication.

    Returns:
        PublicInfoResponse: Basic, non-sensitive service information.
    """
    return PublicInfoResponse(service="Task API", version=app.version, status="ok")


# --------------------------------------------------------------------------
# Protected routes
# --------------------------------------------------------------------------
@app.get("/protected/profile", response_model=ProfileResponse)
def get_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ProfileResponse:
    """Return the authenticated user's profile.

    Args:
        current_user: The authenticated user, resolved from the bearer token.

    Returns:
        ProfileResponse: The user's id and email.
    """
    return ProfileResponse(id=current_user.id, email=current_user.email)


@app.get("/protected/dashboard", response_model=DashboardResponse)
def get_dashboard(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> DashboardResponse:
    """Return a dashboard view combining user identity and task statistics.

    Args:
        current_user: The authenticated user, resolved from the bearer token.

    Returns:
        DashboardResponse: The user's identity alongside aggregate task stats.
    """
    stats = task_repository.get_stats()
    return DashboardResponse(
        user_id=current_user.id, email=current_user.email, stats=stats
    )


# --------------------------------------------------------------------------
# Existing task CRUD routes (unchanged behavior)
# --------------------------------------------------------------------------
@app.get("/tasks", response_model=list[TaskResponse])
def list_tasks(
    search: str | None = Query(default=None, description="Filter tasks by title substring"),
    done: bool | None = Query(default=None, description="Filter tasks by completion status"),
) -> list[dict]:
    """Return all tasks, optionally filtered by search term and/or completion status."""
    return task_repository.list_tasks(search=search, done=done)


@app.get("/stats", response_model=StatsResponse)
def get_stats() -> dict:
    """Return aggregate statistics about tasks."""
    return task_repository.get_stats()


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int) -> dict:
    """Return a single task by id."""
    if task_id <= 0:
        raise HTTPException(status_code=400, detail="task_id must be a positive integer")

    task = task_repository.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")
    return task


@app.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(payload: TaskCreate) -> dict:
    """Create a new task."""
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="title must not be empty")

    return task_repository.create_task(title=payload.title.strip(), done=payload.done)


@app.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, payload: TaskUpdate) -> dict:
    """Update an existing task."""
    if task_id <= 0:
        raise HTTPException(status_code=400, detail="task_id must be a positive integer")
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="title must not be empty")

    updated_task = task_repository.update_task(
        task_id=task_id, title=payload.title.strip(), done=payload.done
    )
    if updated_task is None:
        raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")
    return updated_task


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int) -> Response:
    """Delete a task by id."""
    if task_id <= 0:
        raise HTTPException(status_code=400, detail="task_id must be a positive integer")

    deleted = task_repository.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)