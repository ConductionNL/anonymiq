"""The text routes refuse a caller without valid HTTP Basic credentials.

/api/v1/analyze and /api/v1/anonymize take raw text that still carries
personal data, the same exposure as the document routes, so they sit behind
the same HTTP Basic dependency. The NLP engine is replaced by a stub, so
these tests need no spaCy model and no torch, and a request that passes
authentication gets a real 200 from the real handler.
"""

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routers import text_analysis
from tests.unit.conftest import VALID_AUTH

TEXT = "Jan de Vries woont in Utrecht."
TEXT_ROUTES = [
    ("POST", "/api/v1/analyze", {"json": {"text": TEXT}}),
    ("POST", "/api/v1/anonymize", {"json": {"text": TEXT}}),
]
ROUTE_IDS = [path for _, path, _ in TEXT_ROUTES]


class StubAnalyzer:
    """Stands in for ModularTextAnalyzer so no model has to load."""

    def __init__(self, nlp_engine: str | None = None) -> None:
        """Accept the engine name the handler passes."""
        self.nlp_engine = nlp_engine

    def analyze_text(self, text: str, entities: list, language: str) -> list[dict]:
        """Report one person at the start of the text."""
        return [
            {
                "entity_type": "PERSON",
                "text": "Jan de Vries",
                "start": 0,
                "end": 12,
                "score": 0.9,
            }
        ]

    def anonymize_text(self, text: str, entities: list, language: str) -> str:
        """Replace the one person."""
        return "<PERSON> woont in Utrecht."


@pytest.fixture(autouse=True)
def stub_analyzer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap the NLP engine for the stub in the text router."""
    monkeypatch.setattr(text_analysis, "ModularTextAnalyzer", StubAnalyzer)


def test_the_table_covers_every_text_route() -> None:
    """A text route added later must be added to this table too."""
    text_paths = {"/api/v1/analyze", "/api/v1/anonymize"}
    registered = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.endpoint.__module__ == text_analysis.__name__
        for method in route.methods
    }
    assert registered == {(m, p) for m, p, _ in TEXT_ROUTES}
    assert {p for _, p in registered} == text_paths


@pytest.mark.parametrize(("method", "path", "kwargs"), TEXT_ROUTES, ids=ROUTE_IDS)
def test_without_credentials_is_refused(
    client: TestClient, method: str, path: str, kwargs: dict
) -> None:
    """No Authorization header: 401 with a Basic challenge, and no text echoed."""
    response = client.request(method, path, **kwargs)
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Basic"
    assert TEXT not in response.text


@pytest.mark.parametrize(("method", "path", "kwargs"), TEXT_ROUTES, ids=ROUTE_IDS)
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


def test_analyze_with_credentials_succeeds(client: TestClient) -> None:
    """Correct credentials reach the handler and get its answer."""
    response = client.post("/api/v1/analyze", json={"text": TEXT}, auth=VALID_AUTH)
    assert response.status_code == 200
    assert response.json()["pii_entities"][0]["entity_type"] == "PERSON"


def test_anonymize_with_credentials_succeeds(client: TestClient) -> None:
    """Correct credentials reach the handler and get the anonymised text."""
    response = client.post("/api/v1/anonymize", json={"text": TEXT}, auth=VALID_AUTH)
    assert response.status_code == 200
    assert response.json()["anonymized_text"] == "<PERSON> woont in Utrecht."


def test_no_configured_password_refuses_everyone(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without BASIC_AUTH_PASSWORD the text routes fail closed too."""
    from src.api.config import settings

    monkeypatch.setattr(settings, "BASIC_AUTH_PASSWORD", "")
    for _, path, kwargs in TEXT_ROUTES:
        assert client.post(path, auth=("admin", ""), **kwargs).status_code == 401
        assert client.post(path, auth=VALID_AUTH, **kwargs).status_code == 401
