"""In-process fixtures for the unit tests.

These tests run the FastAPI app through TestClient, so they need no running
server, no spaCy model and no torch. The settings are read once, when
``src.api.config`` is imported, so the environment is set here, before any
test module imports the app.
"""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="anonymiq-unit-")

os.environ["BASIC_AUTH_USERNAME"] = "unit-user"
os.environ["BASIC_AUTH_PASSWORD"] = "unit-secret"
os.environ["ALLOWED_ORIGINS"] = "https://allowed.example"
os.environ["DATA_DIR"] = os.path.join(_TMP, "data")
os.environ["LOG_DIR"] = os.path.join(_TMP, "logs")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'unit.db')}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402

VALID_AUTH = ("unit-user", "unit-secret")


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Return a TestClient on the real app, with the real middleware stack."""
    return TestClient(app)
