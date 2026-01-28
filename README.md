# SDA Automation Service

Web automation service for Club Virtual IASD using Python, FastAPI, and Playwright.

## Features

- **Login Automation**: Automated login to Club Virtual IASD
- **Session Management**: Save and reuse browser sessions
- **Data Extraction**: Extract user profiles, specialties, and activities
- **Screenshot Capture**: Take screenshots as proof of automation
- **REST API**: Full REST API for triggering automations
- **Docker Support**: Containerized with Playwright browsers

## Tech Stack

- **Python 3.11+**
- **FastAPI** - Modern async web framework
- **Playwright** - Browser automation
- **Pydantic** - Data validation
- **Structlog** - Structured logging
- **Ruff** - Fast Python linter
- **Black** - Code formatter
- **MyPy** - Static type checker

## Quick Start

### Prerequisites

- Python 3.11 or higher
- pip

### Installation

```bash
# Clone the repository
cd automation-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
make install-dev

# Copy environment file
cp .env.example .env
```

### Running Locally

```bash
# Start the service
make run

# Or with auto-reload
make run-reload
```

The API will be available at http://localhost:8080

### API Documentation

- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

## API Endpoints

### Health Check

```bash
# Health status
GET /api/v1/health

# Liveness probe
GET /api/v1/health/live

# Readiness probe
GET /api/v1/health/ready
```

### Authentication

```bash
# Login to Club Virtual
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password",
  "club_id": null,
  "save_session": true
}

# Logout
POST /api/v1/auth/logout?session_id=<session_id>
```

### Sessions

```bash
# Get session info
GET /api/v1/sessions/{session_id}

# Delete session
DELETE /api/v1/sessions/{session_id}
```

### Automation

```bash
# Extract specialties
GET /api/v1/sessions/{session_id}/specialties
```

## Configuration

Environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment (development/staging/production) | development |
| `PORT` | Server port | 8080 |
| `LOG_LEVEL` | Logging level | INFO |
| `BROWSER_HEADLESS` | Run browser in headless mode | true |
| `BROWSER_TIMEOUT` | Browser timeout in ms | 30000 |
| `SCREENSHOTS_ENABLED` | Enable screenshot capture | true |

## Development

### Code Quality

```bash
# Run linting
make lint

# Fix linting issues
make lint-fix

# Format code
make format

# Type checking
make type-check

# Run all quality checks
make quality
```

### Testing

```bash
# Run tests
make test

# Run tests with coverage
make test-cov
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install
pre-commit install --hook-type commit-msg

# Run manually
pre-commit run --all-files
```

## Docker

### Build

```bash
make docker-build
```

### Run

```bash
make docker-run
```

## Project Structure

```
automation-service/
├── src/
│   └── automation_service/
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes.py          # API endpoints
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py          # Configuration
│       │   ├── exceptions.py      # Custom exceptions
│       │   └── logging.py         # Logging setup
│       ├── models/
│       │   ├── __init__.py
│       │   └── schemas.py         # Pydantic models
│       ├── services/
│       │   ├── __init__.py
│       │   ├── browser.py         # Browser management
│       │   └── club_virtual.py    # Club Virtual automation
│       ├── utils/
│       │   └── __init__.py
│       ├── __init__.py
│       └── main.py                # Application entry point
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_health.py
├── scripts/
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── Dockerfile
├── Makefile
├── pyproject.toml
└── README.md
```

## License

MIT
