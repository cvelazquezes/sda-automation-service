# Automation Service - AI Agent Guide

## Overview

The **Automation Service** is a browser automation and web scraping service built with **Python 3.12+** and **FastAPI**. It uses **Playwright** for headless browser automation to extract data from external systems like Club Virtual IASD. This service is **stateless** with no database, relying entirely on browser sessions for state management.

**Core Purpose**: Automate login flows, navigate complex web applications, and extract structured data through browser automation with retry logic and resource limits.

## Service Details

| Property | Value |
|----------|-------|
| Language | Python 3.12+ |
| Port | 8089 |
| Framework | FastAPI (async/await) |
| Browser Engine | Playwright (Chromium) |
| Database | None (stateless) |
| HTTP Client | httpx (async) |
| Logging | structlog (structured) |
| Retry Logic | tenacity (exponential backoff) |

## Critical Rules for AI Agents

### ALWAYS Remember

1. **Close browser contexts** - Use try/finally blocks to ensure cleanup
2. **Limit concurrent sessions** - Max 5 browser sessions (Chromium is memory-heavy)
3. **Retry with exponential backoff** - Use tenacity for transient failures
4. **NEVER log credentials** - Mask sensitive data in logs
5. **Async/await enforcement** - ALL Playwright operations must use await
6. **Base extractor pattern** - All extractors inherit from BaseExtractor
7. **Resource management** - Browser contexts are expensive, always clean up
8. **NO database** - Service is stateless, all state in browser sessions

### NEVER Do This

```python
# WRONG - No cleanup, resource leak
async def scrape():
    context = await browser_manager.create_context("session-123")
    page = await context.new_page()
    return await extract_data(page)  # Context leaked!

# WRONG - Missing await
async def extract_data(page: Page):
    page.goto(url)  # Will fail! Must await

# WRONG - Logging credentials
logger.info("Login", username=username, password=password)

# WRONG - Using sleep instead of explicit waits
await asyncio.sleep(5)  # Brittle timing
```

### ALWAYS Do This

```python
# CORRECT - Proper cleanup with try/finally
async def scrape():
    context = None
    try:
        context = await browser_manager.create_context("session-123")
        page = await context.new_page()
        return await extract_data(page)
    finally:
        if context:
            await context.close()

# CORRECT - Awaiting all operations
async def extract_data(page: Page):
    await page.goto(url)
    await page.wait_for_selector("div.content")

# CORRECT - Masked logging
logger.info("Login attempted", username=username[:3]+"***")

# CORRECT - Explicit waits
await page.wait_for_selector("div.loaded", state="visible")
await page.wait_for_load_state("networkidle")
```

## Project Structure

```
automation-service/
├── src/automation_service/
│   ├── __init__.py
│   ├── main.py                           # FastAPI app entry point + lifespan
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py                     # All HTTP endpoints
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                     # Settings (pydantic-settings)
│   │   ├── exceptions.py                 # Custom exception hierarchy
│   │   └── logging.py                    # Structured logging setup
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py                    # Pydantic request/response models
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── browser.py                    # BrowserManager (Playwright lifecycle)
│   │   ├── club_virtual.py               # Club Virtual specific automation
│   │   ├── login_flow.py                 # Login flow handlers
│   │   ├── orchestrator.py               # ExtractOrchestrator (coordinates extractors)
│   │   │
│   │   └── extractors/                   # Extractor plugin architecture
│   │       ├── __init__.py
│   │       ├── base.py                   # BaseExtractor + ExtractorRegistry
│   │       ├── profile.py                # Profile extraction
│   │       └── tasks.py                  # Tasks/classes extraction
│   │
│   └── utils/
│       └── __init__.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                       # Pytest fixtures
│   └── test_*.py                         # Test files
│
├── docs/                                 # Additional documentation
├── screenshots/                          # Debug screenshots (gitignored)
├── sessions/                             # Session storage (gitignored)
│
├── .cursorrules                          # Comprehensive Playwright patterns
├── CLAUDE.md                             # This file
├── pyproject.toml                        # Dependencies + tool config
├── Dockerfile                            # Container build
└── Makefile                              # Development commands
```

## API Endpoints

### Health Checks
```
GET    /health                  # Service health + browser readiness
GET    /health/live             # Kubernetes liveness probe
GET    /health/ready            # Kubernetes readiness probe (checks browser)
```

### Authentication
```
POST   /auth/login/simple       # Quick credential validation (no session)
POST   /auth/login              # Full login with club selection + session
POST   /auth/logout             # Logout + cleanup session
```

### Combined Extraction (Recommended)
```
POST   /extract                 # Login + extract multiple data types in one call
GET    /extract/available       # List available extractors
```

### Session Management
```
GET    /sessions/{id}           # Check session status
DELETE /sessions/{id}           # Close session + cleanup
```

### Automation Tasks (Post-Login)
```
GET    /sessions/{id}/tasks-and-reports  # Extract active classes + progress
GET    /sessions/{id}/specialties        # Extract specialties/badges
```

## Key Patterns with Code Examples

### 1. Browser Context Management (CRITICAL)

**Pattern**: Each session gets an isolated browser context. ALWAYS close contexts in finally blocks.

```python
from playwright.async_api import BrowserContext, Page
from automation_service.services.browser import BrowserManager

async def automation_flow(browser_manager: BrowserManager, session_id: str):
    """
    Template for any browser automation flow.

    Key Points:
    - Fresh context per session (isolation)
    - Try/finally ensures cleanup
    - Resource limit via BrowserManager semaphore
    """
    context: BrowserContext | None = None
    try:
        # Create isolated context (auto-limited to 5 concurrent)
        context = await browser_manager.create_context(
            session_id=session_id,
            storage_state=None,  # Or path to saved session
        )

        # Set timeouts (from config, default 30s)
        context.set_default_timeout(30000)

        # Create page and navigate
        page: Page = await context.new_page()
        await page.goto("https://example.com", wait_until="networkidle")

        # Perform automation
        await page.wait_for_selector("div.content", state="visible")
        data = await extract_data(page)

        # Optional: Save session for later
        session_path = await browser_manager.save_session(session_id)

        return data

    finally:
        # CRITICAL: Always cleanup, even on exception
        if context:
            await context.close()
            # Also remove from registry
            await browser_manager.close_context(session_id)
```

**Configuration Options**:
```python
# Browser context with custom settings
context = await browser.new_context(
    viewport={"width": 1280, "height": 720},
    locale="es-MX",
    timezone_id="America/Mexico_City",
    user_agent="Custom Agent",
    storage_state="./sessions/session-123.json",  # Restore saved session
)
```

### 2. Retry with Exponential Backoff (tenacity)

**Pattern**: Transient failures (timeouts, network issues) should retry with exponential backoff.

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

@retry(
    stop=stop_after_attempt(3),                      # Max 3 attempts
    wait=wait_exponential(multiplier=1, min=2, max=10),  # 2s, 4s, 8s (capped at 10s)
    retry=retry_if_exception_type((PlaywrightTimeoutError, TimeoutError)),
)
async def extract_with_retry(page: Page) -> dict:
    """
    Retry extraction on timeout errors.

    Retry Strategy:
    - Attempt 1: Immediate
    - Attempt 2: Wait 2s
    - Attempt 3: Wait 4s

    Only retries on timeout errors, not logic errors.
    """
    await page.wait_for_selector("div.data", timeout=5000)
    return await extract_data(page)

# Use it
try:
    data = await extract_with_retry(page)
except PlaywrightTimeoutError:
    # All retries exhausted
    logger.error("Extraction failed after 3 retries")
    raise
```

**When to Retry**:
- Timeout errors (network, slow page loads)
- Transient navigation failures
- Race conditions (element not ready yet)

**When NOT to Retry**:
- Login failures (wrong credentials)
- Element not found (selector issue)
- Logic errors (wrong page structure)

### 3. Base Extractor Pattern + Registry

**Pattern**: All extractors inherit from BaseExtractor and register via decorator for discoverability.

```python
# File: services/extractors/base.py
from abc import ABC, abstractmethod
from typing import Any, ClassVar
from playwright.async_api import Page

class ExtractorRegistry:
    """Registry for dynamic extractor discovery."""
    _extractors: ClassVar[dict[str, type["BaseExtractor"]]] = {}

    @classmethod
    def register(cls, extractor_class: type["BaseExtractor"]):
        """Decorator to register extractors."""
        name = extractor_class.name
        cls._extractors[name] = extractor_class
        return extractor_class

    @classmethod
    def get(cls, name: str) -> "BaseExtractor":
        """Get extractor instance by name."""
        if name not in cls._extractors:
            raise ValueError(f"Unknown extractor: {name}")
        return cls._extractors[name]()

    @classmethod
    def list_extractors(cls) -> list[str]:
        """List all registered extractor names."""
        return list(cls._extractors.keys())

class BaseExtractor(ABC):
    """
    Abstract base class for all data extractors.

    Subclasses must define:
    - name: Unique identifier (e.g., "profile", "tasks")
    - description: Human-readable description
    - extract(): Implementation of extraction logic
    """

    name: str = ""
    description: str = ""
    requires_navigation: bool = True

    @abstractmethod
    async def extract(self, page: Page, base_url: str) -> dict[str, Any]:
        """Extract data from Club Virtual."""
        pass

    async def safe_get_text(self, page: Page, selector: str) -> str | None:
        """Safely extract text, return None if not found."""
        try:
            element = await page.query_selector(selector)
            if element:
                return (await element.text_content() or "").strip()
        except Exception:
            pass
        return None

# File: services/extractors/profile.py
@ExtractorRegistry.register
class ProfileExtractor(BaseExtractor):
    """Extract user profile information."""

    name = "profile"
    description = "Extracts user profile data (name, email, birthday, etc.)"
    requires_navigation = True

    async def extract(self, page: Page, base_url: str) -> dict[str, Any]:
        """Extract profile data from Club Virtual."""
        # Navigate to profile page
        await page.goto(f"{base_url}/mi-perfil", wait_until="networkidle")

        # Wait for profile content
        await page.wait_for_selector("div.profile-container", timeout=10000)

        # Extract fields with retry logic
        full_name = await self.safe_get_text(page, "h1.profile-name")
        email = await self.safe_get_text(page, "input[name='email']")

        return {
            "full_name": full_name,
            "email": email,
            # ... more fields
        }

# Usage in orchestrator or service
extractor = ExtractorRegistry.get("profile")
data = await extractor.extract(page, base_url)
```

**Creating New Extractors**:
1. Create file in `services/extractors/my_extractor.py`
2. Inherit from `BaseExtractor`
3. Use `@ExtractorRegistry.register` decorator
4. Implement `extract()` method
5. Add unit tests in `tests/extractors/test_my_extractor.py`

### 4. Resource Limits (Semaphore)

**Pattern**: Limit concurrent browser sessions to prevent memory exhaustion.

```python
# File: services/browser.py
import asyncio
from playwright.async_api import BrowserContext

class BrowserManager:
    """
    Manages browser lifecycle and enforces resource limits.

    Resource Limits:
    - Max 5 concurrent browser contexts (configurable via settings)
    - Semaphore blocks new contexts when limit reached
    - Automatic cleanup on shutdown
    """

    def __init__(self, max_sessions: int = 5):
        self._contexts: dict[str, BrowserContext] = {}
        self._semaphore = asyncio.Semaphore(max_sessions)  # Limit concurrent sessions

    async def create_context(self, session_id: str) -> BrowserContext:
        """
        Create new browser context with resource limit.

        Blocks if 5 sessions already active, waits for one to close.
        """
        async with self._semaphore:  # Acquire semaphore (blocks if at limit)
            context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                locale="es-MX",
            )
            self._contexts[session_id] = context
            return context

    async def close_context(self, session_id: str) -> None:
        """Close context and release semaphore."""
        if session_id in self._contexts:
            await self._contexts[session_id].close()
            del self._contexts[session_id]
            # Semaphore automatically released when exiting 'async with' block
```

**Why 5 Sessions?**
- Chromium ~100-150MB RAM per context
- 5 contexts = ~750MB max for browsers
- Allows headroom for app itself
- Configurable via `MAX_CONCURRENT_SESSIONS` env var

### 5. Error Recovery Strategies

**Exception Hierarchy**:
```python
# File: core/exceptions.py
class AutomationError(Exception):
    """Base exception for all automation errors."""
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class LoginError(AutomationError):
    """Raised when login fails (401)."""
    pass

class NavigationError(AutomationError):
    """Raised when page navigation fails."""
    pass

class ElementNotFoundError(AutomationError):
    """Raised when expected element not found."""
    pass

class SessionExpiredError(AutomationError):
    """Raised when session expired."""
    pass

class BrowserError(AutomationError):
    """Raised when browser operations fail."""
    pass
```

**Error Handling Pattern**:
```python
from automation_service.core.exceptions import (
    LoginError,
    NavigationError,
    ElementNotFoundError,
)

async def robust_extraction(page: Page) -> dict:
    """Extraction with error handling and recovery."""
    try:
        # Try navigation
        await page.goto(url, timeout=30000)

    except PlaywrightTimeoutError as e:
        # Take screenshot for debugging
        screenshot_path = f"screenshots/error_{session_id}.png"
        await page.screenshot(path=screenshot_path)

        logger.error(
            "Navigation timeout",
            url=url,
            screenshot=screenshot_path,
            error=str(e),
        )
        raise NavigationError(
            "Page failed to load",
            details={"url": url, "screenshot": screenshot_path},
        ) from e

    try:
        # Try element extraction
        await page.wait_for_selector("div.content", timeout=10000)
        data = await extract_data(page)
        return data

    except PlaywrightTimeoutError as e:
        # Element not found - take screenshot
        await page.screenshot(path=f"screenshots/missing_element_{session_id}.png")
        raise ElementNotFoundError(
            "Expected element not found",
            details={"selector": "div.content"},
        ) from e
```

**Screenshot Strategy**:
- Always capture screenshot on failure
- Store in `screenshots/` directory (gitignored)
- Include path in error details
- Delete old screenshots (24h retention)

### 6. Wait Strategies (NEVER use sleep)

**Pattern**: Use explicit waits instead of arbitrary sleeps.

```python
from playwright.async_api import Page

async def proper_waits(page: Page):
    """Demonstrate proper waiting strategies."""

    # Wait for selector to be visible
    await page.wait_for_selector("div.content", state="visible", timeout=10000)

    # Wait for network to be idle (all requests done)
    await page.wait_for_load_state("networkidle")

    # Wait for element to be enabled
    await page.locator("button.submit").wait_for(state="enabled")

    # Wait for navigation to complete
    async with page.expect_navigation():
        await page.click("a.next-page")

    # Wait for specific text to appear
    await page.wait_for_function(
        "document.body.innerText.includes('Success')",
        timeout=5000,
    )

    # Wait for element count
    await page.wait_for_function(
        "document.querySelectorAll('div.item').length >= 5",
        timeout=10000,
    )

# WRONG - Never do this
async def bad_waits(page: Page):
    await page.goto(url)
    await asyncio.sleep(5)  # Brittle! Could be too short or too long
    await page.click("button")  # May fail if page not ready
```

### 7. Headless Browser Configuration

**Configuration in settings**:
```python
# File: core/config.py
class Settings(BaseSettings):
    # Browser settings
    BROWSER_HEADLESS: bool = True           # True for production
    BROWSER_TIMEOUT: int = 30000            # Default timeout (ms)
    BROWSER_SLOW_MO: int = 0                # Slow down for debugging (ms)

    # Club Virtual
    CLUB_VIRTUAL_BASE_URL: str = "https://clubvirtual-asd.org.mx"

    # Sessions
    SESSION_STORAGE_PATH: str = "./sessions"
    SESSION_TTL_HOURS: int = 24

    # Screenshots
    SCREENSHOTS_PATH: str = "./screenshots"
    SCREENSHOTS_ENABLED: bool = True
```

**Browser Launch Options**:
```python
# File: services/browser.py
async def initialize(self) -> None:
    """Initialize Playwright and launch browser."""
    self._playwright = await async_playwright().start()
    self._browser = await self._playwright.chromium.launch(
        headless=settings.BROWSER_HEADLESS,  # True in prod, False for debug
        slow_mo=settings.BROWSER_SLOW_MO,    # Milliseconds between actions
        args=[
            "--disable-blink-features=AutomationControlled",  # Avoid detection
            "--no-sandbox",                                   # Docker compat
            "--disable-dev-shm-usage",                        # Reduce memory
        ],
    )
```

**Debugging Tips**:
- Set `BROWSER_HEADLESS=false` to see browser
- Set `BROWSER_SLOW_MO=500` to slow down actions
- Enable `SCREENSHOTS_ENABLED=true` for failure screenshots
- Use `page.pause()` for interactive debugging

## Environment Variables

```bash
# Application
VERSION=0.1.0
ENVIRONMENT=development              # development | staging | production
DEBUG=false
LOG_LEVEL=INFO                       # DEBUG | INFO | WARNING | ERROR

# Server
HOST=0.0.0.0
PORT=8089
CORS_ORIGINS=*                       # Comma-separated: http://localhost:3000,https://app.com

# Browser Configuration
BROWSER_HEADLESS=true                # false for debugging
BROWSER_TIMEOUT=30000                # Default timeout (ms)
BROWSER_SLOW_MO=0                    # Slow down actions for debugging (ms)

# Resource Limits
MAX_CONCURRENT_SESSIONS=5            # Max parallel browser contexts

# Club Virtual
CLUB_VIRTUAL_BASE_URL=https://clubvirtual-asd.org.mx
CLUB_VIRTUAL_LOGIN_PATH=/login/auth
CLUB_VIRTUAL_SELECT_CLUB_PATH=/valida/selecciona-club

# Session Management
SESSION_STORAGE_PATH=./sessions      # Where to save session files
SESSION_TTL_HOURS=24                 # Session expiration

# Screenshots
SCREENSHOTS_PATH=./screenshots
SCREENSHOTS_ENABLED=true

# Optional: Redis for session caching
REDIS_URL=redis://localhost:6379

# Security (for credential encryption)
ENCRYPTION_KEY=<base64-encoded-key>
```

## Development Commands

```bash
# Install dependencies (includes Playwright browsers)
make install

# Install Playwright browsers manually
playwright install chromium
# Or with dependencies for Docker/Linux
playwright install --with-deps chromium

# Run service (production mode)
make run

# Run with hot reload (development)
make dev

# Run tests
make test

# Run tests with coverage
pytest --cov=automation_service --cov-report=html

# Run linter (Ruff)
make lint
ruff check .
ruff format .

# Run type checker
mypy src/

# Build Docker image
make docker-build

# Run in Docker
docker run -p 8089:8089 \
  -e BROWSER_HEADLESS=true \
  -e LOG_LEVEL=INFO \
  automation-service

# Interactive debugging (with browser visible)
BROWSER_HEADLESS=false BROWSER_SLOW_MO=500 python -m automation_service.main
```

## Dependencies

```toml
# Core
fastapi = "^0.109.0"
uvicorn = "^0.27.0"
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"

# Browser Automation
playwright = "^1.41.0"

# HTTP Client
httpx = "^0.26.0"

# Logging
structlog = "^24.1.0"

# Retry Logic
tenacity = "^8.2.0"

# Development
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
pytest-cov = "^4.1.0"
ruff = "^0.2.0"
mypy = "^1.8.0"
```

## Testing Strategies

### 1. Mock Browser Testing

```python
# File: tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
async def mock_page():
    """Mock Playwright Page for unit tests."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector = AsyncMock()

    # Mock element text extraction
    element = AsyncMock()
    element.text_content = AsyncMock(return_value="Test Name")
    page.query_selector.return_value = element

    return page

@pytest.fixture
async def mock_context():
    """Mock BrowserContext."""
    context = AsyncMock()
    context.new_page = AsyncMock(return_value=mock_page)
    context.close = AsyncMock()
    return context

# File: tests/extractors/test_profile.py
import pytest
from automation_service.services.extractors.profile import ProfileExtractor

@pytest.mark.asyncio
async def test_profile_extractor(mock_page):
    """Test profile extraction with mocked page."""
    extractor = ProfileExtractor()
    result = await extractor.extract(mock_page, "https://example.com")

    assert result["full_name"] == "Test Name"
    mock_page.goto.assert_called_once()
    mock_page.wait_for_selector.assert_called()
```

### 2. Integration Testing with Real Browser

```python
# File: tests/test_integration.py
import pytest
from playwright.async_api import async_playwright

@pytest.mark.integration  # Mark as slow test
@pytest.mark.asyncio
async def test_real_login():
    """Integration test with real browser."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto("https://clubvirtual-asd.org.mx/login/auth")
            await page.wait_for_selector("input[name='username']")

            # Fill test credentials
            await page.fill("input[name='username']", "test_user")
            await page.fill("input[name='password']", "test_pass")

            # Submit and verify
            await page.click("button[type='submit']")
            # ... assertions

        finally:
            await context.close()
            await browser.close()
```

### 3. Playwright Testing Tools

```python
# Use Playwright's built-in test fixtures
from playwright.async_api import Page, expect

async def test_with_playwright_expect(page: Page):
    """Use Playwright's expect for assertions."""
    await page.goto("https://example.com")

    # Playwright-specific assertions (auto-wait)
    await expect(page.locator("h1")).to_have_text("Welcome")
    await expect(page.locator("button")).to_be_enabled()
    await expect(page).to_have_url("https://example.com/dashboard")
```

### 4. Test Organization

```bash
tests/
├── conftest.py                  # Shared fixtures
├── test_health.py               # Health endpoint tests
│
├── unit/                        # Fast unit tests (mocked)
│   ├── test_config.py
│   ├── test_exceptions.py
│   └── test_browser_manager.py
│
├── extractors/                  # Extractor unit tests
│   ├── test_base.py
│   ├── test_profile.py
│   └── test_tasks.py
│
└── integration/                 # Slow integration tests (real browser)
    ├── test_login_flow.py
    └── test_full_extraction.py
```

**Run Tests**:
```bash
# Run all tests
pytest

# Run only unit tests (fast)
pytest tests/unit/ tests/extractors/

# Run only integration tests (slow)
pytest tests/integration/ -m integration

# Run with coverage
pytest --cov=automation_service --cov-report=html

# Run specific test
pytest tests/extractors/test_profile.py::test_profile_extractor -v
```

## SLO Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Availability | 99.5% | Browser crashes excluded |
| P50 Latency | 5000ms | Login + single extraction |
| **P95 Latency** | **15000ms** | **Due to browser overhead + network** |
| P99 Latency | 30000ms | Heavy pages, slow networks |
| Success Rate | 95% | Excludes invalid credentials |
| Error Rate | <5% | Transient failures only |

**Why P95 is 15 seconds?**
- Browser launch/context creation: 500-1000ms
- Page navigation + network: 2000-5000ms
- Login flow (2-3 pages): 3000-6000ms
- Data extraction + waits: 2000-4000ms
- Screenshot capture on error: 500-1000ms
- Total with variance: 10000-15000ms at P95

**Performance Tips**:
- Reuse browser contexts for multiple operations
- Use `page.wait_for_load_state("domcontentloaded")` instead of `"networkidle"` when possible
- Run independent extractions in parallel with `asyncio.gather()`
- Implement request-level timeouts to prevent long tails

## Related Services

This service is called by:

- **Identity Service** (8080) - User authentication via Club Virtual credentials
- **Organization Service** (8081) - Member data sync from Club Virtual
- **Profile Import Service** (8082) - Bulk profile imports

This service calls:
- **Club Virtual IASD** (https://clubvirtual-asd.org.mx) - External target system

## Critical Notes for AI Agents

### 1. Browser Context Lifecycle

**NEVER share contexts between users** - Each user gets a fresh context for isolation.

```python
# CORRECT - Fresh context per request
@router.post("/extract")
async def extract(request: ExtractRequest):
    session_id = str(uuid4())
    context = None
    try:
        context = await browser_manager.create_context(session_id)
        # ... automation
    finally:
        if context:
            await context.close()

# WRONG - Reusing context across users
# This will leak cookies and session data!
shared_context = await browser.new_context()  # DON'T DO THIS

@router.post("/extract")
async def extract(request: ExtractRequest):
    page = await shared_context.new_page()  # Multiple users share cookies!
```

### 2. Credential Security

**NEVER log credentials** - Mask sensitive data in all logs.

```python
import structlog

logger = structlog.get_logger()

# CORRECT - Masked logging
logger.info(
    "Login attempt",
    username=username[:3] + "***",  # Only first 3 chars
    club_id=club_id,
)

# WRONG - Credential leak
logger.info("Login", username=username, password=password)
logger.debug("Request data", data=request.dict())  # May contain password
```

### 3. Async/Await Enforcement

**ALL Playwright operations are async** - Missing `await` will cause runtime errors.

```python
# CORRECT
async def navigate(page: Page):
    await page.goto(url)
    await page.wait_for_selector("div.content")
    text = await page.locator("h1").text_content()

# WRONG - Missing await
async def navigate(page: Page):
    page.goto(url)  # Returns coroutine, doesn't navigate!
    page.wait_for_selector("div.content")  # Never executes
```

### 4. Resource Cleanup Checklist

Before deploying any automation code, verify:

- [ ] Browser contexts closed in `finally` blocks
- [ ] Sessions removed from BrowserManager registry
- [ ] Screenshots cleaned up (24h retention)
- [ ] Semaphore not exhausted (max 5 sessions)
- [ ] No credential leaks in logs
- [ ] All Playwright operations have `await`
- [ ] Retry logic for transient failures
- [ ] Explicit waits (no `asyncio.sleep`)
- [ ] Error handling with screenshots
- [ ] Timeouts configured on all operations

### 5. Adding New Extractors

To add a new extractor (e.g., `specialties`):

1. **Create extractor file**: `services/extractors/specialties.py`
   ```python
   from automation_service.services.extractors.base import BaseExtractor, ExtractorRegistry

   @ExtractorRegistry.register
   class SpecialtiesExtractor(BaseExtractor):
       name = "specialties"
       description = "Extracts user specialties and badges"

       async def extract(self, page: Page, base_url: str) -> dict:
           await page.goto(f"{base_url}/mis-especialidades")
           # ... extraction logic
           return {"specialties": []}
   ```

2. **Import in `__init__.py`**: `services/extractors/__init__.py`
   ```python
   from .specialties import SpecialtiesExtractor
   ```

3. **Add test**: `tests/extractors/test_specialties.py`
   ```python
   @pytest.mark.asyncio
   async def test_specialties_extractor(mock_page):
       extractor = SpecialtiesExtractor()
       result = await extractor.extract(mock_page, "https://example.com")
       assert "specialties" in result
   ```

4. **Verify registration**:
   ```python
   # Should now appear in list
   ExtractorRegistry.list_extractors()  # ["profile", "tasks", "specialties"]
   ```

### 6. Common Playwright Selectors

**Club Virtual IASD specific selectors** (may change, verify in browser):

```python
# Login page
LOGIN_USERNAME = "input[name='username']"
LOGIN_PASSWORD = "input[name='password']"
LOGIN_SUBMIT = "button[type='submit']"

# Club selection
CLUB_DROPDOWN = "select#club-select"
CLUB_OPTION = f"option[value='{club_id}']"

# Dashboard
DASHBOARD_CONTAINER = "div.dashboard"
USER_NAME = "h1.profile-name"
LOGOUT_BUTTON = "a[href*='logout']"

# Classes/Tasks
ACTIVE_CLASSES = "div.class-card"
CLASS_NAME = "h3.class-title"
PROGRESS_BAR = "div.progress-percentage"
INVESTITURE_BADGE = "span.ready-for-investiture"
```

### 7. Error Messages (Spanish)

Common error messages from Club Virtual:

```python
# Login errors
"Usuario o contraseña incorrectos"     # Invalid credentials
"No se encontró el club especificado"  # Club not found
"Sesión expirada"                      # Session expired
"Debes seleccionar un club"            # Must select club

# Navigation errors
"Página no encontrada"                 # 404
"Acceso denegado"                      # Permission denied
```

### 8. Session Management Patterns

**Pattern 1: Stateless (Recommended)**
```python
# One-shot extraction, no session persistence
@router.post("/extract")
async def extract(request: ExtractRequest):
    session_id = str(uuid4())
    context = None
    try:
        context = await browser_manager.create_context(session_id)
        # Login + extract + cleanup all in one request
    finally:
        await context.close()
```

**Pattern 2: Stateful (Multi-step)**
```python
# Step 1: Login and save session
@router.post("/auth/login")
async def login(request: LoginRequest):
    session_id = str(uuid4())
    context = await browser_manager.create_context(session_id)
    # Login and keep context open
    await browser_manager.save_session(session_id)
    return {"session_id": session_id}

# Step 2: Use session for automation
@router.get("/sessions/{session_id}/data")
async def get_data(session_id: str):
    context = await browser_manager.get_context(session_id)
    page = await context.new_page()
    # Extract data using existing session

# Step 3: Cleanup
@router.delete("/sessions/{session_id}")
async def cleanup(session_id: str):
    await browser_manager.close_context(session_id)
```

## Reference

For comprehensive Playwright patterns and best practices, see `.cursorrules` in this directory.

**Key Documentation**:
- Playwright Python Docs: https://playwright.dev/python/
- FastAPI Async: https://fastapi.tiangolo.com/async/
- Tenacity Retry: https://tenacity.readthedocs.io/
- Structlog: https://www.structlog.org/

**Architecture Decisions**:
- Stateless design (no DB) for simplicity and scalability
- Semaphore-based resource limits for memory management
- Plugin architecture (ExtractorRegistry) for extensibility
- Retry with exponential backoff for reliability
- Screenshot-on-failure for debuggability
