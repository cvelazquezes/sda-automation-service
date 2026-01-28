"""Club Virtual automation service."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from automation_service.core.config import settings
from automation_service.core.exceptions import (
    ElementNotFoundError,
    LoginError,
    NavigationError,
)
from automation_service.models.schemas import ClubInfo, LoginResponse, UserProfile

if TYPE_CHECKING:
    from automation_service.services.browser import BrowserManager

logger = structlog.get_logger()


class ClubVirtualService:
    """Service for automating Club Virtual IASD website."""

    def __init__(self, browser_manager: "BrowserManager") -> None:
        self.browser_manager = browser_manager
        self.base_url = settings.CLUB_VIRTUAL_BASE_URL

    async def login(
        self,
        username: str,
        password: str,
        club_id: int | None = None,
        save_session: bool = True,
    ) -> LoginResponse:
        """
        Perform login to Club Virtual.

        Args:
            username: User's username
            password: User's password
            club_id: Optional club ID to select after login
            save_session: Whether to save the session for reuse

        Returns:
            LoginResponse with session info and user profile
        """
        session_id = str(uuid.uuid4())
        screenshot_path: str | None = None

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
                raise LoginError(
                    f"Login failed: {error_text}",
                    {"username": username, "error": error_text},
                )

            # Handle club selection if needed
            clubs: list[ClubInfo] = []
            if settings.CLUB_VIRTUAL_SELECT_CLUB_PATH in page.url:
                clubs = await self._extract_clubs(page)

                if club_id:
                    await self._select_club(page, club_id)
                elif clubs:
                    # Select first club by default
                    await self._select_club(page, clubs[0].id)

            # Wait for dashboard
            await page.wait_for_load_state("networkidle")

            # Extract user profile
            user = await self._extract_user_profile(page)

            # Take screenshot
            if settings.SCREENSHOTS_ENABLED:
                screenshot_path = await self._take_screenshot(page, f"login_{session_id}")

            # Save session
            if save_session:
                await self.browser_manager.save_session(session_id)

            logger.info(
                "Login successful",
                username=username,
                session_id=session_id,
                user_name=user.full_name if user else None,
            )

            return LoginResponse(
                success=True,
                message="Login successful",
                session_id=session_id,
                user=user,
                clubs=clubs,
                screenshot_path=screenshot_path,
            )

        except LoginError:
            await self.browser_manager.close_context(session_id)
            raise
        except PlaywrightTimeout as e:
            await self.browser_manager.close_context(session_id)
            raise NavigationError(f"Timeout during login: {e}") from e
        except Exception as e:
            await self.browser_manager.close_context(session_id)
            logger.error("Login failed", error=str(e), username=username)
            raise LoginError(f"Login failed: {e}") from e

    async def _get_error_message(self, page: Page) -> str:
        """Extract error message from login page."""
        try:
            error_element = await page.query_selector(".alert-danger, .error-message, .alert")
            if error_element:
                return await error_element.text_content() or "Unknown error"
        except Exception:
            pass
        return "Invalid credentials"

    async def _extract_clubs(self, page: Page) -> list[ClubInfo]:
        """Extract available clubs from selection page."""
        clubs: list[ClubInfo] = []
        try:
            # Wait for club list
            await page.wait_for_selector("input[type='radio'], .club-option", timeout=5000)

            # Get all club options
            options = await page.query_selector_all("input[type='radio']")

            for option in options:
                club_id_str = await option.get_attribute("value")
                if club_id_str:
                    # Get the label text
                    label = await page.query_selector(f"label[for='{await option.get_attribute('id')}']")
                    if not label:
                        # Try sibling text
                        parent = await option.evaluate_handle("el => el.parentElement")
                        label_text = await parent.evaluate("el => el.textContent")
                    else:
                        label_text = await label.text_content()

                    if label_text:
                        # Parse club name and role
                        parts = label_text.strip().split(" como ")
                        name = parts[0].strip() if parts else label_text.strip()
                        role = parts[1].strip() if len(parts) > 1 else "Miembro"

                        clubs.append(
                            ClubInfo(
                                id=int(club_id_str),
                                name=name,
                                role=role,
                            )
                        )

            logger.debug("Extracted clubs", count=len(clubs))

        except PlaywrightTimeout:
            logger.debug("No club selection found")
        except Exception as e:
            logger.warning("Error extracting clubs", error=str(e))

        return clubs

    async def _select_club(self, page: Page, club_id: int) -> None:
        """Select a club from the selection page."""
        try:
            # Click the radio button for the club
            await page.click(f"input[value='{club_id}']")

            # Click enter button
            await page.click('a:has-text("Entrar"), button:has-text("Entrar")')

            # Wait for navigation
            await page.wait_for_load_state("networkidle")

            logger.debug("Selected club", club_id=club_id)

        except Exception as e:
            logger.warning("Error selecting club", club_id=club_id, error=str(e))

    async def _extract_user_profile(self, page: Page) -> UserProfile | None:
        """Extract user profile from dashboard."""
        try:
            # Wait for profile section
            await page.wait_for_selector("h2, .user-name, .profile-name", timeout=5000)

            # Try to get full name
            full_name = None
            name_selectors = ["h2.user-name", ".profile-name", "h2"]
            for selector in name_selectors:
                element = await page.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text and len(text.strip()) > 0:
                        full_name = text.strip()
                        break

            # Get username from page context
            username_element = await page.query_selector(
                '[class*="username"], :text("Iniciaste sesión como")'
            )
            username = ""
            if username_element:
                text = await username_element.text_content()
                if text and "Iniciaste sesión como" in text:
                    username = text.replace("Iniciaste sesión como", "").strip()

            return UserProfile(
                username=username or "unknown",
                full_name=full_name,
            )

        except Exception as e:
            logger.warning("Error extracting user profile", error=str(e))
            return None

    async def _take_screenshot(self, page: Page, name: str) -> str:
        """Take a screenshot and save it."""
        screenshots_dir = Path(settings.SCREENSHOTS_PATH)
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = screenshots_dir / filename

        await page.screenshot(path=str(filepath), full_page=False)

        logger.debug("Screenshot saved", path=str(filepath))
        return str(filepath)

    async def extract_specialties(self, session_id: str) -> list[dict]:
        """Extract specialties from the dashboard."""
        context = await self.browser_manager.get_context(session_id)
        if not context:
            raise ElementNotFoundError("Session not found", {"session_id": session_id})

        page = context.pages[0] if context.pages else await context.new_page()

        try:
            # Navigate to specialties if not already there
            if "especialidades" not in page.url.lower():
                await page.click('a:has-text("Especialidades")')
                await page.wait_for_load_state("networkidle")

            # Extract specialties
            specialties = []
            items = await page.query_selector_all(".specialty-item, .especialidad")

            for item in items:
                name = await item.query_selector(".name, h3, h4")
                name_text = await name.text_content() if name else "Unknown"

                specialties.append({
                    "name": name_text.strip() if name_text else "Unknown",
                })

            return specialties

        except Exception as e:
            logger.error("Error extracting specialties", error=str(e))
            raise

    async def logout(self, session_id: str) -> None:
        """Logout from current session."""
        context = await self.browser_manager.get_context(session_id)
        if context:
            try:
                page = context.pages[0] if context.pages else None
                if page:
                    await page.click('a:has-text("Cerrar Sesión")')
                    await page.wait_for_load_state("networkidle")
            except Exception as e:
                logger.warning("Error during logout", error=str(e))
            finally:
                await self.browser_manager.close_context(session_id)

        logger.info("Logged out", session_id=session_id)
