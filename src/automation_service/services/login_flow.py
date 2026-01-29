"""
Login flow for Club Virtual IASD.

This module provides the reusable login functionality that handles:
1. Navigating to the login page
2. Filling and submitting credentials
3. Handling club selection (if user belongs to multiple clubs)
4. Returning the page ready for further automation

The LoginFlow is designed to be used by the orchestrator and can be
composed with various extractors to create complete automation flows.

LOGIN FLOW DIAGRAM:
------------------
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │ Login Page   │ ──► │ Club Select  │ ──► │  Dashboard   │
    │              │     │ (if multiple)│     │              │
    └──────────────┘     └──────────────┘     └──────────────┘
          │                     │                    │
          │ Fill credentials    │ Select club       │ Ready for
          │ Click submit        │ Click "Entrar"    │ extraction
          ▼                     ▼                    ▼
"""

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeout

from automation_service.core.config import settings
from automation_service.core.exceptions import LoginError, NavigationError
from automation_service.models.schemas import ClubInfo

if TYPE_CHECKING:
    from automation_service.services.browser import BrowserManager

logger = structlog.get_logger()


@dataclass
class LoginResult:
    """Result of a login operation."""

    success: bool
    session_id: str
    page: Page
    clubs: list[ClubInfo]
    selected_club: ClubInfo | None
    error: str | None = None


class LoginFlow:
    """
    Handles the login flow for Club Virtual IASD.

    This class encapsulates all login-related logic and provides
    a clean interface for the orchestrator to use.

    Usage:
        flow = LoginFlow(browser_manager)
        result = await flow.execute(
            username="user",
            password="pass",
            club_type="Aventureros",
            club_name="Peniel"
        )
        if result.success:
            # Use result.page for further automation
            pass
    """

    def __init__(self, browser_manager: "BrowserManager") -> None:
        """Initialize the login flow."""
        self.browser_manager = browser_manager
        self.base_url = settings.CLUB_VIRTUAL_BASE_URL

    async def execute(
        self,
        username: str,
        password: str,
        club_id: int | None = None,
        club_type: str | None = None,
        club_name: str | None = None,
    ) -> LoginResult:
        """
        Execute the login flow.

        Args:
            username: Club Virtual username
            password: Club Virtual password
            club_id: Optional. Direct club ID to select
            club_type: Optional. Club type to search for
            club_name: Optional. Club name to search for

        Returns:
            LoginResult with session_id, page, and club info

        Raises:
            LoginError: Invalid credentials or club not found
            NavigationError: Timeout or navigation failure
        """
        session_id = str(uuid.uuid4())

        try:
            # Create browser context
            context = await self.browser_manager.create_context(session_id)
            page = await context.new_page()

            logger.info("Starting login flow", username=username, session_id=session_id)

            # Navigate to login page
            login_url = f"{self.base_url}{settings.CLUB_VIRTUAL_LOGIN_PATH}"
            await page.goto(login_url, wait_until="networkidle")

            # Fill login form
            await page.fill(
                'input[placeholder*="nombre de usuario"], input[name="username"]',
                username,
            )
            await page.fill(
                'input[placeholder*="contraseña"], input[name="password"], input[type="password"]',
                password,
            )

            # Click login button
            await page.click('button:has-text("Iniciar sesión"), button[type="submit"]')

            # Wait for navigation
            await page.wait_for_load_state("networkidle")

            # Check for login error
            if "login_error" in page.url:
                error_text = await self._get_error_message(page)
                await self.browser_manager.close_context(session_id)
                raise LoginError(
                    f"Login failed: {error_text}",
                    {"username": username, "error": error_text},
                )

            # Handle club selection if needed
            clubs, selected_club = await self._handle_club_selection(
                page, club_id, club_type, club_name
            )

            # Wait for dashboard to fully load
            await page.wait_for_load_state("networkidle")

            logger.info(
                "Login successful",
                username=username,
                session_id=session_id,
                selected_club=selected_club.name if selected_club else None,
            )

            return LoginResult(
                success=True,
                session_id=session_id,
                page=page,
                clubs=clubs,
                selected_club=selected_club,
            )

        except LoginError:
            raise
        except PlaywrightTimeout as e:
            await self.browser_manager.close_context(session_id)
            raise NavigationError(f"Timeout during login: {e}") from e
        except Exception as e:
            await self.browser_manager.close_context(session_id)
            logger.error("Login failed", error=str(e), username=username)
            raise LoginError(f"Login failed: {e}") from e

    async def cleanup(self, session_id: str) -> None:
        """Clean up a login session."""
        await self.browser_manager.close_context(session_id)

    async def _handle_club_selection(
        self,
        page: Page,
        club_id: int | None,
        club_type: str | None,
        club_name: str | None,
    ) -> tuple[list[ClubInfo], ClubInfo | None]:
        """Handle club selection after successful login."""
        clubs: list[ClubInfo] = []
        selected_club: ClubInfo | None = None

        if settings.CLUB_VIRTUAL_SELECT_CLUB_PATH not in page.url:
            return clubs, selected_club

        clubs = await self._extract_clubs(page)

        if club_id:
            selected_club = next((c for c in clubs if c.id == club_id), None)
            if selected_club:
                await self._select_club(page, club_id)
        elif club_type and club_name:
            selected_club = self._find_club_by_type_and_name(clubs, club_type, club_name)
            if selected_club:
                await self._select_club(page, selected_club.id)
                logger.info(
                    "Found and selected club",
                    club_id=selected_club.id,
                    club_name=selected_club.name,
                    club_type=selected_club.club_type,
                )
            else:
                available = [f"{c.name} ({c.club_type})" for c in clubs]
                raise LoginError(
                    f"Club not found: {club_name} ({club_type})",
                    {
                        "requested_type": club_type,
                        "requested_name": club_name,
                        "available_clubs": available,
                    },
                )
        elif clubs:
            selected_club = clubs[0]
            await self._select_club(page, clubs[0].id)

        return clubs, selected_club

    def _find_club_by_type_and_name(
        self,
        clubs: list[ClubInfo],
        club_type: str,
        club_name: str,
    ) -> ClubInfo | None:
        """Find a club by type and name using fuzzy matching."""
        club_name_lower = club_name.lower()
        club_type_lower = club_type.lower()

        for club in clubs:
            if (
                club.club_type
                and club_type_lower in club.club_type.lower()
                and club_name_lower in club.name.lower()
            ):
                return club

        # Try a more lenient search
        for club in clubs:
            full_text = club.full_text or f"{club.name} {club.club_type or ''}"
            if club_type_lower in full_text.lower() and club_name_lower in full_text.lower():
                return club

        return None

    async def _get_error_message(self, page: Page) -> str:
        """Extract error message from the login page."""
        try:
            error_element = await page.query_selector(".alert-danger, .error-message, .alert")
            if error_element:
                return await error_element.text_content() or "Unknown error"
        except Exception:
            pass
        return "Invalid credentials"

    async def _extract_clubs(self, page: Page) -> list[ClubInfo]:
        """Extract available clubs from the selection page."""
        clubs: list[ClubInfo] = []
        try:
            await page.wait_for_selector("input[type='radio'], .club-option", timeout=5000)
            options = await page.query_selector_all("input[type='radio']")

            for option in options:
                club_id_str = await option.get_attribute("value")
                if club_id_str:
                    label = await page.query_selector(
                        f"label[for='{await option.get_attribute('id')}']"
                    )
                    if not label:
                        parent = await option.evaluate_handle("el => el.parentElement")
                        label_text = await parent.evaluate("el => el.textContent")
                    else:
                        label_text = await label.text_content()

                    if label_text:
                        full_text = label_text.strip()
                        name, club_type, role = self._parse_club_text(full_text)

                        clubs.append(
                            ClubInfo(
                                id=int(club_id_str),
                                name=name,
                                club_type=club_type,
                                role=role,
                                full_text=full_text,
                            )
                        )

            logger.debug(
                "Extracted clubs",
                count=len(clubs),
                clubs=[f"{c.name} ({c.club_type})" for c in clubs],
            )

        except PlaywrightTimeout:
            logger.debug("No club selection found")
        except Exception as e:
            logger.warning("Error extracting clubs", error=str(e))

        return clubs

    def _parse_club_text(self, full_text: str) -> tuple[str, str | None, str]:
        """Parse club info from label text."""
        name = full_text
        club_type: str | None = None
        role = "Miembro"

        if " como " in full_text:
            parts = full_text.rsplit(" como ", 1)
            role = parts[1].strip() if len(parts) > 1 else "Miembro"
            text_without_role = parts[0].strip()
        else:
            text_without_role = full_text

        if ", Club de " in text_without_role:
            parts = text_without_role.split(", Club de ", 1)
            name_part = parts[0].strip()
            kind_part = parts[1].strip() if len(parts) > 1 else ""
            name = name_part[5:].strip() if name_part.lower().startswith("club ") else name_part
            club_type = self._detect_club_type(kind_part)

        elif "Club de " in text_without_role:
            parts = text_without_role.split(" Club de ", 1)
            name = parts[0].replace("Club ", "").strip()
            kind_part = parts[1].strip() if len(parts) > 1 else ""
            club_type = self._detect_club_type(kind_part)

        else:
            club_type = self._detect_club_type(text_without_role)
            name = text_without_role.replace("Club ", "").strip()

        return name, club_type, role

    def _detect_club_type(self, text: str) -> str | None:
        """Detect standardized club type from text."""
        text_lower = text.lower()

        if "aventurero" in text_lower:
            return "Aventureros"
        elif "conquistador" in text_lower:
            return "Conquistadores"
        elif "guia" in text_lower or "guías" in text_lower or "mayor" in text_lower:
            return "Guías Mayores"

        return None

    async def _select_club(self, page: Page, club_id: int) -> None:
        """Select a specific club on the selection page."""
        try:
            await page.click(f"input[value='{club_id}']")
            await page.click('a:has-text("Entrar"), button:has-text("Entrar")')
            await page.wait_for_load_state("networkidle")
            logger.debug("Selected club", club_id=club_id)
        except Exception as e:
            logger.warning("Error selecting club", club_id=club_id, error=str(e))
