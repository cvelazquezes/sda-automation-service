"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class AutomationTaskStatus(str, Enum):
    """Status of an automation task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Types of automation tasks."""

    LOGIN = "login"
    EXTRACT_PROFILE = "extract_profile"
    EXTRACT_TASKS = "extract_tasks"
    EXTRACT_SPECIALTIES = "extract_specialties"
    CUSTOM = "custom"


# =============================================================================
# Health Check
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    environment: str
    browser_ready: bool = False


# =============================================================================
# Authentication
# =============================================================================


class LoginRequest(BaseModel):
    """Login request payload."""

    username: str = Field(..., min_length=1, description="Club Virtual username")
    password: str = Field(..., min_length=1, description="Club Virtual password")
    club_id: int | None = Field(None, description="Club ID to select after login")
    save_session: bool = Field(True, description="Save session for reuse")


class LoginResponse(BaseModel):
    """Login response payload."""

    success: bool
    message: str
    session_id: str | None = None
    user: "UserProfile | None" = None
    clubs: list["ClubInfo"] = []
    screenshot_path: str | None = None


# =============================================================================
# User & Club
# =============================================================================


class UserProfile(BaseModel):
    """User profile information."""

    username: str
    full_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    role: str | None = None


class ClubInfo(BaseModel):
    """Club information."""

    id: int
    name: str
    role: str  # e.g., "Miembro", "Director", etc.


# =============================================================================
# Tasks
# =============================================================================


class AutomationTaskCreate(BaseModel):
    """Create automation task request."""

    task_type: TaskType
    session_id: str | None = Field(None, description="Existing session ID to use")
    credentials: LoginRequest | None = Field(None, description="Credentials if no session")
    parameters: dict[str, Any] = Field(default_factory=dict)
    webhook_url: str | None = Field(None, description="URL to notify on completion")


class AutomationTask(BaseModel):
    """Automation task model."""

    id: str
    task_type: TaskType
    status: AutomationTaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: "TaskResult | None" = None
    error: str | None = None


class TaskResult(BaseModel):
    """Result of an automation task."""

    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    screenshots: list[str] = Field(default_factory=list)
    duration_ms: int = 0


# =============================================================================
# Specialties & Activities
# =============================================================================


class Specialty(BaseModel):
    """Pathfinder specialty information."""

    id: str
    name: str
    category: str | None = None
    classes: list[str] = []  # e.g., ["Amigo", "Compañero", "Explorador"]
    is_new: bool = False


class Activity(BaseModel):
    """Club activity information."""

    id: str
    name: str
    date: datetime | None = None
    status: str | None = None
    points: int | None = None
