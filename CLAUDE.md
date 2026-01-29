# Automation Service

## Overview

The **Automation Service** provides browser automation and web scraping capabilities for extracting data from external systems like Club Virtual. Written in **Python** using FastAPI and Playwright.

## Service Details

| Property | Value |
|----------|-------|
| Language | Python 3.12+ |
| Port | 8089 |
| Framework | FastAPI |
| Browser | Playwright (Chromium) |
| Database | None (stateless) |

## Responsibilities

- Browser automation for external system integration
- Web scraping and data extraction
- Login flow handling
- Session management
- Profile and task extraction from Club Virtual

## Project Structure

```
automation-service/
├── src/automation_service/
│   ├── __init__.py
│   ├── main.py                     # FastAPI entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py               # HTTP endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               # Configuration
│   │   ├── exceptions.py           # Custom exceptions
│   │   └── logging.py              # Structured logging
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py              # Pydantic models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── browser.py              # Browser management
│   │   ├── club_virtual.py         # Club Virtual scraping
│   │   ├── login_flow.py           # Login handling
│   │   ├── orchestrator.py         # Task orchestration
│   │   └── extractors/
│   │       ├── __init__.py
│   │       ├── base.py             # Base extractor
│   │       ├── profile.py          # Profile extraction
│   │       └── tasks.py            # Task extraction
│   └── utils/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_*.py
├── pyproject.toml
├── Dockerfile
├── docs/
└── Makefile
```

## API Endpoints

```
# Scraping Operations
POST   /api/v1/scrape/profile        # Extract user profile
POST   /api/v1/scrape/tasks          # Extract user tasks
POST   /api/v1/scrape/full           # Full data extraction

# Session Management
POST   /api/v1/session/create        # Create browser session
DELETE /api/v1/session/:id           # Close session
GET    /api/v1/session/:id/status    # Check session status

# Health
GET    /health/live
GET    /health/ready
GET    /metrics
```

## Request/Response Models

```python
class ScrapeRequest(BaseModel):
    user_id: UUID
    username: str
    password: str  # Encrypted
    target_url: str
    extraction_type: str

class ScrapeResponse(BaseModel):
    task_id: UUID
    status: str
    data: Optional[dict]
    error: Optional[str]
    duration_ms: int
```

## Key Patterns

### Browser Context Management
```python
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Custom User Agent",
        viewport={"width": 1920, "height": 1080}
    )
    page = await context.new_page()
    try:
        await page.goto(url)
        # Extraction logic
    finally:
        await context.close()
        await browser.close()
```

### Retry with Backoff
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(TimeoutError)
)
async def extract_data(page: Page) -> dict:
    # Extraction with retry
```

### Base Extractor Pattern
```python
class BaseExtractor(ABC):
    def __init__(self, page: Page):
        self.page = page

    @abstractmethod
    async def extract(self) -> dict:
        pass

    async def safe_get_text(self, selector: str) -> Optional[str]:
        try:
            element = await self.page.query_selector(selector)
            if element:
                return (await element.text_content()).strip()
        except Exception:
            pass
        return None
```

## Development Commands

```bash
# Install dependencies
make install

# Run service
make run

# Run with hot reload
make dev

# Run tests
make test

# Run linter
make lint

# Build Docker image
make docker-build
```

## Environment Variables

```bash
PORT=8089
LOG_LEVEL=INFO
BROWSER_HEADLESS=true
BROWSER_TIMEOUT=30000
MAX_CONCURRENT_SESSIONS=5
REDIS_URL=redis://localhost:6379
```

## Dependencies

```toml
[project.dependencies]
fastapi = "^0.109.0"
uvicorn = "^0.27.0"
pydantic = "^2.5.0"
playwright = "^1.41.0"
httpx = "^0.26.0"
structlog = "^24.1.0"
tenacity = "^8.2.0"
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
```

## Testing

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_profile_extraction():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/scrape/profile", json={
            "user_id": "123e4567-e89b-12d3-a456-426614174000",
            "username": "test",
            "password": "encrypted",
            "target_url": "https://example.com"
        })
    assert response.status_code == 200
```

## SLO Targets

| Metric | Target |
|--------|--------|
| Availability | 99.5% |
| P50 Latency | 5000ms |
| P95 Latency | 15000ms |
| Success Rate | 95% |

## Related Services

This service is called by:
- **Identity Service** (8080) - Profile import
- **Organization Service** (8081) - Member data sync

## Important Notes

1. **Browser isolation** - Each request gets fresh browser context
2. **Resource limits** - Limit concurrent browser sessions
3. **Timeouts** - Use generous timeouts for page loads
4. **Error recovery** - Implement retry logic for transient failures
5. **Credentials** - Never log sensitive data
