"""
Browser Management Service using Playwright.

This module provides a centralized browser management layer for the automation service.
It handles Playwright lifecycle, browser contexts (sessions), and resource cleanup.

ARCHITECTURE:
------------
    ┌─────────────────────────────────────────────────────────────────┐
    │                      BrowserManager                             │
    │                                                                 │
    │   ┌─────────────┐    ┌──────────────────────────────────────┐  │
    │   │  Playwright │───►│           Chromium Browser           │  │
    │   │  (Engine)   │    │                                      │  │
    │   └─────────────┘    │  ┌────────────┐  ┌────────────┐     │  │
    │                      │  │ Context A  │  │ Context B  │ ... │  │
    │                      │  │ (Session1) │  │ (Session2) │     │  │
    │                      │  │   ┌─────┐  │  │   ┌─────┐  │     │  │
    │                      │  │   │Page │  │  │   │Page │  │     │  │
    │                      │  │   └─────┘  │  │   └─────┘  │     │  │
    │                      │  └────────────┘  └────────────┘     │  │
    │                      └──────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────┘

KEY CONCEPTS:
------------
- Playwright: The automation engine (must be started/stopped with the app)
- Browser: Single Chromium instance (shared across all sessions)
- Context: Isolated browser session (cookies, storage, etc.)
- Page: A browser tab within a context

Each user session gets its own Context, enabling:
- Parallel sessions for different users
- Session isolation (no cookie/storage leakage)
- Independent authentication states

LIFECYCLE:
---------
1. App startup: initialize() - starts Playwright and browser
2. Per request: create_context() - creates isolated session
3. Per request: Various page operations
4. Cleanup: close_context() - closes session
5. App shutdown: close() - stops browser and Playwright

Usage Example:
-------------
    manager = BrowserManager()
    await manager.initialize()  # Call once at startup

    # Create a session
    context = await manager.create_context("session-123")
    page = await context.new_page()
    await page.goto("https://example.com")

    # Save session for later
    await manager.save_session("session-123")

    # Cleanup
    await manager.close_context("session-123")
    await manager.close()  # Call once at shutdown
"""

from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from automation_service.core.config import settings
from automation_service.core.exceptions import BrowserError

if TYPE_CHECKING:
    from playwright.async_api import Playwright

logger = structlog.get_logger()


class BrowserManager:
    """
    Manages browser instances and contexts for automation.

    This class is responsible for:
    - Starting and stopping the Playwright engine
    - Managing a single browser instance
    - Creating and managing browser contexts (sessions)
    - Session persistence and restoration

    Attributes:
        _playwright: The Playwright engine instance
        _browser: The Chromium browser instance
        _contexts: Dict mapping session_id to BrowserContext

    Thread Safety:
        This class is designed for async usage with a single event loop.
        All methods are async and should be awaited.
    """

    def __init__(self) -> None:
        """Initialize the browser manager (does not start browser yet)."""
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._contexts: dict[str, BrowserContext] = {}

    async def initialize(self) -> None:
        """
        Initialize Playwright and launch the Chromium browser.

        Must be called once at application startup before any automation.
        The FastAPI lifespan handler calls this automatically.

        Browser Configuration (from settings):
        - BROWSER_HEADLESS: True for production, False for debugging
        - BROWSER_SLOW_MO: Milliseconds to slow down operations (debugging)

        Raises:
            BrowserError: If Playwright or browser fails to start

        Note:
            In Docker/headless environments, ensure you're using the
            Playwright Docker image or have installed browser dependencies.
        """
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=settings.BROWSER_HEADLESS,
                slow_mo=settings.BROWSER_SLOW_MO,
            )
            logger.info(
                "Browser initialized",
                headless=settings.BROWSER_HEADLESS,
                browser_version=self._browser.version,
            )
        except Exception as e:
            logger.error("Failed to initialize browser", error=str(e))
            raise BrowserError(f"Failed to initialize browser: {e}") from e

    async def close(self) -> None:
        """
        Gracefully shutdown the browser and Playwright.

        Call this once at application shutdown. The FastAPI lifespan
        handler calls this automatically.

        Cleanup Order:
        1. Close all browser contexts (active sessions)
        2. Close the browser instance
        3. Stop the Playwright engine

        Note:
            Safe to call multiple times. Logs warnings for cleanup errors
            but doesn't raise exceptions.
        """
        # Close all contexts
        for session_id, context in list(self._contexts.items()):
            try:
                await context.close()
                logger.debug("Closed context", session_id=session_id)
            except Exception as e:
                logger.warning("Error closing context", session_id=session_id, error=str(e))

        self._contexts.clear()

        # Close browser
        if self._browser:
            await self._browser.close()
            self._browser = None

        # Stop Playwright
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        logger.info("Browser manager closed")

    @property
    def is_ready(self) -> bool:
        """
        Check if browser is ready for automation.

        Returns True if:
        - Browser instance exists
        - Browser is connected (not crashed or closed)

        Used by health check endpoints to verify service readiness.
        """
        return self._browser is not None and self._browser.is_connected()

    async def create_context(
        self,
        session_id: str,
        storage_state: str | dict | None = None,
    ) -> BrowserContext:
        """
        Create a new isolated browser context for a session.

        A context is like an incognito window - it has its own:
        - Cookies
        - Local storage
        - Session storage
        - Cache

        This enables multiple users to be logged in simultaneously
        without interfering with each other.

        Default Configuration:
        - Viewport: 1280x720
        - Locale: es-MX (Spanish Mexico)
        - Timezone: America/Mexico_City
        - Timeout: From BROWSER_TIMEOUT setting

        Args:
            session_id: Unique identifier for this session
            storage_state: Optional. Path to JSON file or dict with
                          saved session state (cookies, localStorage).
                          Used to restore a previous session.

        Returns:
            BrowserContext ready for page creation

        Raises:
            BrowserError: If browser not initialized

        Note:
            If a context with this session_id exists, it will be
            closed and replaced with a new one.
        """
        if not self._browser:
            raise BrowserError("Browser not initialized")

        # Close existing context if any
        if session_id in self._contexts:
            await self._contexts[session_id].close()

        context_options = {
            "viewport": {"width": 1280, "height": 720},
            "locale": "es-MX",
            "timezone_id": "America/Mexico_City",
        }

        # Load storage state if provided
        if storage_state and (
            (isinstance(storage_state, str) and Path(storage_state).exists())
            or isinstance(storage_state, dict)
        ):
            context_options["storage_state"] = storage_state

        context = await self._browser.new_context(**context_options)
        context.set_default_timeout(settings.BROWSER_TIMEOUT)

        self._contexts[session_id] = context
        logger.debug("Created browser context", session_id=session_id)

        return context

    async def get_context(self, session_id: str) -> BrowserContext | None:
        """
        Get an existing browser context by session ID.

        Use this to retrieve a context from a previous login() call
        for subsequent automation operations.

        Args:
            session_id: The session ID from login response

        Returns:
            BrowserContext if found, None otherwise
        """
        return self._contexts.get(session_id)

    async def close_context(self, session_id: str) -> None:
        """
        Close and cleanup a specific browser context.

        Always call this when done with a session to free resources.
        Safe to call even if the session doesn't exist.

        Args:
            session_id: The session ID to close
        """
        if session_id in self._contexts:
            await self._contexts[session_id].close()
            del self._contexts[session_id]
            logger.debug("Closed browser context", session_id=session_id)

    async def save_session(self, session_id: str, path: str | None = None) -> str:
        """
        Save the browser context state (cookies, localStorage) to a file.

        This allows restoring a session later without re-authenticating.
        Useful for long-running tasks or scheduled automation.

        Storage State Includes:
        - Cookies (authentication tokens, session IDs)
        - Local storage
        - Origins data

        File Location:
        - Default: {SESSION_STORAGE_PATH}/{session_id}.json
        - Custom: Specify with path argument

        Args:
            session_id: The session to save
            path: Optional custom path for the state file

        Returns:
            Full path to the saved state file

        Raises:
            BrowserError: If session/context not found

        Usage:
            # Save session
            path = await manager.save_session("session-123")

            # Later, restore session
            context = await manager.create_context("new-session", storage_state=path)
        """
        context = self._contexts.get(session_id)
        if not context:
            raise BrowserError(f"Context not found: {session_id}")

        # Create sessions directory
        sessions_dir = Path(settings.SESSION_STORAGE_PATH)
        sessions_dir.mkdir(parents=True, exist_ok=True)

        # Save storage state
        storage_path = path or str(sessions_dir / f"{session_id}.json")
        await context.storage_state(path=storage_path)

        logger.info("Session saved", session_id=session_id, path=storage_path)
        return storage_path

    async def new_page(self, session_id: str) -> Page:
        """
        Create a new page (tab) within an existing context.

        Each page is like a browser tab. Multiple pages can exist
        within a single context, sharing cookies and storage.

        Args:
            session_id: The session to create a page in

        Returns:
            A new Page ready for navigation

        Raises:
            BrowserError: If session/context not found

        Note:
            For most automation, you'll use the context directly:
            context = await manager.create_context(...)
            page = await context.new_page()
        """
        context = self._contexts.get(session_id)
        if not context:
            raise BrowserError(f"Context not found: {session_id}")

        return await context.new_page()
