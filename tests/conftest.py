"""Pytest fixtures for automation service tests."""

import pytest
from fastapi.testclient import TestClient

from automation_service.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_credentials() -> dict[str, str]:
    """Mock credentials for testing."""
    return {
        "username": "testuser",
        "password": "testpassword",
    }
