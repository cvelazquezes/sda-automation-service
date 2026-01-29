"""
Club Virtual IASD Automation Service.

This module provides automation capabilities for interacting with the Club Virtual IASD
website (https://clubvirtual-asd.org.mx). It handles authentication, club selection,
and provides the foundation for additional automation flows.

ARCHITECTURE:
------------
The ClubVirtualService depends on BrowserManager for browser lifecycle management.
Each user session gets its own browser context, enabling parallel operations.

    ┌─────────────────────┐
    │   API Endpoint      │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │ ClubVirtualService  │  ◄── This module
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │   BrowserManager    │  ◄── Manages Playwright browser
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │   Club Virtual      │  ◄── External website
    │     (Website)       │
    └─────────────────────┘

ADDING NEW FLOWS:
----------------
To add a new automation flow after login:

1. Create a new async method in this class:

    async def my_new_flow(self, session_id: str, **params) -> MyResultType:
        '''Description of what this flow does.'''
        # Get the existing browser context
        context = await self.browser_manager.get_context(session_id)
        if not context:
            raise ElementNotFoundError("Session not found", {"session_id": session_id})

        # Get the page (or create new one if needed)
        page = context.pages[0] if context.pages else await context.new_page()

        # Navigate to the desired section
        await page.goto(f"{self.base_url}/path/to/section")
        await page.wait_for_load_state("networkidle")

        # Perform your automation steps
        # ...

        return result

2. Add an API endpoint in routes.py to expose your new flow.

SELECTORS REFERENCE:
-------------------
The website uses the following key selectors (may change over time):

- Login form:
  - Username: 'input[placeholder*="nombre de usuario"], input[name="username"]'
  - Password: 'input[type="password"]'
  - Submit: 'button:has-text("Iniciar sesión")'

- Club selection page:
  - Club options: 'input[type="radio"]'
  - Enter button: 'a:has-text("Entrar")'

- Navigation menu: Look for <a> tags with specific text

Example Usage:
-------------
    service = ClubVirtualService(browser_manager)

    # Simple login
    response = await service.login(username="user", password="pass")

    # Login with specific club
    response = await service.login(
        username="user",
        password="pass",
        club_type="Aventureros",
        club_name="Peniel"
    )

    # Use session for additional flows
    specialties = await service.extract_specialties(response.session_id)

    # Logout when done
    await service.logout(response.session_id)
"""

import contextlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeout

from automation_service.core.config import settings
from automation_service.core.exceptions import (
    ElementNotFoundError,
    LoginError,
    NavigationError,
)
from automation_service.models.schemas import (
    ActiveClass,
    ClubInfo,
    LoginResponse,
    TasksAndReportsResponse,
    UserProfile,
)

# Import extractors for modular data extraction
from automation_service.services.extractors import ProfileExtractor, TasksExtractor

if TYPE_CHECKING:
    from automation_service.services.browser import BrowserManager

logger = structlog.get_logger()


class ClubVirtualService:
    """
    Service for automating Club Virtual IASD website.

    This is the main automation service that handles all interactions with
    Club Virtual. It uses Playwright through BrowserManager to control
    a Chromium browser instance.

    Attributes:
        browser_manager: The BrowserManager instance for browser control.
        base_url: Base URL for Club Virtual (from settings).

    Public Methods:
        login() - Authenticate and optionally select a club
        logout() - Close session and cleanup
        extract_specialties() - Get specialties from dashboard (example flow)

    Private Methods (for internal use):
        _handle_club_selection() - Process club selection after login
        _find_club_by_type_and_name() - Search for club in list
        _extract_clubs() - Parse club options from page
        _select_club() - Click to select a specific club
        _parse_club_text() - Parse club info from label text
        _detect_club_type() - Identify club type from text
        _extract_user_profile() - Get user info from dashboard
        _get_error_message() - Extract error text from page
        _take_screenshot() - Save screenshot for debugging
    """

    def __init__(self, browser_manager: "BrowserManager") -> None:
        """
        Initialize the Club Virtual service.

        Args:
            browser_manager: BrowserManager instance for browser control.
                            Must be initialized before use.
        """
        self.browser_manager = browser_manager
        self.base_url = settings.CLUB_VIRTUAL_BASE_URL

    async def login(
        self,
        username: str,
        password: str,
        club_id: int | None = None,
        club_type: str | None = None,
        club_name: str | None = None,
        save_session: bool = True,
    ) -> LoginResponse:
        """
        Perform complete login flow to Club Virtual IASD.

        This is the main entry point for authentication. It handles:
        1. Navigating to the login page
        2. Filling and submitting credentials
        3. Handling club selection (if user belongs to multiple clubs)
        4. Extracting user profile information
        5. Optionally saving the session for reuse

        LOGIN FLOW DIAGRAM:
        ------------------
        ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
        │ Login Page   │ ──► │ Club Select  │ ──► │  Dashboard   │
        │              │     │ (if multiple)│     │              │
        └──────────────┘     └──────────────┘     └──────────────┘
              │                     │                    │
              │ Fill credentials    │ Select club       │ Extract profile
              │ Click submit        │ Click "Entrar"    │ Take screenshot
              ▼                     ▼                    ▼

        Club Selection Options:
        ----------------------
        - club_id: Direct selection by ID (fastest, requires known ID)
        - club_type + club_name: Search by type and name (more flexible)
        - None: Auto-select first available club

        Args:
            username: User's username for Club Virtual
            password: User's password
            club_id: Optional. Direct club ID for selection.
                     Use this if you already know the club ID from a previous call.
            club_type: Optional. Type of club to search for.
                       Values: "Conquistadores", "Guías Mayores", "Aventureros"
            club_name: Optional. Name of club (partial match supported).
                       Example: "Peniel" will match "Club Peniel"
            save_session: If True, saves browser state for session reuse.
                         Set False for one-time validation.

        Returns:
            LoginResponse containing:
            - success: True if login succeeded
            - message: Human-readable result message
            - session_id: UUID for this session (use in subsequent calls)
            - user: UserProfile with username and full_name (may be None)
            - clubs: List of available clubs (empty if only one club)
            - screenshot_path: Path to login screenshot (if enabled)

        Raises:
            LoginError: Invalid credentials or club not found
            NavigationError: Timeout or navigation failure
            BrowserError: Browser initialization failure

        Example:
            # Simple login (auto-select first club)
            response = await service.login("user", "pass")

            # Login with specific club by type and name
            response = await service.login(
                username="user",
                password="pass",
                club_type="Aventureros",
                club_name="Peniel"
            )

            # Validate credentials only (don't keep session)
            response = await service.login("user", "pass", save_session=False)
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
            clubs, selected_club = await self._handle_club_selection(
                page, club_id, club_type, club_name
            )

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

            # Build success message
            message = "Login successful"
            if selected_club:
                message = f"Login exitoso - {selected_club.name} ({selected_club.club_type})"

            logger.info(
                "Login successful",
                username=username,
                session_id=session_id,
                user_name=user.full_name if user else None,
                selected_club=selected_club.name if selected_club else None,
            )

            return LoginResponse(
                success=True,
                message=message,
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

    async def _handle_club_selection(
        self,
        page: Page,
        club_id: int | None,
        club_type: str | None,
        club_name: str | None,
    ) -> tuple[list[ClubInfo], ClubInfo | None]:
        """
        Handle club selection after successful login.

        This method is called after login when the user belongs to multiple clubs.
        The club selection page shows radio buttons for each available club.

        Selection Priority:
        1. club_id (direct selection) - Fastest, use if ID is known
        2. club_type + club_name (search) - More flexible, partial match
        3. First club (default) - Auto-selects first option

        Page Structure Expected:
        -----------------------
        The club selection page (/valida/selecciona-club) contains:
        - Radio buttons with club IDs as values
        - Labels with club info text
        - "Entrar" button to confirm selection

        Args:
            page: Playwright Page object (current browser page)
            club_id: Direct club ID to select (skips search)
            club_type: Club type for search ("Conquistadores", etc.)
            club_name: Club name for search (partial match)

        Returns:
            Tuple containing:
            - List[ClubInfo]: All available clubs (for reference)
            - ClubInfo | None: The selected club, or None if no selection needed

        Raises:
            LoginError: If club_type and club_name specified but not found

        Note:
            If not on club selection page, returns empty list and None.
            This handles users with only one club (no selection needed).
        """
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
        """
        Find a club by type and name using fuzzy matching.

        Search Strategy (in order):
        1. Exact type + name match in structured fields
        2. Full text search in the original label text

        Matching is case-insensitive and supports partial names.

        Args:
            clubs: List of ClubInfo objects to search
            club_type: Type to match ("Conquistadores", "Guías Mayores", "Aventureros")
            club_name: Club name to match (partial match supported)
                      Example: "Pen" will match "Peniel"

        Returns:
            ClubInfo if a matching club is found, None otherwise

        Example:
            # Find "Club Peniel" of type "Aventureros"
            club = self._find_club_by_type_and_name(
                clubs, "Aventureros", "Peniel"
            )
        """
        club_name_lower = club_name.lower()
        club_type_lower = club_type.lower()

        for club in clubs:
            # Check if club type and name match
            if (
                club.club_type
                and club_type_lower in club.club_type.lower()
                and club_name_lower in club.name.lower()
            ):
                return club

        # Try a more lenient search if exact match not found
        for club in clubs:
            full_text = club.full_text or f"{club.name} {club.club_type or ''}"
            if club_type_lower in full_text.lower() and club_name_lower in full_text.lower():
                return club

        return None

    async def _get_error_message(self, page: Page) -> str:
        """
        Extract error message from the login page after failed login.

        Looks for common error message elements in the page.
        Falls back to generic message if no specific error found.

        Selectors checked:
        - .alert-danger (Bootstrap alert)
        - .error-message (Custom error class)
        - .alert (Generic alert)

        Args:
            page: Playwright Page object

        Returns:
            Error message string, or "Invalid credentials" as fallback
        """
        try:
            error_element = await page.query_selector(".alert-danger, .error-message, .alert")
            if error_element:
                return await error_element.text_content() or "Unknown error"
        except Exception:
            pass
        return "Invalid credentials"

    async def _extract_clubs(self, page: Page) -> list[ClubInfo]:
        """
        Extract all available clubs from the club selection page.

        Parses radio button options and their labels to build ClubInfo objects.

        Page Structure Expected:
        -----------------------
        <input type="radio" id="club_123" value="123">
        <label for="club_123">Club Peniel, Club de Aventureros como Miembro</label>

        Each club label follows the format:
        "Club {name}, Club de {type} como {role}"

        Args:
            page: Playwright Page on the club selection URL

        Returns:
            List of ClubInfo objects with:
            - id: Club ID from radio button value
            - name: Club name (e.g., "Peniel")
            - club_type: Type (e.g., "Aventureros")
            - role: User's role (e.g., "Miembro", "Consejero(a)")
            - full_text: Original label text

        Note:
            Returns empty list if no clubs found or on timeout.
            This is expected for users with only one club.
        """
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
                    label = await page.query_selector(
                        f"label[for='{await option.get_attribute('id')}']"
                    )
                    if not label:
                        # Try sibling text
                        parent = await option.evaluate_handle("el => el.parentElement")
                        label_text = await parent.evaluate("el => el.textContent")
                    else:
                        label_text = await label.text_content()

                    if label_text:
                        full_text = label_text.strip()

                        # Parse club info from text format: Club {name}, Club de {kind} como {role}
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
        """
        Parse club information from label text.

        Expected Format:
        "Club {name}, Club de {kind} como {role}"

        Parsing Steps:
        1. Extract role from " como " suffix
        2. Split name and type from ", Club de " separator
        3. Clean up "Club " prefix from name
        4. Detect standardized club type

        Examples:
            Input:  "Club Elphis Kalein, Club de Guias Mayores como Miembro"
            Output: ("Elphis Kalein", "Guías Mayores", "Miembro")

            Input:  "Club Peniel, Club de Aventureros como Consejero(a)"
            Output: ("Peniel", "Aventureros", "Consejero(a)")

        Args:
            full_text: The raw label text from the club option

        Returns:
            Tuple of (name, club_type, role):
            - name: Club name without "Club " prefix
            - club_type: Standardized type or None if not detected
            - role: User's role (defaults to "Miembro")

        Note:
            Handles various text formats gracefully. If parsing fails,
            returns the full text as name with None type and "Miembro" role.
        """
        name = full_text
        club_type: str | None = None
        role = "Miembro"

        # Extract role (after "como ")
        if " como " in full_text:
            parts = full_text.rsplit(" como ", 1)
            role = parts[1].strip() if len(parts) > 1 else "Miembro"
            text_without_role = parts[0].strip()
        else:
            text_without_role = full_text

        # Extract club type and name from text
        if ", Club de " in text_without_role:
            parts = text_without_role.split(", Club de ", 1)
            name_part = parts[0].strip()
            kind_part = parts[1].strip() if len(parts) > 1 else ""

            # Remove "Club " prefix from name if present
            name = name_part[5:].strip() if name_part.lower().startswith("club ") else name_part

            # Detect club type from kind
            club_type = self._detect_club_type(kind_part)

        elif "Club de " in text_without_role:
            # Alternative format without comma
            parts = text_without_role.split(" Club de ", 1)
            name = parts[0].replace("Club ", "").strip()
            kind_part = parts[1].strip() if len(parts) > 1 else ""
            club_type = self._detect_club_type(kind_part)

        else:
            # Fallback: try to detect type from full text
            club_type = self._detect_club_type(text_without_role)
            name = text_without_role.replace("Club ", "").strip()

        return name, club_type, role

    def _detect_club_type(self, text: str) -> str | None:
        """
        Detect standardized club type from text.

        Maps various text patterns to standardized club types:
        - "aventurero*" → "Aventureros"
        - "conquistador*" → "Conquistadores"
        - "guia*", "guías*", "mayor*" → "Guías Mayores"

        Args:
            text: Text to analyze (case-insensitive)

        Returns:
            Standardized club type string, or None if not detected

        Note:
            Uses simple substring matching. Add more patterns here
            if the website introduces new club types.
        """
        text_lower = text.lower()

        if "aventurero" in text_lower:
            return "Aventureros"
        elif "conquistador" in text_lower:
            return "Conquistadores"
        elif "guia" in text_lower or "guías" in text_lower or "mayor" in text_lower:
            return "Guías Mayores"

        return None

    async def _select_club(self, page: Page, club_id: int) -> None:
        """
        Select a specific club on the club selection page.

        Steps:
        1. Click the radio button for the club ID
        2. Click the "Entrar" button to confirm
        3. Wait for navigation to dashboard

        Args:
            page: Playwright Page on club selection URL
            club_id: The club ID to select (from radio button value)

        Note:
            Logs warning but doesn't raise if selection fails.
            The login flow will continue and may fail later.
        """
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
        """
        Extract complete user profile from the profile page.

        This method delegates to ProfileExtractor for the actual extraction.
        See ProfileExtractor for implementation details.

        Args:
            page: Playwright Page (will navigate to profile page)

        Returns:
            UserProfile with all available information, or None if extraction fails

        Note:
            This method navigates away from the current page to /mi-perfil.
            Some fields may be None if the user hasn't filled them in.
        """
        try:
            extractor = ProfileExtractor()
            profile_data = await extractor.extract(page, self.base_url)

            logger.debug("Extracted user profile via ProfileExtractor", profile_data=profile_data)

            return UserProfile(**profile_data)

        except Exception as e:
            logger.warning("Error extracting user profile", error=str(e))
            return None

    async def _parse_profile_page(self, page: Page) -> dict:
        """
        Parse the profile page and extract all user information.

        This method extracts data from the profile page's structured layout
        where each field has a label and value in a list format.

        Args:
            page: Playwright Page on /mi-perfil

        Returns:
            Dictionary with all extracted profile fields
        """
        profile_data: dict = {"username": "unknown"}

        # Get full name from page title or h2 heading
        full_name = await self._get_text_content(page, "h2")
        if full_name:
            profile_data["full_name"] = full_name.strip()

        # Get avatar URL if available
        avatar = await page.query_selector("img.profile-image, img.avatar, .profile-photo img")
        if avatar:
            profile_data["avatar_url"] = await avatar.get_attribute("src")

        # Extract using specific field patterns
        profile_data.update(await self._extract_profile_fields(page))

        return profile_data

    async def _extract_profile_fields(self, page: Page) -> dict:
        """
        Extract all profile fields from the profile page using JavaScript.

        The Club Virtual profile page uses a specific structure where
        labels and values are in adjacent elements (typically table cells
        or list items with label-value pairs).

        Args:
            page: Playwright Page on /mi-perfil

        Returns:
            Dictionary with all extracted profile field values
        """
        # Use JavaScript to extract profile fields with precise targeting
        result = await page.evaluate(
            """() => {
                const fields = {};
                const placeholder = 'Haz click en el icono';
                const ignorePhrases = ['Estos datos', 'Para cambiar', 'Guardar', 'Cancelar'];

                // Define field mappings
                const fieldMappings = {
                    'Número de cuenta': 'account_number',
                    'Usuario': 'username',
                    'Nombre completo': 'full_name',
                    'Género': 'gender',
                    'Cumpleaños': 'birthday',
                    'Correo electrónico': 'email',
                    'Teléfono': 'phone',
                    'Dirección': 'address',
                    'Mi Presentación': 'bio',
                    'Twitter': 'twitter',
                    'Facebook': 'facebook',
                    'Instagram': 'instagram'
                };

                // Helper to check if value should be ignored
                const shouldIgnore = (value) => {
                    if (!value || value.length === 0) return true;
                    if (value.includes(placeholder)) return true;
                    for (const phrase of ignorePhrases) {
                        if (value.includes(phrase)) return true;
                    }
                    // Also ignore if it contains other field labels
                    for (const label of Object.keys(fieldMappings)) {
                        if (value.includes(label)) return true;
                    }
                    return false;
                };

                // Strategy 1: Look for table rows with two cells
                const tableRows = document.querySelectorAll('tr');
                for (const row of tableRows) {
                    const cells = row.querySelectorAll('td, th');
                    if (cells.length >= 2) {
                        const label = cells[0].textContent?.trim();
                        const value = cells[1].textContent?.trim();
                        if (label && fieldMappings[label] && value && !shouldIgnore(value)) {
                            fields[fieldMappings[label]] = value;
                        }
                    }
                }

                // Strategy 2: Look for list items with strong labels
                const listItems = document.querySelectorAll('li');
                for (const li of listItems) {
                    const strong = li.querySelector('strong, b, .font-bold, .font-weight-bold');
                    if (strong) {
                        const label = strong.textContent?.trim();
                        if (label && fieldMappings[label] && !fields[fieldMappings[label]]) {
                            // Get text after the label
                            const fullText = li.textContent || '';
                            const labelIndex = fullText.indexOf(label);
                            if (labelIndex >= 0) {
                                let value = fullText.substring(labelIndex + label.length).trim();
                                value = value.replace(/^[:\\s]+/, '').trim();
                                if (!shouldIgnore(value)) {
                                    fields[fieldMappings[label]] = value;
                                }
                            }
                        }
                    }
                }

                // Strategy 3: Look for definition lists
                const dlItems = document.querySelectorAll('dl');
                for (const dl of dlItems) {
                    const dts = dl.querySelectorAll('dt');
                    const dds = dl.querySelectorAll('dd');
                    for (let i = 0; i < dts.length && i < dds.length; i++) {
                        const label = dts[i].textContent?.trim();
                        const value = dds[i].textContent?.trim();
                        if (label && fieldMappings[label] && value && !shouldIgnore(value)) {
                            fields[fieldMappings[label]] = value;
                        }
                    }
                }

                // Strategy 4: Look for specific text patterns in spans/divs
                const spans = document.querySelectorAll('span, div.col, div.value, p.value');
                for (const span of spans) {
                    const text = span.textContent?.trim();
                    if (text) {
                        // Check if this is a value element (not containing a label)
                        const parent = span.parentElement;
                        if (parent) {
                            const prevSibling = span.previousElementSibling;
                            if (prevSibling) {
                                const label = prevSibling.textContent?.trim();
                                if (label && fieldMappings[label] && !fields[fieldMappings[label]]) {
                                    if (!shouldIgnore(text)) {
                                        fields[fieldMappings[label]] = text;
                                    }
                                }
                            }
                        }
                    }
                }

                return fields;
            }"""
        )

        fields = result if result else {}

        # Post-process birthday to extract age
        if "birthday" in fields and " - " in str(fields.get("birthday", "")):
            birthday_str = str(fields["birthday"])
            parts = birthday_str.split(" - ")
            fields["birthday"] = parts[0].strip()
            if len(parts) > 1:
                age_str = parts[1].replace("años", "").strip()
                with contextlib.suppress(ValueError):
                    fields["age"] = float(age_str)

        logger.debug("Extracted profile fields", fields=fields)
        return dict(fields)

    async def _get_text_content(self, page: Page, selector: str) -> str | None:
        """
        Get text content from the first matching element.

        Args:
            page: Playwright Page
            selector: CSS selector

        Returns:
            Text content or None if not found
        """
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.text_content()
                return str(text) if text else None
        except Exception:
            pass
        return None

    async def _extract_basic_profile(self, page: Page) -> UserProfile | None:
        """
        Fallback method to extract basic profile info from any page.

        Used when full profile extraction fails. Tries to get at least
        the username and display name from the current page.

        Args:
            page: Playwright Page (any page after login)

        Returns:
            UserProfile with basic info, or None if extraction fails
        """
        try:
            # Try to get username from session text
            username = "unknown"
            session_element = await page.query_selector(':text("Iniciaste sesión como")')
            if session_element:
                parent = await session_element.evaluate_handle("el => el.parentElement")
                text = await parent.evaluate("el => el.textContent")
                if text and "Iniciaste sesión como" in text:
                    username = text.split("Iniciaste sesión como")[-1].strip().split()[0]

            # Try to get display name
            full_name = None
            name_element = await page.query_selector("h2")
            if name_element:
                full_name = await name_element.text_content()
                if full_name:
                    full_name = full_name.strip()

            return UserProfile(username=username, full_name=full_name)

        except Exception as e:
            logger.warning("Error in basic profile extraction", error=str(e))
            return None

    async def _take_screenshot(self, page: Page, name: str) -> str:
        """
        Take a screenshot of the current page state.

        Screenshots are useful for debugging and verification.
        They're saved to the configured SCREENSHOTS_PATH directory.

        Filename Format: {name}_{timestamp}.png
        Example: login_abc123_20240128_143022.png

        Args:
            page: Playwright Page to screenshot
            name: Base name for the screenshot file

        Returns:
            Full path to the saved screenshot file

        Note:
            Creates the screenshots directory if it doesn't exist.
            Screenshots are NOT full-page by default (viewport only).
        """
        screenshots_dir = Path(settings.SCREENSHOTS_PATH)
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = screenshots_dir / filename

        await page.screenshot(path=str(filepath), full_page=False)

        logger.debug("Screenshot saved", path=str(filepath))
        return str(filepath)

    async def get_tasks_and_reports(self, session_id: str) -> TasksAndReportsResponse:
        """
        Extract active classes and task progress from "Mis tareas y reportes".

        This method delegates to TasksExtractor for the actual extraction.
        See TasksExtractor for implementation details.

        Args:
            session_id: Session ID from a previous login() call

        Returns:
            TasksAndReportsResponse containing:
            - active_classes: List of ActiveClass objects
            - total_classes: Number of active classes
            - overall_completion: Average completion percentage

        Raises:
            ElementNotFoundError: Session not found or expired
            NavigationError: Failed to navigate to tasks page
        """
        context = await self.browser_manager.get_context(session_id)
        if not context:
            raise ElementNotFoundError("Session not found", {"session_id": session_id})

        page = context.pages[0] if context.pages else await context.new_page()
        screenshot_path: str | None = None

        try:
            logger.info("Extracting tasks and reports", session_id=session_id)

            # Use TasksExtractor for extraction
            extractor = TasksExtractor()
            tasks_data = await extractor.extract(page, self.base_url)

            # Convert to ActiveClass models
            active_classes = [
                ActiveClass(
                    name=item.get("name", "Unknown"),
                    completion_percentage=float(item.get("completion_percentage", 0)),
                    status=item.get("status"),
                    is_ready_for_investiture=item.get("is_ready_for_investiture", False),
                    image_url=item.get("image_url"),
                )
                for item in tasks_data.get("active_classes", [])
            ]

            # Take screenshot
            if settings.SCREENSHOTS_ENABLED:
                screenshot_path = await self._take_screenshot(page, f"tasks_{session_id}")

            # Build message
            message = f"Se encontraron {len(active_classes)} clases activas"
            ready_count = tasks_data.get("ready_for_investiture_count", 0)
            if ready_count > 0:
                message += f" ({ready_count} lista(s) para investidura)"

            logger.info(
                "Tasks and reports extracted",
                session_id=session_id,
                class_count=len(active_classes),
            )

            return TasksAndReportsResponse(
                success=True,
                message=message,
                session_id=session_id,
                active_classes=active_classes,
                total_classes=tasks_data.get("total_classes", len(active_classes)),
                overall_completion=tasks_data.get("overall_completion"),
                screenshot_path=screenshot_path,
            )

        except PlaywrightTimeout as e:
            logger.error("Timeout extracting tasks", error=str(e))
            raise NavigationError(f"Timeout accessing tasks page: {e}") from e
        except Exception as e:
            logger.error("Error extracting tasks", error=str(e))
            return TasksAndReportsResponse(
                success=False,
                message=f"Error al extraer tareas: {e}",
                session_id=session_id,
            )

    async def _extract_active_classes(self, page: Page) -> list[ActiveClass]:
        """
        Extract active class information from the tasks page.

        Parses the course cards on /miembro/cursos-activos to extract
        class names, completion percentages, and status.

        Args:
            page: Playwright Page on the tasks URL

        Returns:
            List of ActiveClass objects
        """
        # Use JavaScript to extract class information
        result = await page.evaluate(
            """() => {
                const classes = [];

                // Look for class headings (h3 elements typically contain class names)
                const headings = document.querySelectorAll('h3');

                for (const heading of headings) {
                    const name = heading.textContent?.trim();

                    // Skip non-class headings
                    if (!name || name.includes('Cambiar') || name.includes('Investidura')) {
                        continue;
                    }

                    // Find the parent container
                    const container = heading.closest('div, section, article');
                    if (!container) continue;

                    const classInfo = {
                        name: name,
                        completion_percentage: 0,
                        status: null,
                        is_ready_for_investiture: false,
                        image_url: null
                    };

                    // Look for completion percentage text
                    const containerText = container.textContent || '';
                    const percentMatch = containerText.match(/(\\d+)\\s*%/);
                    if (percentMatch) {
                        classInfo.completion_percentage = parseInt(percentMatch[1], 10);
                    }

                    // Check for investiture status
                    if (containerText.includes('autorizado') ||
                        containerText.includes('Autorizado') ||
                        containerText.includes('investir')) {
                        classInfo.is_ready_for_investiture = true;
                        classInfo.status = 'Autorizado para investir';
                    } else if (classInfo.completion_percentage >= 100) {
                        classInfo.status = 'Completado';
                    } else if (classInfo.completion_percentage > 0) {
                        classInfo.status = 'En progreso';
                    } else {
                        classInfo.status = 'Sin iniciar';
                    }

                    // Look for image
                    const img = container.querySelector('img');
                    if (img) {
                        classInfo.image_url = img.src;
                    }

                    classes.push(classInfo);
                }

                return classes;
            }"""
        )

        classes = []
        if result:
            for item in result:
                classes.append(
                    ActiveClass(
                        name=item.get("name", "Unknown"),
                        completion_percentage=float(item.get("completion_percentage", 0)),
                        status=item.get("status"),
                        is_ready_for_investiture=item.get("is_ready_for_investiture", False),
                        image_url=item.get("image_url"),
                    )
                )

        logger.debug("Extracted active classes", count=len(classes), classes=classes)
        return classes

    async def extract_specialties(self, session_id: str) -> list[dict]:
        """
        Extract specialties/badges from the user's dashboard.

        EXAMPLE OF A POST-LOGIN FLOW:
        ----------------------------
        This method demonstrates how to add new automation flows that
        operate on an existing session. Use this as a template.

        Prerequisites:
        - User must be logged in (valid session_id from login())
        - Session must still be active (not timed out or logged out)

        Flow:
        1. Get existing browser context using session_id
        2. Navigate to the specialties section if not already there
        3. Parse the specialties list from the page
        4. Return structured data

        Args:
            session_id: Session ID from a previous login() call

        Returns:
            List of specialty dictionaries with 'name' field
            Example: [{"name": "Primeros Auxilios"}, {"name": "Camping"}]

        Raises:
            ElementNotFoundError: Session not found or expired

        Usage:
            response = await service.login("user", "pass")
            specialties = await service.extract_specialties(response.session_id)
        """
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

                specialties.append(
                    {
                        "name": name_text.strip() if name_text else "Unknown",
                    }
                )

            return specialties

        except Exception as e:
            logger.error("Error extracting specialties", error=str(e))
            raise

    async def logout(self, session_id: str) -> None:
        """
        Logout from Club Virtual and cleanup session.

        Performs a clean logout by:
        1. Clicking the "Cerrar Sesión" link (if page available)
        2. Waiting for logout to complete
        3. Closing the browser context
        4. Releasing session resources

        Args:
            session_id: Session ID from a previous login() call

        Note:
            This method is safe to call even if:
            - Session doesn't exist
            - Session already logged out
            - Browser context already closed

            Always call this when done with a session to free resources.
        """
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
