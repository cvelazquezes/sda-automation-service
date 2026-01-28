# =============================================================================
# Makefile - Automation Service
# =============================================================================

.PHONY: help install install-dev run test lint format type-check clean docker-build docker-run

# Default target
help:
	@echo "Available commands:"
	@echo "  make install      - Install production dependencies"
	@echo "  make install-dev  - Install development dependencies"
	@echo "  make run          - Run the service locally"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linting"
	@echo "  make format       - Format code"
	@echo "  make type-check   - Run type checking"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run Docker container"

# =============================================================================
# Development
# =============================================================================

install:
	pip install -e .
	playwright install chromium

install-dev:
	pip install -e ".[dev]"
	playwright install chromium
	pre-commit install
	pre-commit install --hook-type commit-msg

run:
	python -m automation_service.main

run-reload:
	uvicorn automation_service.main:app --reload --host 0.0.0.0 --port 8080

# =============================================================================
# Testing
# =============================================================================

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src/automation_service --cov-report=html --cov-report=term-missing

# =============================================================================
# Code Quality
# =============================================================================

lint:
	ruff check src/ tests/

lint-fix:
	ruff check src/ tests/ --fix

format:
	black src/ tests/

format-check:
	black src/ tests/ --check

type-check:
	mypy src/

quality: lint format-check type-check

# =============================================================================
# Docker
# =============================================================================

docker-build:
	docker build -t sda-automation-service:latest .

docker-run:
	docker run -p 8080:8080 \
		-e ENVIRONMENT=development \
		-e BROWSER_HEADLESS=true \
		-v $(PWD)/sessions:/app/sessions \
		-v $(PWD)/screenshots:/app/screenshots \
		sda-automation-service:latest

docker-shell:
	docker run -it --entrypoint /bin/bash sda-automation-service:latest

# =============================================================================
# Cleanup
# =============================================================================

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-sessions:
	rm -rf sessions/*
	rm -rf screenshots/*
