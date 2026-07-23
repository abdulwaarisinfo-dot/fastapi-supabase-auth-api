"""Pydantic request and response models for the Task API."""

from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    """Payload required to create a new task."""

    title: str = Field(..., min_length=1, max_length=255)
    done: bool = False


class TaskUpdate(BaseModel):
    """Payload required to update an existing task."""

    title: str = Field(..., min_length=1, max_length=255)
    done: bool = False


class TaskResponse(BaseModel):
    """Representation of a task returned by the API."""

    id: int
    title: str
    done: bool
    created_at: datetime
    updated_at: datetime


class StatsResponse(BaseModel):
    """Aggregate task statistics."""

    total_tasks: int
    completed_tasks: int
    pending_tasks: int


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    detail: str