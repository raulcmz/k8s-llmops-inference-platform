import pytest
from fastapi.testclient import TestClient

from app.main import app, settings


@pytest.fixture
def client() -> TestClient:
    """HTTP client against the FastAPI app (no real network server)."""
    return TestClient(app)


@pytest.fixture
def backend_url() -> str:
    """Backend base URL currently loaded by the app settings."""
    return settings.ollama_base_url
