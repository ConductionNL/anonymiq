"""Every document route refuses a caller without valid HTTP Basic credentials.

Documents reach this service before redaction, so they carry personal data.
The health route stays public for the liveness and readiness probes.
"""

import uuid

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.api.main import app
from tests.unit.conftest import VALID_AUTH

FILE_ID = str(uuid.uuid4())
PDF = ("doc.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")

# (method, path, request kwargs): each request is well formed, so on code
# without authentication it reaches the handler and is NOT answered with 401.
DOCUMENT_ROUTES = [
    ("POST", "/api/v1/documents/upload", {"files": {"files": PDF}}),
    ("POST", "/api/v1/documents/deanonymize", {"files": {"file": PDF}}),
    ("GET", f"/api/v1/documents/{FILE_ID}/metadata", {}),
    (
        "POST",
        f"/api/v1/documents/{FILE_ID}/anonymize",
        {"json": {"pii_entities_to_anonymize": ["PERSON"]}},
    ),
    ("GET", f"/api/v1/documents/{FILE_ID}/download", {}),
]

ROUTE_IDS = [f"{m} {p.replace(FILE_ID, '{file_id}')}" for m, p, _ in DOCUMENT_ROUTES]


def test_the_table_covers_every_document_route() -> None:
    """A document route added later must be added to this table too."""
    registered = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute) and "/documents" in route.path
        for method in route.methods
    }
    covered = {(m, p.replace(FILE_ID, "{file_id}")) for m, p, _ in DOCUMENT_ROUTES}
    assert registered == covered


@pytest.mark.parametrize(("method", "path", "kwargs"), DOCUMENT_ROUTES, ids=ROUTE_IDS)
def test_without_credentials_is_refused(
    client: TestClient, method: str, path: str, kwargs: dict
) -> None:
    """No Authorization header: 401 with a Basic challenge."""
    response = client.request(method, path, **kwargs)
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Basic"


@pytest.mark.parametrize(("method", "path", "kwargs"), DOCUMENT_ROUTES, ids=ROUTE_IDS)
@pytest.mark.parametrize(
    "auth",
    [("unit-user", "wrong"), ("wrong", "unit-secret"), ("", "")],
    ids=["wrong-password", "wrong-username", "empty"],
)
def test_wrong_credentials_are_refused(
    client: TestClient, method: str, path: str, kwargs: dict, auth: tuple
) -> None:
    """Wrong credentials: 401."""
    response = client.request(method, path, auth=auth, **kwargs)
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "expected"),
    [
        # An upload without files fails validation, after authentication.
        ("POST", "/api/v1/documents/upload", {}, 422),
        ("POST", "/api/v1/documents/deanonymize", {}, 422),
        # An unknown document id reaches the handler and its own 404.
        ("GET", f"/api/v1/documents/{FILE_ID}/metadata", {}, 404),
        (
            "POST",
            f"/api/v1/documents/{FILE_ID}/anonymize",
            {"json": {"pii_entities_to_anonymize": ["PERSON"]}},
            404,
        ),
        ("GET", f"/api/v1/documents/{FILE_ID}/download", {}, 404),
    ],
    ids=ROUTE_IDS,
)
def test_correct_credentials_reach_the_handler(
    client: TestClient, method: str, path: str, kwargs: dict, expected: int
) -> None:
    """Correct credentials pass authentication and reach validation or the handler."""
    response = client.request(method, path, auth=VALID_AUTH, **kwargs)
    assert response.status_code == expected


def test_health_stays_public(client: TestClient) -> None:
    """The probes call /health without credentials."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"ping": "pong"}


def test_no_configured_password_refuses_everyone(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without BASIC_AUTH_PASSWORD the routes fail closed, even for an empty one."""
    from src.api.config import settings

    monkeypatch.setattr(settings, "BASIC_AUTH_PASSWORD", "")
    path = f"/api/v1/documents/{FILE_ID}/metadata"
    assert client.get(path, auth=("admin", "")).status_code == 401
    assert client.get(path, auth=VALID_AUTH).status_code == 401
