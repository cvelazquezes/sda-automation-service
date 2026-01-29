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


class ClubType(str, Enum):
    """Types of clubs in Club Virtual."""

    CONQUISTADORES = "Conquistadores"
    GUIAS_MAYORES = "Guías Mayores"
    AVENTUREROS = "Aventureros"


class SimpleLoginRequest(BaseModel):
    """Simple login request - just credentials."""

    username: str = Field(..., min_length=1, description="Club Virtual username")
    password: str = Field(..., min_length=1, description="Club Virtual password")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "usuario123",
                    "password": "contraseña123",
                }
            ]
        }
    }


class SimpleLoginResponse(BaseModel):
    """Simple login response - just success/failure message."""

    success: bool = Field(..., description="Whether login was successful")
    message: str = Field(..., description="Human-readable result message")
    username: str = Field(..., description="Username that was used")
    user_name: str | None = Field(None, description="User's full name if login successful")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "¡Bienvenido! Login exitoso para Juan Pérez",
                    "username": "juanperez123",
                    "user_name": "Juan Pérez",
                },
                {
                    "success": False,
                    "message": "Credenciales inválidas. Usuario o contraseña incorrectos.",
                    "username": "usuario123",
                    "user_name": None,
                },
            ]
        }
    }


class LoginRequest(BaseModel):
    """Full login request payload with club selection options."""

    username: str = Field(..., min_length=1, description="Club Virtual username")
    password: str = Field(..., min_length=1, description="Club Virtual password")
    club_type: ClubType | None = Field(
        None,
        description="Type of club: Conquistadores, Guías Mayores, or Aventureros",
    )
    club_name: str | None = Field(
        None,
        description="Name of the club to select (partial match supported)",
    )
    club_id: int | None = Field(
        None,
        description="Direct club ID (alternative to club_type + club_name)",
    )
    save_session: bool = Field(True, description="Save session for reuse")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "usuario123",
                    "password": "contraseña123",
                    "club_type": "Aventureros",
                    "club_name": "Club Peniel",
                    "save_session": True,
                },
                {
                    "username": "usuario123",
                    "password": "contraseña123",
                    "club_type": "Conquistadores",
                    "club_name": "Leones de Judá",
                    "save_session": True,
                },
            ]
        }
    }


class LoginResponse(BaseModel):
    """Full login response payload with session and user info."""

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
    """
    Complete user profile information from Club Virtual.

    This model contains all the information available on the user's profile page.
    Fields may be None if not filled by the user or not available.

    Basic Information (Información Básica):
        - account_number: Unique account identifier in Club Virtual
        - username: Login username
        - full_name: Complete name (nombre completo)
        - gender: Gender (Masculino/Femenino/Otro)
        - birthday: Birth date as string (e.g., "April 09, 2018")
        - age: Calculated age in years

    Contact Information (Información de Contacto):
        - email: Email address (correo electrónico)
        - phone: Phone number (teléfono)
        - address: Physical address (dirección)
        - bio: User presentation/bio (mi presentación)

    Social Media:
        - twitter: Twitter handle
        - facebook: Facebook profile
        - instagram: Instagram handle

    Other:
        - avatar_url: Profile picture URL
        - role: User's role in the club
    """

    # Basic Information
    account_number: str | None = Field(None, description="Club Virtual account number")
    username: str = Field(..., description="Login username")
    full_name: str | None = Field(None, description="Full name (nombre completo)")
    gender: str | None = Field(None, description="Gender (Masculino/Femenino)")
    birthday: str | None = Field(None, description="Birth date string")
    age: float | None = Field(None, description="Age in years")

    # Contact Information
    email: str | None = Field(None, description="Email address")
    phone: str | None = Field(None, description="Phone number")
    address: str | None = Field(None, description="Physical address")
    bio: str | None = Field(None, description="User presentation/bio")

    # Social Media
    twitter: str | None = Field(None, description="Twitter handle")
    facebook: str | None = Field(None, description="Facebook profile")
    instagram: str | None = Field(None, description="Instagram handle")

    # Other
    avatar_url: str | None = Field(None, description="Profile picture URL")
    role: str | None = Field(None, description="Role in the club")


class ClubInfo(BaseModel):
    """Club information."""

    id: int
    name: str
    club_type: str | None = None  # e.g., "Aventureros", "Conquistadores", "Guías Mayores"
    role: str  # e.g., "Miembro", "Director", etc.
    full_text: str | None = None  # Original full text from the page


# =============================================================================
# Active Classes / Courses
# =============================================================================


class ActiveClass(BaseModel):
    """
    Information about an active class/course the user is enrolled in.

    In Club Virtual, users are assigned to classes based on their age and progress.
    Each class has tasks that need to be completed for investiture.

    Aventureros Classes (ages 6-9):
        - Abejas (Bees) - Age 6
        - Rayitos de Sol (Sunbeams) - Age 7
        - Constructores (Builders) - Age 8
        - Manos Ayudadoras (Helping Hands) - Age 9

    Conquistadores Classes (ages 10-15):
        - Amigo (Friend) - Age 10
        - Compañero (Companion) - Age 11
        - Explorador (Explorer) - Age 12
        - Orientador (Ranger) - Age 13
        - Viajero (Voyager) - Age 14
        - Guía (Guide) - Age 15
    """

    name: str = Field(..., description="Class name (e.g., 'Abejas', 'Amigo')")
    completion_percentage: float = Field(
        ...,
        description="Percentage of tasks completed (0-100)",
        ge=0,
        le=100,
    )
    status: str | None = Field(
        None,
        description="Current status (e.g., 'En progreso', 'Completado', 'Autorizado para investir')",
    )
    is_ready_for_investiture: bool = Field(
        False,
        description="Whether the user has completed all requirements for investiture",
    )
    image_url: str | None = Field(None, description="URL of the class badge/logo")


class TasksAndReportsResponse(BaseModel):
    """
    Response containing user's active classes and task progress.

    This response is returned by the /tasks-and-reports endpoint
    after navigating to "Mis tareas y reportes" in Club Virtual.
    """

    success: bool = Field(..., description="Whether extraction was successful")
    message: str = Field(..., description="Status message")
    session_id: str | None = Field(None, description="Session ID used")
    active_classes: list[ActiveClass] = Field(
        default_factory=list,
        description="List of active classes the user is enrolled in",
    )
    total_classes: int = Field(0, description="Total number of active classes")
    overall_completion: float | None = Field(
        None,
        description="Overall completion percentage across all classes",
    )
    screenshot_path: str | None = Field(None, description="Path to screenshot")


# =============================================================================
# Combined Extraction (Orchestrator)
# =============================================================================


class ExtractRequest(BaseModel):
    """
    Request for the combined extraction endpoint.

    This endpoint allows extracting multiple types of data in a single call.
    The login is performed once, then each requested extractor is run.

    Available Extractors:
        - profile: User profile information (name, email, birthday, etc.)
        - tasks: Active classes and task completion progress

    Example Usage:
        # Extract only profile
        {"username": "user", "password": "pass", "include": ["profile"]}

        # Extract profile and tasks with club selection
        {
            "username": "user",
            "password": "pass",
            "club_type": "Aventureros",
            "club_name": "Peniel",
            "include": ["profile", "tasks"]
        }

        # Extract all available data (default)
        {"username": "user", "password": "pass"}
    """

    username: str = Field(..., min_length=1, description="Club Virtual username")
    password: str = Field(..., min_length=1, description="Club Virtual password")
    club_type: ClubType | None = Field(
        None,
        description="Type of club: Conquistadores, Guías Mayores, or Aventureros",
    )
    club_name: str | None = Field(
        None,
        description="Name of the club to select (partial match supported)",
    )
    club_id: int | None = Field(
        None,
        description="Direct club ID (alternative to club_type + club_name)",
    )
    include: list[str] | None = Field(
        None,
        description="List of extractors to run (e.g., ['profile', 'tasks']). "
        "If not specified, all extractors are run.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "usuario123",
                    "password": "contraseña123",
                    "club_type": "Aventureros",
                    "club_name": "Club Peniel",
                    "include": ["profile", "tasks"],
                },
                {
                    "username": "usuario123",
                    "password": "contraseña123",
                    "include": ["profile"],
                },
            ]
        }
    }


class ExtractResponse(BaseModel):
    """
    Response from the combined extraction endpoint.

    Contains all requested data in a single response:
    - Login info (clubs, selected club)
    - Profile data (if requested)
    - Tasks data (if requested)
    - Metadata (timestamp, screenshot, errors)

    Structure:
        {
            "success": true,
            "message": "Club: Peniel (Aventureros) | Extracted: profile, tasks",
            "session_id": "uuid",
            "login": {
                "clubs": [...],
                "selected_club": {...}
            },
            "profile": {
                "full_name": "Juan Pérez",
                "email": "juan@email.com",
                ...
            },
            "tasks": {
                "active_classes": [...],
                "overall_completion": 85.5
            },
            "extracted_at": "2024-01-28T15:30:00",
            "screenshot_path": "/path/to/screenshot.png"
        }
    """

    success: bool = Field(..., description="Whether extraction was successful")
    message: str = Field(..., description="Human-readable result message")
    session_id: str | None = Field(None, description="Session ID (for reference only)")

    # Login info
    login: dict[str, Any] | None = Field(
        None,
        description="Login info with available clubs and selected club",
    )

    # Extracted data (each key corresponds to an extractor name)
    profile: dict[str, Any] | None = Field(
        None,
        description="User profile data (if 'profile' was in include)",
    )
    tasks: dict[str, Any] | None = Field(
        None,
        description="Tasks and active classes data (if 'tasks' was in include)",
    )
    specialties: dict[str, Any] | None = Field(
        None,
        description="Specialties data (if 'specialties' was in include)",
    )

    # Metadata
    extracted_at: str | None = Field(None, description="ISO timestamp of extraction")
    screenshot_path: str | None = Field(None, description="Path to screenshot")
    errors: list[str] | None = Field(
        None,
        description="List of errors for extractors that failed",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Club: Peniel (Aventureros) | Extracted: profile, tasks",
                    "session_id": "abc123",
                    "login": {
                        "clubs": [{"id": 123, "name": "Peniel", "club_type": "Aventureros"}],
                        "selected_club": {
                            "id": 123,
                            "name": "Peniel",
                            "club_type": "Aventureros",
                        },
                    },
                    "profile": {
                        "full_name": "Juan Pérez",
                        "email": "juan@email.com",
                        "age": 8,
                    },
                    "tasks": {
                        "active_classes": [
                            {
                                "name": "Constructores",
                                "completion_percentage": 75,
                                "status": "En progreso",
                            }
                        ],
                        "overall_completion": 75,
                    },
                    "extracted_at": "2024-01-28T15:30:00",
                },
            ]
        }
    }


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
