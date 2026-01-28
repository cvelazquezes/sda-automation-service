"""Browser management service using Playwright."""

import asyncio
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
    """Manages browser instances and contexts for automation."""

    def __init__(self) -> None:
        self._playwright: "Playwright | None" = None
        self._browser: Browser | None = None
        self._contexts: dict[str, BrowserContext] = {}

    async def initialize(self) -> None:
        """Initialize Playwright and launch browser."""
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
        """Close all contexts and the browser."""
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
        """Check if browser is ready."""
        return self._browser is not None and self._browser.is_connected()

    async def create_context(
        self,
        session_id: str,
        storage_state: str | dict | None = None,
    ) -> BrowserContext:
        """Create a new browser context."""
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
        if storage_state:
            if isinstance(storage_state, str) and Path(storage_state).exists():
                context_options["storage_state"] = storage_state
            elif isinstance(storage_state, dict):
                context_options["storage_state"] = storage_state

        context = await self._browser.new_context(**context_options)
        context.set_default_timeout(settings.BROWSER_TIMEOUT)

        self._contexts[session_id] = context
        logger.debug("Created browser context", session_id=session_id)

        return context

    async def get_context(self, session_id: str) -> BrowserContext | None:
        """Get an existing browser context."""
        return self._contexts.get(session_id)

    async def close_context(self, session_id: str) -> None:
        """Close a specific browser context."""
        if session_id in self._contexts:
            await self._contexts[session_id].close()
            del self._contexts[session_id]
            logger.debug("Closed browser context", session_id=session_id)

    async def save_session(self, session_id: str, path: str | None = None) -> str:
        """Save browser context storage state."""
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
        """Create a new page in a context."""
        context = self._contexts.get(session_id)
        if not context:
            raise BrowserError(f"Context not found: {session_id}")

        return await context.new_page()
