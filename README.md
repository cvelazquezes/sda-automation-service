# Automation Service

> **Enterprise-Grade Browser Automation & Web Scraping Microservice**
> Intelligent data extraction from external systems using Playwright, built with Python and async-first architecture

[![Python Version](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Framework](https://img.shields.io/badge/Framework-FastAPI-green.svg)](https://fastapi.tiangolo.com)
[![Browser](https://img.shields.io/badge/Browser-Playwright-red.svg)](https://playwright.dev)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Enterprise Patterns](#enterprise-patterns)
- [API Specification](#api-specification)
- [Performance & Scalability](#performance--scalability)
- [Observability](#observability)
- [Development](#development)
- [Deployment](#deployment)
- [Testing Strategy](#testing-strategy)

---

## 🎯 Overview

The Automation Service is the **intelligent automation engine** of the SDA Master Guide Platform. It provides robust browser automation capabilities for extracting data from external systems like Club Virtual IASD, enabling seamless integration with third-party platforms that lack APIs.

### Service Characteristics

| Property | Value | Rationale |
|----------|-------|-----------|
| **Language** | Python 3.12+ | Rich async ecosystem, excellent scraping libraries |
| **Framework** | FastAPI | High performance async, automatic OpenAPI docs |
| **Port** | 8088 | Dedicated automation service port |
| **Browser** | Playwright (Chromium) | Modern automation, multi-browser support, reliable |
| **Database** | None (stateless) | Ephemeral sessions, no persistent state needed |
| **Pattern** | Extractor Registry | Plugin architecture for modular scrapers |

### Bounded Context

**Automation & Data Integration** - This service owns:
- Browser session management
- Web scraping and data extraction
- External system authentication
- Automated data collection workflows
- Screenshot capture for debugging

### Key Use Cases

1. **Club Virtual IASD Integration**: Extract member profiles, progress tracking, and club data
2. **Profile Synchronization**: Import user information from external systems
3. **Task Progress Tracking**: Monitor member advancement and specialty completion
4. **Automated Reporting**: Collect data for analytics and dashboards

---

## 🏗️ Architecture

### High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                  Automation Service (Python)                        │
│                          Port: 8088                                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   HTTP Layer (FastAPI)                       │  │
│  │  ┌──────────┬──────────┬──────────┬──────────┬────────────┐ │  │
│  │  │  Health  │  Auth    │  Extract │ Session  │ Middleware │ │  │
│  │  │  Routes  │  Routes  │  Routes  │  Mgmt    │  (CORS)    │ │  │
│  │  └──────────┴──────────┴──────────┴──────────┴────────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                 │                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              Service Layer (Business Logic)                  │  │
│  │  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐ │  │
│  │  │ ClubVirtual    │  │  Orchestrator│  │   LoginFlow     │ │  │
│  │  │ Service        │  │  (Coordin.)  │  │   (Auth)        │ │  │
│  │  └────────────────┘  └──────────────┘  └─────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                 │                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │             Extractor Layer (Plugin System)                  │  │
│  │  ┌───────────────┐  ┌───────────────┐  ┌────────────────┐  │  │
│  │  │    Profile    │  │     Tasks     │  │  Specialties   │  │  │
│  │  │   Extractor   │  │   Extractor   │  │   Extractor    │  │  │
│  │  └───────────────┘  └───────────────┘  └────────────────┘  │  │
│  │           ▲                  ▲                  ▲            │  │
│  │           └──────────────────┴──────────────────┘            │  │
│  │                  BaseExtractor (ABC)                         │  │
│  │                ExtractorRegistry (Discovery)                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                 │                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │          Browser Layer (Playwright Management)               │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │              BrowserManager                             │ │  │
│  │  │  • Context isolation (per-session)                      │ │  │
│  │  │  • Resource pooling                                     │ │  │
│  │  │  • Session persistence                                  │ │  │
│  │  │  • Screenshot capture                                   │ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  │                                                               │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐            │  │
│  │  │ Context A  │  │ Context B  │  │ Context C  │   ...      │  │
│  │  │ (User 1)   │  │ (User 2)   │  │ (User 3)   │            │  │
│  │  │  ┌──────┐  │  │  ┌──────┐  │  │  ┌──────┐  │            │  │
│  │  │  │ Page │  │  │  │ Page │  │  │  │ Page │  │            │  │
│  │  │  └──────┘  │  │  └──────┘  │  │  └──────┘  │            │  │
│  │  └────────────┘  └────────────┘  └────────────┘            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                 │                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │          Infrastructure Layer (Technical)                    │  │
│  │  ┌──────────────┬──────────────┬──────────────┬───────────┐ │  │
│  │  │  Structlog   │   Tenacity   │  Pydantic    │  Uvicorn  │ │  │
│  │  │  (Logging)   │   (Retry)    │ (Validation) │  (ASGI)   │ │  │
│  │  └──────────────┴──────────────┴──────────────┴───────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │   Chromium   │   │  Screenshot  │   │    Jaeger    │
    │   Browser    │   │   Storage    │   │  (tracing)   │
    └──────────────┘   └──────────────┘   └──────────────┘
```

### Directory Structure (Modern Python)

```
automation-service/
├── src/
│   └── automation_service/
│       ├── __init__.py
│       ├── main.py                          # FastAPI app & lifespan
│       │
│       ├── api/                             # HTTP Layer
│       │   ├── __init__.py
│       │   └── routes.py                   # All REST endpoints
│       │
│       ├── core/                            # Core Infrastructure
│       │   ├── __init__.py
│       │   ├── config.py                   # Settings (pydantic-settings)
│       │   ├── exceptions.py               # Custom exceptions
│       │   └── logging.py                  # Structured logging setup
│       │
│       ├── models/                          # Data Models
│       │   ├── __init__.py
│       │   └── schemas.py                  # Pydantic request/response models
│       │
│       ├── services/                        # Business Logic
│       │   ├── __init__.py
│       │   ├── browser.py                  # BrowserManager (Playwright)
│       │   ├── club_virtual.py             # Club Virtual automation
│       │   ├── login_flow.py               # Authentication workflow
│       │   ├── orchestrator.py             # Multi-extractor coordination
│       │   └── extractors/                 # Extractor Plugins
│       │       ├── __init__.py
│       │       ├── base.py                 # BaseExtractor + Registry
│       │       ├── profile.py              # Profile data extractor
│       │       ├── tasks.py                # Tasks & progress extractor
│       │       └── specialties.py          # Badges/specialties extractor
│       │
│       └── utils/                           # Utilities
│           └── __init__.py
│
├── tests/                                   # Test Suite
│   ├── __init__.py
│   ├── conftest.py                         # Pytest fixtures
│   ├── test_health.py                      # Health check tests
│   ├── test_extractors.py                  # Extractor tests
│   └── test_browser.py                     # Browser manager tests
│
├── docs/                                    # Documentation
│   ├── ADR/                                # Architecture Decision Records
│   │   ├── 001-playwright-over-selenium.md
│   │   ├── 002-extractor-pattern.md
│   │   └── 003-session-management.md
│   └── SCRAPING_GUIDE.md                   # Web scraping best practices
│
├── screenshots/                             # Debug screenshots
├── sessions/                                # Session storage
│
├── pyproject.toml                          # Project config & dependencies
├── Dockerfile                              # Multi-stage container build
├── .env.example                            # Environment variables template
├── Makefile                                # Development commands
└── README.md                               # This file
```

---

## 🎨 Enterprise Patterns

### 1. Browser Context Isolation

```python
# Each request gets a fresh, isolated browser context
# Prevents cookie leakage and state contamination

class BrowserManager:
    """
    Manages browser instances and contexts (sessions).

    Architecture:
        1 Browser Instance (shared)
        ├─ Context A (User 1 session)
        │  └─ Page (tabs)
        ├─ Context B (User 2 session)
        │  └─ Page
        └─ Context C (User 3 session)
           └─ Page

    Each context has:
    - Isolated cookies
    - Separate localStorage/sessionStorage
    - Independent cache
    - Unique viewport settings
    """

    async def create_context(self, session_id: str) -> BrowserContext:
        """Create isolated browser context for a session."""
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            locale="es-MX",
            timezone_id="America/Mexico_City",
            # No shared state between contexts
        )
        context.set_default_timeout(settings.BROWSER_TIMEOUT)
        self._contexts[session_id] = context
        return context
```

**Benefits:**
- ✅ Parallel execution: Multiple users can authenticate simultaneously
- ✅ Security: No session data leakage between users
- ✅ Reliability: Crashes in one context don't affect others
- ✅ Clean state: Each session starts fresh

### 2. Extractor Registry Pattern (Plugin Architecture)

```python
# Dynamic extractor discovery and registration
# Allows adding new scrapers without modifying core code

class ExtractorRegistry:
    """
    Central registry for all data extractors.

    Plugin Discovery Pattern:
    - Extractors self-register via @decorator
    - Dynamic instantiation by name
    - Runtime discovery of capabilities
    """

    _extractors: ClassVar[dict[str, type[BaseExtractor]]] = {}

    @classmethod
    def register(cls, extractor_class: type[BaseExtractor]):
        """Register an extractor. Use as decorator."""
        cls._extractors[extractor_class.name] = extractor_class
        return extractor_class

    @classmethod
    def get(cls, name: str) -> BaseExtractor:
        """Get extractor by name."""
        if name not in cls._extractors:
            raise ValueError(f"Unknown extractor: '{name}'")
        return cls._extractors[name]()


# Create new extractor - just add file and decorate
@ExtractorRegistry.register
class ProfileExtractor(BaseExtractor):
    name = "profile"
    description = "Extracts user profile information"

    async def extract(self, page: Page, base_url: str) -> dict:
        """Extract profile data."""
        await page.goto(f"{base_url}/mi-perfil")
        # Scraping logic here
        return {"full_name": "...", "email": "..."}
```

**Benefits:**
- ✅ Extensibility: Add new extractors without touching existing code
- ✅ Discoverability: `GET /extract/available` lists all extractors
- ✅ Composability: Mix and match extractors in single request
- ✅ Testability: Each extractor can be tested in isolation

### 3. Retry with Exponential Backoff (Tenacity)

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# Automatic retry for transient failures (network, timeouts)

@retry(
    stop=stop_after_attempt(3),              # Max 3 attempts
    wait=wait_exponential(                   # Exponential backoff
        multiplier=1,
        min=2,                               # Start at 2 seconds
        max=10                               # Cap at 10 seconds
    ),
    retry=retry_if_exception_type((
        TimeoutError,
        ConnectionError,
    )),
    before_sleep=log_retry_attempt,          # Observability
)
async def navigate_with_retry(page: Page, url: str) -> None:
    """Navigate to URL with automatic retry."""
    await page.goto(url, wait_until="networkidle", timeout=15000)


# Retry sequence: 2s → 4s → 8s (capped at 10s)
# Total time: ~14 seconds before giving up
```

**Why Exponential Backoff?**
- Avoids overwhelming the target server
- Gives time for transient issues to resolve
- Industry standard (AWS, Google Cloud, etc.)
- Prevents thundering herd problem

### 4. Async-First Architecture

```python
# All I/O operations are async - maximize concurrency

async def extract_multiple_users(users: list[User]) -> list[Profile]:
    """Extract profiles for multiple users concurrently."""
    tasks = [
        extract_profile(user.username, user.password)
        for user in users
    ]
    # Run all extractions in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]


# FastAPI endpoints are async by default
@router.post("/extract")
async def extract_data(
    request: ExtractRequest,
    orchestrator: ExtractOrchestrator = Depends(get_orchestrator),
) -> ExtractResponse:
    """Async endpoint - won't block event loop."""
    return await orchestrator.extract(
        username=request.username,
        password=request.password,
        include=request.include,
    )
```

**Performance Impact:**
- Single thread can handle 100+ concurrent requests
- No thread overhead (GIL not a bottleneck)
- Efficient resource utilization
- Better scalability than sync alternatives

### 5. Graceful Degradation & Error Handling

```python
# Fail gracefully, return partial results

async def extract(self, include: list[str]) -> ExtractResponse:
    """Extract data with fault tolerance."""
    extracted_data = {}
    errors = []

    for extractor_name in include:
        try:
            extractor = ExtractorRegistry.get(extractor_name)
            data = await extractor.extract(page, base_url)
            extracted_data[extractor_name] = data
        except ValueError as e:
            # Unknown extractor - skip and continue
            errors.append(f"Unknown extractor: {extractor_name}")
        except Exception as e:
            # Extraction failed - log and continue
            errors.append(f"{extractor_name}: {str(e)}")
            logger.warning("Extractor failed", extractor=extractor_name)

    # Return partial success
    return ExtractResponse(
        success=len(extracted_data) > 0,
        profile=extracted_data.get("profile"),
        tasks=extracted_data.get("tasks"),
        errors=errors,  # Include errors for debugging
    )
```

**Philosophy:**
- Fail fast on critical errors (auth failure)
- Fail gracefully on optional data (profile pic missing)
- Always return structured error information
- Never leave resources uncleaned

### 6. Resource Management & Cleanup

```python
# Ensure browser contexts are always cleaned up

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    app.state.browser_manager = BrowserManager()
    await app.state.browser_manager.initialize()

    yield  # Application runs

    # Shutdown - guaranteed to run
    await app.state.browser_manager.close()


# Per-request cleanup with try/finally
async def extract(self, ...):
    session_id = None
    try:
        # Login and extraction
        login_result = await self.login_flow.execute(...)
        session_id = login_result.session_id
        # ... perform extraction
        return response
    finally:
        # ALWAYS cleanup browser context
        if session_id:
            await self.browser_manager.close_context(session_id)
```

**Best Practices:**
- Use context managers (`async with`, `@asynccontextmanager`)
- Always cleanup in `finally` blocks
- Set resource limits (max concurrent sessions)
- Monitor resource usage (memory, CPU, open file descriptors)

### 7. Observability-First Design

```python
import structlog

# Structured logging with context
logger = structlog.get_logger()

async def extract(self, username: str, include: list[str]):
    """Extract data with full observability."""
    logger.info(
        "Starting extraction",
        username=username,
        include=include,
        service="automation",
    )

    start_time = time.time()

    try:
        # ... extraction logic

        logger.info(
            "Extraction completed",
            username=username,
            extracted=list(data.keys()),
            duration_ms=(time.time() - start_time) * 1000,
            success=True,
        )
        return data

    except Exception as e:
        logger.error(
            "Extraction failed",
            username=username,
            error=str(e),
            duration_ms=(time.time() - start_time) * 1000,
            success=False,
        )
        raise


# Every log entry is JSON with full context
# {"event": "Extraction completed", "username": "john",
#  "extracted": ["profile", "tasks"], "duration_ms": 3420, ...}
```

---

## 📖 API Specification

### Base URL

```
Development: http://localhost:8088
Production:  https://automation.sda-platform.com
```

### Authentication

No service-level authentication required. Credentials are passed per-request for target systems.

### Key Endpoints

#### Health & Monitoring

```http
GET /api/v1/health                 # Full health check
GET /api/v1/health/live            # Kubernetes liveness probe
GET /api/v1/health/ready           # Kubernetes readiness probe
GET /metrics                       # Prometheus metrics
```

#### Authentication (Club Virtual)

```http
POST /api/v1/auth/login/simple     # Simple credential validation
POST /api/v1/auth/login            # Full login with club selection
POST /api/v1/auth/logout           # Logout and cleanup session
```

#### Data Extraction (Recommended)

```http
POST /api/v1/extract               # Combined login + extraction
GET  /api/v1/extract/available     # List available extractors
```

#### Session Management

```http
GET    /api/v1/sessions/{id}       # Check session status
DELETE /api/v1/sessions/{id}       # Close session
```

#### Automation Tasks (Advanced)

```http
GET /api/v1/sessions/{id}/tasks-and-reports    # Get task progress
GET /api/v1/sessions/{id}/specialties          # Get badges/specialties
```

### Example: Combined Extraction Request

**Request:**
```http
POST /api/v1/extract
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "SecurePass123!",
  "club_type": "Aventureros",
  "club_name": "Peniel",
  "include": ["profile", "tasks"]
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Club: Peniel (Aventureros) | Extracted: profile, tasks",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "login": {
    "clubs": [
      {
        "id": 7037,
        "name": "Peniel",
        "club_type": "Aventureros",
        "role": "Director"
      }
    ],
    "selected_club": {
      "id": 7037,
      "name": "Peniel",
      "club_type": "Aventureros",
      "role": "Director"
    }
  },
  "profile": {
    "full_name": "Juan Pérez",
    "username": "jperez",
    "email": "juan@email.com",
    "birthday": "2016-03-15",
    "age": 8,
    "gender": "Masculino",
    "phone": "+52 123 456 7890",
    "address": "Calle Principal 123",
    "avatar_url": "https://clubvirtual-asd.org.mx/avatar.jpg"
  },
  "tasks": {
    "active_classes": [
      {
        "name": "Abejas",
        "completion_percentage": 75.0,
        "status": "En progreso",
        "is_ready_for_investiture": false,
        "image_url": "https://..."
      },
      {
        "name": "Constructores",
        "completion_percentage": 100.0,
        "status": "Autorizado para investir",
        "is_ready_for_investiture": true,
        "image_url": "https://..."
      }
    ],
    "total_classes": 2,
    "overall_completion": 87.5
  },
  "extracted_at": "2024-01-29T15:30:45.123456",
  "screenshot_path": "/screenshots/extract_abc123_20240129_153045.png",
  "errors": null
}
```

### API Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Simplicity** | Single endpoint (`/extract`) for most use cases |
| **Composability** | Mix extractors via `include` parameter |
| **Fault Tolerance** | Return partial results with errors array |
| **Idempotency** | Safe to retry - no side effects |
| **Observability** | Include timing, screenshot paths |

---

## ⚡ Performance & Scalability

### Performance Targets (SLO)

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Availability** | 99.5% | Lower than Identity (dependent on external systems) |
| **P50 Latency** | < 5000ms | Browser automation is inherently slow |
| **P95 Latency** | < 15000ms | Complex pages with dynamic content |
| **P99 Latency** | < 30000ms | Worst case with retries |
| **Throughput** | 50 RPS | Limited by browser resource consumption |
| **Success Rate** | > 95% | External system availability dependency |

### Why Higher Latency?

Browser automation is **intentionally slow** compared to API services:

```
┌────────────────────────────────────────────────────────────┐
│  API Service (Identity)     vs    Automation Service       │
├────────────────────────────────────────────────────────────┤
│  • Database query: 5-20ms         • Browser launch: 500ms  │
│  • JSON parsing: <1ms             • Page load: 2-5s        │
│  • Token validation: 2ms          • Wait for JS: 1-3s      │
│  • Response: 50-150ms             • Element extraction: 500ms│
│  ─────────────────────────────────────────────────────────│
│  Total: ~50-150ms                 Total: ~5-15 seconds     │
└────────────────────────────────────────────────────────────┘
```

**Optimization Strategies:**
- Parallel extraction (run multiple extractors concurrently)
- Intelligent waiting (avoid arbitrary `sleep()`, use `wait_for_selector()`)
- Minimize navigation (extract multiple data types per login)
- Browser context pooling (keep contexts warm)
- Caching (store session state for repeated operations)

### Scalability Characteristics

**Horizontal Scaling:**
```yaml
# Kubernetes HPA configuration
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: automation-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: automation-service
  minReplicas: 2                   # Minimum instances
  maxReplicas: 10                  # Maximum instances
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60   # Lower than typical (CPU-heavy)
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 70   # Chromium is memory-hungry
```

**Resource Consumption:**

| Component | Memory | CPU | Notes |
|-----------|--------|-----|-------|
| Chromium Browser | 150-300 MB | 0.1-0.5 cores | Per instance (shared) |
| Browser Context | 50-100 MB | 0.05 cores | Per active session |
| Page/Tab | 20-50 MB | 0.02 cores | Per page |
| Python Process | 100-200 MB | 0.1 cores | Base overhead |

**Recommended Resource Limits:**

Development:
- CPU: 1 core
- Memory: 1 GB
- Max Concurrent Sessions: 5

Production (per pod):
- CPU: 2 cores (request: 0.5, limit: 2)
- Memory: 4 GB (request: 2 GB, limit: 4 GB)
- Max Concurrent Sessions: 10-15

### Concurrency Control

```python
import asyncio

class BrowserManager:
    """Browser manager with concurrency limits."""

    def __init__(self, max_concurrent_sessions: int = 10):
        self._semaphore = asyncio.Semaphore(max_concurrent_sessions)

    async def create_context(self, session_id: str):
        """Create context with concurrency limit."""
        async with self._semaphore:
            # Only N contexts can be created simultaneously
            context = await self._browser.new_context(...)
            return context


# Prevents memory exhaustion from too many concurrent sessions
# Provides backpressure when system is under load
```

---

## 📊 Observability

### Metrics (Prometheus)

**RED Metrics (Request-based):**
```
# Rate - Requests per second
http_requests_total{service="automation",endpoint="/extract"}

# Errors - Error rate
http_requests_failed{service="automation",error_type="login_failed"}

# Duration - Response time (note: seconds, not milliseconds)
http_request_duration_seconds{service="automation",endpoint="/extract"}
```

**Application Metrics:**
```
# Browser Management
browser_contexts_active               # Active browser sessions
browser_contexts_total               # Total contexts created
browser_page_loads_total             # Pages loaded
browser_screenshots_captured_total   # Screenshots taken

# Extraction
extraction_attempts_total{extractor="profile",status="success"}
extraction_duration_seconds{extractor="tasks"}

# Resource Usage
browser_memory_usage_bytes
browser_cpu_usage_seconds_total

# Business Metrics
club_virtual_logins_total{status="success"}
club_virtual_clubs_selected_total{club_type="Aventureros"}
data_points_extracted_total{type="profile"}
```

### Structured Logging (Structlog)

**Log Format (JSON):**
```json
{
  "timestamp": "2024-01-29T15:30:45.123456Z",
  "level": "info",
  "event": "extraction_completed",
  "service": "automation-service",
  "username": "jperez",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "extracted": ["profile", "tasks"],
  "duration_ms": 4523,
  "success": true,
  "club_type": "Aventureros",
  "club_name": "Peniel"
}
```

**Log Levels:**
- **DEBUG**: Extractor details, page navigation, element selectors
- **INFO**: Extraction start/complete, login success, session lifecycle
- **WARNING**: Extractor failures, retry attempts, degraded functionality
- **ERROR**: Login failures, browser crashes, unrecoverable errors

### Alerting Rules

```yaml
# Prometheus AlertManager Rules

- alert: HighExtractionFailureRate
  expr: rate(extraction_attempts_total{status="failed"}[5m]) > 0.05
  for: 5m
  annotations:
    summary: "High extraction failure rate (>5%)"

- alert: BrowserMemoryHigh
  expr: browser_memory_usage_bytes > 3000000000  # 3 GB
  for: 10m
  annotations:
    summary: "Browser memory usage exceeds 3 GB"

- alert: SlowExtractionLatency
  expr: histogram_quantile(0.95, extraction_duration_seconds) > 20
  for: 10m
  annotations:
    summary: "P95 extraction latency exceeds 20 seconds"

- alert: TooManyConcurrentSessions
  expr: browser_contexts_active > 15
  for: 5m
  annotations:
    summary: "Too many concurrent browser sessions"
```

---

## 🛠️ Development

### Prerequisites

- Python 3.12+
- Make
- Docker (optional)
- Playwright browsers

### Quick Start

```bash
# Clone repository
git clone <repo-url>
cd automation-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium

# Copy configuration
cp .env.example .env

# Run service
make run

# Or run with hot reload (uvicorn auto-reload)
make dev
```

### Environment Variables

```bash
# Server
PORT=8088
HOST=0.0.0.0
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO

# Browser
BROWSER_HEADLESS=true
BROWSER_TIMEOUT=30000      # milliseconds
BROWSER_SLOW_MO=0          # milliseconds between actions (for debugging)

# Club Virtual
CLUB_VIRTUAL_BASE_URL=https://clubvirtual-asd.org.mx
CLUB_VIRTUAL_LOGIN_PATH=/login/auth
CLUB_VIRTUAL_SELECT_CLUB_PATH=/valida/selecciona-club

# Sessions
SESSION_STORAGE_PATH=./sessions
SESSION_TTL_HOURS=24

# Screenshots
SCREENSHOTS_PATH=./screenshots
SCREENSHOTS_ENABLED=true

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Redis (optional, for session caching)
REDIS_URL=redis://localhost:6379/0
```

### Makefile Commands

```bash
# Development
make run                  # Run service with uvicorn
make dev                  # Run with auto-reload
make test                 # Run tests with pytest
make test-coverage        # Run tests with coverage report
make lint                 # Run ruff linter
make format               # Format code with black & ruff
make type-check           # Run mypy type checking

# Browser Management
make install-browsers     # Install Playwright browsers
make browser-debug        # Run browser in headed mode

# Docker
make docker-build         # Build Docker image
make docker-run           # Run in Docker
make docker-compose-up    # Start with dependencies

# Cleanup
make clean                # Clean generated files
make clean-screenshots    # Delete old screenshots
```

### Adding a New Extractor

1. **Create extractor file** in `src/automation_service/services/extractors/`:

```python
# my_extractor.py

from typing import TYPE_CHECKING, Any
import structlog
from automation_service.services.extractors.base import (
    BaseExtractor,
    ExtractorRegistry,
)

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = structlog.get_logger()


@ExtractorRegistry.register
class MyExtractor(BaseExtractor):
    """Extracts my custom data from Club Virtual."""

    name = "my_data"
    description = "Extracts my custom data points"
    requires_navigation = True

    async def extract(self, page: "Page", base_url: str) -> dict[str, Any]:
        """Extract custom data."""
        # Navigate to target page
        await page.goto(f"{base_url}/my-page")

        # Wait for content
        await page.wait_for_selector(".my-content")

        # Extract data
        data = await page.evaluate("""() => {
            const element = document.querySelector('.my-content');
            return {
                title: element.querySelector('h1')?.textContent,
                value: element.querySelector('.value')?.textContent,
            };
        }""")

        logger.info("My data extracted", data=data)
        return data
```

2. **Test the extractor** in `tests/test_my_extractor.py`

3. **Use it via API**:

```bash
curl -X POST http://localhost:8088/api/v1/extract \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user",
    "password": "pass",
    "include": ["profile", "my_data"]
  }'
```

---

## 🚀 Deployment

### Docker

**Multi-Stage Dockerfile:**
```dockerfile
# ============================================================
# Stage 1: Build
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# ============================================================
# Stage 2: Runtime
# ============================================================
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

WORKDIR /app

# Install only runtime dependencies
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app/src /app/src

# Create non-root user
RUN useradd -m -u 1000 automation && \
    chown -R automation:automation /app

# Create required directories
RUN mkdir -p /app/screenshots /app/sessions && \
    chown -R automation:automation /app/screenshots /app/sessions

USER automation

EXPOSE 8088

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import httpx; httpx.get('http://localhost:8088/api/v1/health/live')"

CMD ["python", "-m", "uvicorn", "automation_service.main:app", \
     "--host", "0.0.0.0", "--port", "8088"]
```

### Kubernetes

**Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: automation-service
  labels:
    app: automation-service
    version: v1
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: automation-service
  template:
    metadata:
      labels:
        app: automation-service
        version: v1
    spec:
      containers:
        - name: automation-service
          image: sda/automation-service:1.0.0
          ports:
            - containerPort: 8088
              name: http
          env:
            - name: ENVIRONMENT
              value: "production"
            - name: BROWSER_HEADLESS
              value: "true"
            - name: LOG_LEVEL
              value: "INFO"
          resources:
            requests:
              cpu: 500m
              memory: 2Gi
            limits:
              cpu: 2000m
              memory: 4Gi
          livenessProbe:
            httpGet:
              path: /api/v1/health/live
              port: 8088
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /api/v1/health/ready
              port: 8088
            initialDelaySeconds: 5
            periodSeconds: 10
          volumeMounts:
            - name: screenshots
              mountPath: /app/screenshots
      volumes:
        - name: screenshots
          emptyDir:
            sizeLimit: 1Gi
```

---

## 🧪 Testing Strategy

### Test Pyramid

```
           ┌──────────┐
          /    E2E     \         10% - Full browser tests
         ├──────────────┤
        /  Integration   \       20% - Service + browser mocks
       ├──────────────────┤
      /       Unit         \     70% - Extractor logic, utilities
     └──────────────────────┘
```

### Unit Tests

```python
# tests/test_extractors.py

import pytest
from automation_service.services.extractors import ExtractorRegistry

def test_extractor_registry_registration():
    """Test extractor self-registration."""
    extractors = ExtractorRegistry.list_extractors()
    assert "profile" in extractors
    assert "tasks" in extractors

@pytest.mark.asyncio
async def test_profile_extractor(mock_page):
    """Test profile extraction."""
    from automation_service.services.extractors.profile import ProfileExtractor

    await mock_page.set_content("""
        <h2>Juan Pérez</h2>
        <table>
            <tr><td>Usuario</td><td>jperez</td></tr>
            <tr><td>Correo electrónico</td><td>juan@email.com</td></tr>
        </table>
    """)

    extractor = ProfileExtractor()
    result = await extractor.extract(mock_page, "https://example.com")

    assert result["full_name"] == "Juan Pérez"
    assert result["username"] == "jperez"
    assert result["email"] == "juan@email.com"
```

### Test Coverage Goals

| Layer | Target Coverage |
|-------|-----------------|
| Extractors | > 80% |
| Browser Manager | > 75% |
| Services | > 70% |
| API Routes | > 60% |
| Overall | > 75% |

---

## 📚 Additional Resources

### Documentation

- [Playwright Documentation](https://playwright.dev/python/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Architecture Decision Records](./docs/ADR/)

### Related Services

| Service | Repository | Port | Communication |
|---------|------------|------|---------------|
| Identity Service | [link](#) | 8080 | Calls automation for profile import |
| Organization Service | [link](#) | 8081 | Calls automation for member sync |
| Activity Service | [link](#) | 8083 | Receives extracted progress data |

### Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12+ | Primary language |
| FastAPI | 0.109+ | Web framework |
| Playwright | 1.41+ | Browser automation |
| Pydantic | 2.5+ | Data validation |
| Structlog | 24.1+ | Structured logging |
| Uvicorn | 0.27+ | ASGI server |
| Pytest | 7.4+ | Testing framework |

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for details.

---

## 📄 License

MIT License - see [LICENSE](./LICENSE) for details.

---

## 🎓 Implementation Status

✅ **Production Ready** - Core functionality implemented and tested

**Completed:**
- ✅ Architecture design
- ✅ Browser management layer
- ✅ Extractor pattern implementation
- ✅ Profile & tasks extractors
- ✅ Combined extraction endpoint
- ✅ Session management
- ✅ Structured logging
- ✅ Error handling & retry logic
- ✅ Documentation

**In Progress:**
- 🚧 Redis session caching
- 🚧 Advanced specialties extraction
- 🚧 Performance optimization

**TODO:**
- ⬜ Distributed tracing (OpenTelemetry)
- ⬜ Metrics dashboard
- ⬜ Browser context pooling
- ⬜ Load testing

---

<div align="center">

**Built with ❤️ for intelligent automation and seamless integration**

[Report Bug](https://github.com/sda/automation-service/issues) · [Request Feature](https://github.com/sda/automation-service/issues)

</div>
