"""API routes for the automation service."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from automation_service.core.config import settings
from automation_service.core.exceptions import AutomationError, LoginError
from automation_service.models.schemas import (
    HealthResponse,
    LoginRequest,
    LoginResponse,
)
from automation_service.services.browser import BrowserManager
from automation_service.services.club_virtual import ClubVirtualService

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Dependencies
# =============================================================================


def get_browser_manager(request: Request) -> BrowserManager:
    """Get browser manager from app state."""
    return request.app.state.browser_manager


def get_club_virtual_service(
    browser_manager: Annotated[BrowserManager, Depends(get_browser_manager)],
) -> ClubVirtualService:
    """Get Club Virtual service."""
    return ClubVirtualService(browser_manager)


# =============================================================================
# Health Check
# =============================================================================


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(
    browser_manager: Annotated[BrowserManager, Depends(get_browser_manager)],
) -> HealthResponse:
    """Check service health."""
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        browser_ready=browser_manager.is_ready,
    )


@router.get("/health/live", tags=["Health"])
async def liveness() -> dict[str, str]:
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@router.get("/health/ready", tags=["Health"])
async def readiness(
    browser_manager: Annotated[BrowserManager, Depends(get_browser_manager)],
) -> dict[str, str | bool]:
    """Kubernetes readiness probe."""
    if not browser_manager.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Browser not ready",
        )
    return {"status": "ready", "browser": True}


# =============================================================================
# Authentication
# =============================================================================


@router.post("/auth/login", response_model=LoginResponse, tags=["Authentication"])
async def login(
    request: LoginRequest,
    club_virtual: Annotated[ClubVirtualService, Depends(get_club_virtual_service)],
) -> LoginResponse:
    """
    Login to Club Virtual IASD.

    Returns session ID that can be used for subsequent requests.
    """
    try:
        response = await club_virtual.login(
            username=request.username,
            password=request.password,
            club_id=request.club_id,
            save_session=request.save_session,
        )
        return response

    except LoginError as e:
        logger.warning("Login failed", error=e.message, details=e.details)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
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
    """Logout and close session."""
    await club_virtual.logout(session_id)
    return {"status": "logged_out", "session_id": session_id}


# =============================================================================
# Automation Tasks
# =============================================================================


@router.get("/sessions/{session_id}/specialties", tags=["Automation"])
async def get_specialties(
    session_id: str,
    club_virtual: Annotated[ClubVirtualService, Depends(get_club_virtual_service)],
) -> dict:
    """Extract specialties from an active session."""
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
    """Check if a session exists and is active."""
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
    """Close and delete a session."""
    await browser_manager.close_context(session_id)
    return {"status": "deleted", "session_id": session_id}
