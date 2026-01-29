"""
API Routes for the Automation Service.

This module defines all HTTP endpoints for the automation service.
It follows RESTful conventions and is organized into logical sections.

ENDPOINT CATEGORIES:
-------------------
1. Health Checks (/health/*) - Service status and readiness
2. Authentication (/auth/*) - Login and logout operations
3. Automation Tasks (/sessions/{id}/*) - Post-login automation flows
4. Session Management (/sessions/*) - Session lifecycle

ADDING NEW ENDPOINTS:
--------------------
To add a new automation flow endpoint:

1. Add the flow method in ClubVirtualService (club_virtual.py)
2. Add the endpoint here following this pattern:

    @router.post("/sessions/{session_id}/my-action", tags=["Automation"])
    async def my_action(
        session_id: str,
        request: MyRequest,  # Define in schemas.py
        club_virtual: Annotated[ClubVirtualService, Depends(get_club_virtual_service)],
    ) -> MyResponse:
        '''Description of what this endpoint does.'''
        try:
            result = await club_virtual.my_new_flow(session_id, **request.model_dump())
            return MyResponse(success=True, data=result)
        except AutomationError as e:
            raise HTTPException(status_code=400, detail=e.message) from e

ERROR HANDLING:
--------------
- LoginError (401): Invalid credentials or club not found
- AutomationError (400/500): General automation failures
- HTTPException (404): Session not found
- HTTPException (503): Browser not ready

All errors include descriptive messages for debugging.
"""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from automation_service.core.config import settings
from automation_service.core.exceptions import AutomationError, LoginError
from automation_service.models.schemas import (
    ExtractRequest,
    ExtractResponse,
    HealthResponse,
    LoginRequest,
    LoginResponse,
    SimpleLoginRequest,
    SimpleLoginResponse,
    TasksAndReportsResponse,
)
from automation_service.services.browser import BrowserManager
from automation_service.services.club_virtual import ClubVirtualService
from automation_service.services.orchestrator import ExtractOrchestrator

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Dependencies (FastAPI Dependency Injection)
# =============================================================================


def get_browser_manager(request: Request) -> BrowserManager:
    """
    Get the BrowserManager instance from FastAPI app state.

    The BrowserManager is created once at startup and stored in app.state.
    This dependency provides access to it for all endpoints.

    Args:
        request: FastAPI Request object (injected automatically)

    Returns:
        The singleton BrowserManager instance
    """
    browser_manager: BrowserManager = request.app.state.browser_manager
    return browser_manager


def get_club_virtual_service(
    browser_manager: Annotated[BrowserManager, Depends(get_browser_manager)],
) -> ClubVirtualService:
    """
    Get a ClubVirtualService instance.

    Creates a new service instance for each request, injecting the
    shared BrowserManager. The service is stateless; all state is
    in the browser contexts managed by BrowserManager.

    Args:
        browser_manager: Injected by FastAPI from get_browser_manager

    Returns:
        ClubVirtualService ready for automation
    """
    return ClubVirtualService(browser_manager)


def get_extract_orchestrator(
    browser_manager: Annotated[BrowserManager, Depends(get_browser_manager)],
) -> ExtractOrchestrator:
    """
    Get an ExtractOrchestrator instance.

    The orchestrator coordinates login and multiple extractors in a single
    automated flow. It provides the combined extraction endpoint.

    Args:
        browser_manager: Injected by FastAPI from get_browser_manager

    Returns:
        ExtractOrchestrator ready for extraction
    """
    return ExtractOrchestrator(browser_manager)


# =============================================================================
# Health Check
# =============================================================================


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(
    browser_manager: Annotated[BrowserManager, Depends(get_browser_manager)],
) -> HealthResponse:
    """
    Check overall service health status.

    Returns service version, environment, and browser readiness.
    Use this for monitoring and debugging.
    """
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        browser_ready=browser_manager.is_ready,
    )


@router.get("/health/live", tags=["Health"])
async def liveness() -> dict[str, str]:
    """
    Kubernetes liveness probe.

    Always returns 200 if the service is running.
    Used by K8s to determine if the container should be restarted.
    """
    return {"status": "alive"}


@router.get("/health/ready", tags=["Health"])
async def readiness(
    browser_manager: Annotated[BrowserManager, Depends(get_browser_manager)],
) -> dict[str, str | bool]:
    """
    Kubernetes readiness probe.

    Returns 200 only if the browser is initialized and ready.
    Used by K8s to determine if traffic should be routed to this pod.

    Returns:
        503 SERVICE_UNAVAILABLE if browser not ready
        200 OK with status if ready
    """
    if not browser_manager.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Browser not ready",
        )
    return {"status": "ready", "browser": True}


# =============================================================================
# Authentication
# =============================================================================


@router.post("/auth/login/simple", response_model=SimpleLoginResponse, tags=["Authentication"])
async def simple_login(
    request: SimpleLoginRequest,
    club_virtual: Annotated[ClubVirtualService, Depends(get_club_virtual_service)],
) -> SimpleLoginResponse:
    """
    Simple credential validation for Club Virtual IASD.

    Use this endpoint when you just need to verify if credentials are valid,
    without maintaining a session for further operations.

    FLOW:
    1. Opens browser (headless)
    2. Attempts login with provided credentials
    3. Returns success/failure immediately
    4. Closes browser session (no persistence)

    USE CASES:
    - User authentication for your application
    - Credential validation before storing
    - Quick login verification

    Returns:
        - success: true/false
        - message: Human-readable result in Spanish
        - username: The username that was validated
        - user_name: Full name if login succeeded (may be null)

    Note:
        This endpoint does NOT select a club or maintain state.
        For full session management, use POST /auth/login instead.
    """
    try:
        response = await club_virtual.login(
            username=request.username,
            password=request.password,
            club_id=None,
            save_session=False,
        )

        # Close the session immediately after validation
        if response.session_id:
            await club_virtual.browser_manager.close_context(response.session_id)

        # Handle case where user profile extraction failed
        user_name = None
        if response.user:
            user_name = response.user.full_name

        display_name = user_name or request.username

        return SimpleLoginResponse(
            success=True,
            message=f"¡Bienvenido! Login exitoso para {display_name}",
            username=request.username,
            user_name=user_name,
        )

    except LoginError as e:
        logger.warning("Login failed", error=e.message, details=e.details)
        return SimpleLoginResponse(
            success=False,
            message="Credenciales inválidas. Usuario o contraseña incorrectos.",
            username=request.username,
        )

    except AutomationError as e:
        logger.error("Automation error during login", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el sistema: {e.message}",
        ) from e


@router.post("/auth/login", response_model=LoginResponse, tags=["Authentication"])
async def login(
    request: LoginRequest,
    club_virtual: Annotated[ClubVirtualService, Depends(get_club_virtual_service)],
) -> LoginResponse:
    """
    Full login to Club Virtual IASD with club selection and session management.

    Use this endpoint when you need to:
    - Select a specific club (for users with multiple clubs)
    - Maintain a session for subsequent automation tasks
    - Access dashboard features

    CLUB SELECTION OPTIONS:
    ----------------------
    1. By club_id: Direct selection if you know the numeric ID
       {"username": "x", "password": "y", "club_id": 7037}

    2. By club_type + club_name: Search for matching club
       {"username": "x", "password": "y", "club_type": "Aventureros", "club_name": "Peniel"}

    3. No club specified: Auto-selects the first available club
       {"username": "x", "password": "y"}

    CLUB TYPES:
    - "Conquistadores" - Pathfinders (ages 10-15)
    - "Guías Mayores" - Master Guides (adults)
    - "Aventureros" - Adventurers (ages 6-9)

    SESSION MANAGEMENT:
    - save_session=true (default): Keeps session for later use
    - save_session=false: Closes session after login

    Returns:
        - session_id: UUID for subsequent requests (save this!)
        - clubs: List of available clubs with IDs
        - user: User profile information
        - screenshot_path: Debug screenshot location

    Example Usage Flow:
        1. POST /auth/login → get session_id
        2. GET /sessions/{session_id}/specialties → use session
        3. DELETE /sessions/{session_id} → cleanup when done
    """
    try:
        response = await club_virtual.login(
            username=request.username,
            password=request.password,
            club_id=request.club_id,
            club_type=request.club_type.value if request.club_type else None,
            club_name=request.club_name,
            save_session=request.save_session,
        )
        return response

    except LoginError as e:
        logger.warning("Login failed", error=e.message, details=e.details)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": e.message, "details": e.details},
        ) from e

    except AutomationError as e:
        logger.error("Automation error during login", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message,
        ) from e


@router.post("/auth/logout", tags=["Authentication"])
async def logout(
    session_id: str,
    club_virtual: Annotated[ClubVirtualService, Depends(get_club_virtual_service)],
) -> dict[str, str]:
    """
    Logout from Club Virtual and cleanup session.

    Performs a clean logout by clicking "Cerrar Sesión" on the website,
    then closes the browser context and frees resources.

    Args:
        session_id: The session ID from a previous login

    Note:
        Safe to call even if session doesn't exist or is already closed.
    """
    await club_virtual.logout(session_id)
    return {"status": "logged_out", "session_id": session_id}


# =============================================================================
# Combined Extraction (Single API Call)
# =============================================================================


@router.post(
    "/extract",
    response_model=ExtractResponse,
    tags=["Extraction"],
    summary="Extract data in a single call",
)
async def extract_data(
    request: ExtractRequest,
    orchestrator: Annotated[ExtractOrchestrator, Depends(get_extract_orchestrator)],
) -> ExtractResponse:
    """
    Extract multiple data types from Club Virtual in a single API call.

    This is the recommended endpoint for most use cases. It combines:
    1. Login (with optional club selection)
    2. Data extraction (profile, tasks, etc.)
    3. Session cleanup

    All in one request, eliminating the need to manage sessions manually.

    AVAILABLE EXTRACTORS:
    --------------------
    - "profile": User profile information (name, email, birthday, etc.)
    - "tasks": Active classes and task completion progress

    REQUEST EXAMPLES:
    ----------------
    1. Extract all available data (default):
       {"username": "user", "password": "pass"}

    2. Extract only profile:
       {"username": "user", "password": "pass", "include": ["profile"]}

    3. Extract profile and tasks with club selection:
       {
           "username": "user",
           "password": "pass",
           "club_type": "Aventureros",
           "club_name": "Peniel",
           "include": ["profile", "tasks"]
       }

    RESPONSE STRUCTURE:
    ------------------
    {
        "success": true,
        "message": "Club: Peniel (Aventureros) | Extracted: profile, tasks",
        "login": {
            "clubs": [{"id": 123, "name": "Peniel", "club_type": "Aventureros"}],
            "selected_club": {"id": 123, "name": "Peniel", ...}
        },
        "profile": {
            "full_name": "Juan Pérez",
            "email": "juan@email.com",
            "age": 8,
            ...
        },
        "tasks": {
            "active_classes": [
                {"name": "Constructores", "completion_percentage": 75, ...}
            ],
            "overall_completion": 75
        },
        "extracted_at": "2024-01-28T15:30:00",
        "screenshot_path": "/path/to/screenshot.png"
    }

    COMPARISON WITH /auth/login:
    ---------------------------
    | Feature                | /extract          | /auth/login + session  |
    |------------------------|-------------------|------------------------|
    | API calls needed       | 1                 | 2-3+                   |
    | Session management     | Automatic         | Manual                 |
    | Multiple data types    | Yes (include)     | Separate endpoints     |
    | Resource cleanup       | Automatic         | Must call DELETE       |

    Use /auth/login + sessions when you need:
    - Interactive automation (multiple steps)
    - Long-running sessions
    - Step-by-step debugging
    """
    try:
        return await orchestrator.extract(
            username=request.username,
            password=request.password,
            club_type=request.club_type.value if request.club_type else None,
            club_name=request.club_name,
            club_id=request.club_id,
            include=request.include,
        )

    except LoginError as e:
        logger.warning("Extraction login failed", error=e.message, details=e.details)
        return ExtractResponse(
            success=False,
            message=f"Login failed: {e.message}",
            errors=[e.message],
        )

    except AutomationError as e:
        logger.error("Extraction automation error", error=e.message)
        return ExtractResponse(
            success=False,
            message=f"Automation error: {e.message}",
            errors=[e.message],
        )


@router.get("/extract/available", tags=["Extraction"])
async def list_extractors(
    orchestrator: Annotated[ExtractOrchestrator, Depends(get_extract_orchestrator)],
) -> dict[str, list[str]]:
    """
    List all available extractors.

    Use this to discover what data types can be extracted via /extract.

    Returns:
        {"extractors": ["profile", "tasks", ...]}
    """
    return {"extractors": orchestrator.list_extractors()}


# =============================================================================
# Automation Tasks
# =============================================================================


@router.get(
    "/sessions/{session_id}/tasks-and-reports",
    response_model=TasksAndReportsResponse,
    tags=["Automation"],
)
async def get_tasks_and_reports(
    session_id: str,
    club_virtual: Annotated[ClubVirtualService, Depends(get_club_virtual_service)],
) -> TasksAndReportsResponse:
    """
    Get active classes and task progress from "Mis tareas y reportes".

    This endpoint navigates to the user's tasks and reports section
    and extracts information about their active classes and progress.

    FLOW:
    1. Uses existing session from login
    2. Navigates to /miembro/cursos-activos
    3. Extracts active class information

    Prerequisites:
    - Must have a valid session_id from POST /auth/login
    - Session must still be active (not logged out)

    Args:
        session_id: Session ID from login response

    Returns:
        TasksAndReportsResponse with:
        - active_classes: List of classes with progress info
        - total_classes: Number of active classes
        - overall_completion: Average completion percentage

    Example Response:
        {
            "success": true,
            "message": "Se encontraron 1 clases activas (1 lista para investidura)",
            "session_id": "abc-123",
            "active_classes": [
                {
                    "name": "Abejas",
                    "completion_percentage": 100.0,
                    "status": "Autorizado para investir",
                    "is_ready_for_investiture": true,
                    "image_url": "https://..."
                }
            ],
            "total_classes": 1,
            "overall_completion": 100.0
        }
    """
    try:
        return await club_virtual.get_tasks_and_reports(session_id)
    except AutomationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        ) from e


@router.get("/sessions/{session_id}/specialties", tags=["Automation"])
async def get_specialties(
    session_id: str,
    club_virtual: Annotated[ClubVirtualService, Depends(get_club_virtual_service)],
) -> dict:
    """
    Extract specialties/badges from the user's Club Virtual dashboard.

    EXAMPLE ENDPOINT FOR POST-LOGIN AUTOMATION:
    This demonstrates how to build endpoints that use an existing session.

    Prerequisites:
    - Must have a valid session_id from POST /auth/login
    - Session must still be active

    Args:
        session_id: Session ID from login response

    Returns:
        {
            "success": true,
            "specialties": [{"name": "Primeros Auxilios"}, ...]
        }

    Use this as a template for adding new automation endpoints.
    """
    try:
        specialties = await club_virtual.extract_specialties(session_id)
        return {"success": True, "specialties": specialties}

    except AutomationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        ) from e


# =============================================================================
# Session Management
# =============================================================================


@router.get("/sessions/{session_id}", tags=["Sessions"])
async def get_session(
    session_id: str,
    browser_manager: Annotated[BrowserManager, Depends(get_browser_manager)],
) -> dict:
    """
    Check if a session exists and is still active.

    Use this to verify a session is valid before making automation calls.

    Args:
        session_id: Session ID to check

    Returns:
        - session_id: The ID checked
        - active: Always true if found
        - pages: Number of open pages/tabs

    Raises:
        404 NOT_FOUND: If session doesn't exist or has been closed
    """
    context = await browser_manager.get_context(session_id)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return {
        "session_id": session_id,
        "active": True,
        "pages": len(context.pages),
    }


@router.delete("/sessions/{session_id}", tags=["Sessions"])
async def delete_session(
    session_id: str,
    browser_manager: Annotated[BrowserManager, Depends(get_browser_manager)],
) -> dict[str, str]:
    """
    Close and delete a browser session.

    Use this to cleanup sessions when done with automation.
    Unlike POST /auth/logout, this just closes the browser context
    without performing a logout on the website.

    Args:
        session_id: Session ID to delete

    Returns:
        - status: "deleted"
        - session_id: The ID that was deleted

    Note:
        Safe to call even if session doesn't exist.
    """
    await browser_manager.close_context(session_id)
    return {"status": "deleted", "session_id": session_id}
