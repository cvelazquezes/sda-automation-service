"""
Extraction orchestrator for Club Virtual automation.

This module coordinates the extraction of multiple data types in a single
automated session. It handles:
1. Login via LoginFlow
2. Running selected extractors
3. Aggregating results
4. Cleanup

Architecture:
------------
    ┌─────────────────────────────────────────────────────┐
    │              ExtractOrchestrator                     │
    │  ┌─────────────────────────────────────────────────┐│
    │  │                 LoginFlow                        ││
    │  │  - Authenticate user                            ││
    │  │  - Handle club selection                        ││
    │  │  - Return page ready for extraction             ││
    │  └─────────────────────────────────────────────────┘│
    │                        │                            │
    │                        ▼                            │
    │  ┌─────────────────────────────────────────────────┐│
    │  │              Extractors Registry                 ││
    │  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ ││
    │  │  │ Profile  │ │  Tasks   │ │   Specialties    │ ││
    │  │  └──────────┘ └──────────┘ └──────────────────┘ ││
    │  └─────────────────────────────────────────────────┘│
    │                        │                            │
    │                        ▼                            │
    │  ┌─────────────────────────────────────────────────┐│
    │  │           Combined ExtractResponse               ││
    │  └─────────────────────────────────────────────────┘│
    └─────────────────────────────────────────────────────┘

Usage:
------
    orchestrator = ExtractOrchestrator(browser_manager)

    # Extract profile and tasks in one call
    response = await orchestrator.extract(
        username="user",
        password="pass",
        club_type="Aventureros",
        club_name="Peniel",
        include=["profile", "tasks"]
    )

    if response.success:
        print(response.profile)  # User profile data
        print(response.tasks)    # Active classes data
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from playwright.async_api import Page

from automation_service.core.config import settings
from automation_service.models.schemas import ClubInfo, ExtractResponse
from automation_service.services.extractors import ExtractorRegistry
from automation_service.services.login_flow import LoginFlow

if TYPE_CHECKING:
    from automation_service.services.browser import BrowserManager

logger = structlog.get_logger()


class ExtractOrchestrator:
    """
    Orchestrates data extraction from Club Virtual.

    Coordinates login, extraction, and cleanup in a single operation.
    Supports extracting multiple data types in one session.

    Attributes:
        browser_manager: BrowserManager for browser control
        login_flow: LoginFlow for authentication
        base_url: Club Virtual base URL
    """

    def __init__(self, browser_manager: "BrowserManager") -> None:
        """Initialize the orchestrator."""
        self.browser_manager = browser_manager
        self.login_flow = LoginFlow(browser_manager)
        self.base_url = settings.CLUB_VIRTUAL_BASE_URL

    async def extract(
        self,
        username: str,
        password: str,
        club_type: str | None = None,
        club_name: str | None = None,
        club_id: int | None = None,
        include: list[str] | None = None,
    ) -> ExtractResponse:
        """
        Execute a complete extraction flow.

        This method:
        1. Logs in to Club Virtual
        2. Runs each requested extractor
        3. Aggregates all results
        4. Cleans up the browser session

        Args:
            username: Club Virtual username
            password: Club Virtual password
            club_type: Optional club type to select
            club_name: Optional club name to select
            club_id: Optional direct club ID to select
            include: List of extractor names to run (e.g., ["profile", "tasks"])
                    If None or empty, defaults to all extractors

        Returns:
            ExtractResponse with:
            - success: True if extraction succeeded
            - message: Human-readable result
            - login: Club info and selected club
            - profile: Profile data (if requested)
            - tasks: Tasks data (if requested)
            - extracted_at: Timestamp of extraction
            - screenshot_path: Path to screenshot (if enabled)
        """
        session_id: str | None = None
        screenshot_path: str | None = None

        # Default to all extractors if none specified
        if not include:
            include = ExtractorRegistry.list_extractors()

        try:
            # Step 1: Login
            logger.info(
                "Starting extraction",
                username=username,
                include=include,
            )

            login_result = await self.login_flow.execute(
                username=username,
                password=password,
                club_type=club_type,
                club_name=club_name,
                club_id=club_id,
            )

            session_id = login_result.session_id
            page = login_result.page

            # Step 2: Run extractors
            extracted_data: dict[str, Any] = {}
            errors: list[str] = []

            for extractor_name in include:
                try:
                    extractor = ExtractorRegistry.get(extractor_name)
                    data = await extractor.extract(page, self.base_url)
                    extracted_data[extractor_name] = data
                    logger.debug(
                        "Extractor completed",
                        extractor=extractor_name,
                        data_keys=list(data.keys()) if isinstance(data, dict) else None,
                    )
                except ValueError as e:
                    # Unknown extractor
                    errors.append(str(e))
                    logger.warning("Unknown extractor requested", name=extractor_name)
                except Exception as e:
                    errors.append(f"{extractor_name}: {e}")
                    logger.warning(
                        "Extractor failed",
                        extractor=extractor_name,
                        error=str(e),
                    )

            # Step 3: Take screenshot
            if settings.SCREENSHOTS_ENABLED:
                screenshot_path = await self._take_screenshot(page, f"extract_{session_id}")

            # Step 4: Build response
            message = self._build_message(login_result.selected_club, extracted_data, errors)

            logger.info(
                "Extraction completed",
                session_id=session_id,
                extracted=list(extracted_data.keys()),
                errors=errors if errors else None,
            )

            return ExtractResponse(
                success=True,
                message=message,
                session_id=session_id,
                login={
                    "clubs": [self._club_to_dict(c) for c in login_result.clubs],
                    "selected_club": (
                        self._club_to_dict(login_result.selected_club)
                        if login_result.selected_club
                        else None
                    ),
                },
                profile=extracted_data.get("profile"),
                tasks=extracted_data.get("tasks"),
                specialties=extracted_data.get("specialties"),
                extracted_at=datetime.now().isoformat(),
                screenshot_path=screenshot_path,
                errors=errors if errors else None,
            )

        except Exception as e:
            logger.error("Extraction failed", error=str(e), username=username)
            return ExtractResponse(
                success=False,
                message=f"Error: {e}",
                session_id=session_id,
                errors=[str(e)],
            )

        finally:
            # Step 5: Cleanup
            if session_id:
                await self.browser_manager.close_context(session_id)

    def _club_to_dict(self, club: ClubInfo) -> dict[str, Any]:
        """Convert ClubInfo to dictionary for response."""
        return {
            "id": club.id,
            "name": club.name,
            "club_type": club.club_type,
            "role": club.role,
        }

    def _build_message(
        self,
        selected_club: ClubInfo | None,
        extracted_data: dict[str, Any],
        errors: list[str],
    ) -> str:
        """Build a human-readable result message."""
        parts = []

        if selected_club:
            parts.append(f"Club: {selected_club.name} ({selected_club.club_type})")

        if extracted_data:
            parts.append(f"Extracted: {', '.join(extracted_data.keys())}")

        if errors:
            parts.append(f"Errors: {len(errors)}")

        return " | ".join(parts) if parts else "Extraction completed"

    async def _take_screenshot(self, page: Page, name: str) -> str:
        """Take a screenshot of the current page."""
        screenshots_dir = Path(settings.SCREENSHOTS_PATH)
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = screenshots_dir / filename

        await page.screenshot(path=str(filepath), full_page=False)

        logger.debug("Screenshot saved", path=str(filepath))
        return str(filepath)

    def list_extractors(self) -> list[str]:
        """List all available extractor names."""
        return ExtractorRegistry.list_extractors()
