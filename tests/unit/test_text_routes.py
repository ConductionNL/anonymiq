"""Characterization tests for POST /api/v1/analyze and /api/v1/anonymize.

The text analyzer is replaced by a fake, so the routes run without a spaCy
model; the tests pin the request handling, the response shape and the errors.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.analysis.analyzer import analysis_settings
from src.api import text_routes as text_analysis
from src.api.main import app
from tests.unit.conftest import VALID_AUTH

TEXT = "Jan Jansen mailt jan@example.nl"
RESULTS = [
    {
        "entity_type": "PERSON",
        "text": "Jan Jansen",
        "start": 0,
        "end": 10,
        "score": 0.85,
    },
    {
        "entity_type": "EMAIL",
        "text": "jan@example.nl",
        "start": 17,
        "end": 31,
        "score": "",
    },
]


class FakeAnalyzer:
    built: list[str] = []
    calls: list[tuple] = []
    fail: Exception | None = None

    def __init__(self, nlp_engine: str) -> None:
        if FakeAnalyzer.fail:
            raise FakeAnalyzer.fail
        FakeAnalyzer.built.append(nlp_engine)

    def analyze_text(self, text: str, entities: list, language: str) -> list:
        FakeAnalyzer.calls.append(("analyze", text, entities, language))
        return [dict(r) for r in RESULTS]

    def anonymize_text(self, text: str, entities: list, language: str) -> str:
        FakeAnalyzer.calls.append(("anonymize", text, entities, language))
        return "<PERSON> mailt <EMAIL>"


@pytest.fixture
def client() -> TestClient:
    """The shared client, sending valid HTTP Basic credentials: the routes need them."""
    authed = TestClient(app)
    authed.auth = VALID_AUTH
    return authed


@pytest.fixture(autouse=True)
def fake(monkeypatch: pytest.MonkeyPatch) -> type[FakeAnalyzer]:
    FakeAnalyzer.built, FakeAnalyzer.calls, FakeAnalyzer.fail = [], [], None
    monkeypatch.setattr(text_analysis, "text_analyzer", FakeAnalyzer)
    return FakeAnalyzer


EXPECTED_ENTITIES = [
    {
        "entity_type": "PERSON",
        "text": "Jan Jansen",
        "start": 0,
        "end": 10,
        "score": 0.85,
    },
    {
        "entity_type": "EMAIL",
        "text": "jan@example.nl",
        "start": 17,
        "end": 31,
        "score": None,
    },
]


def test_analyze_with_defaults(client: TestClient, fake: type[FakeAnalyzer]) -> None:
    response = client.post("/api/v1/analyze", json={"text": f"  {TEXT}  "})
    assert response.status_code == 200
    body = response.json()
    assert body["pii_entities"] == EXPECTED_ENTITIES
    assert body["text_length"] == len(TEXT)
    assert body["nlp_engine_used"] == analysis_settings.DEFAULT_NLP_ENGINE
    assert isinstance(body["processing_time_ms"], int)
    assert fake.built == [analysis_settings.DEFAULT_NLP_ENGINE]
    assert fake.calls == [
        ("analyze", TEXT, analysis_settings.DEFAULT_ENTITIES, analysis_settings.DEFAULT_LANGUAGE)
    ]


def test_analyze_with_options(client: TestClient, fake: type[FakeAnalyzer]) -> None:
    response = client.post(
        "/api/v1/analyze",
        json={
            "text": TEXT,
            "language": "en",
            "entities": ["EMAIL"],
            "nlp_engine": "transformers",
        },
    )
    assert response.json()["nlp_engine_used"] == "transformers"
    assert fake.built == ["transformers"]
    assert fake.calls == [("analyze", TEXT, ["EMAIL"], "en")]


def test_anonymize_with_defaults(client: TestClient, fake: type[FakeAnalyzer]) -> None:
    response = client.post("/api/v1/anonymize", json={"text": TEXT})
    assert response.status_code == 200
    body = response.json()
    assert body["original_text"] == TEXT
    assert body["anonymized_text"] == "<PERSON> mailt <EMAIL>"
    assert body["entities_found"] == EXPECTED_ENTITIES
    assert body["text_length"] == len(TEXT)
    assert body["nlp_engine_used"] == analysis_settings.DEFAULT_NLP_ENGINE
    assert body["anonymization_strategy"] == "replace"
    assert isinstance(body["processing_time_ms"], int)
    args = (TEXT, analysis_settings.DEFAULT_ENTITIES, analysis_settings.DEFAULT_LANGUAGE)
    assert fake.calls == [("analyze", *args), ("anonymize", *args)]


def test_anonymize_with_options(client: TestClient, fake: type[FakeAnalyzer]) -> None:
    response = client.post(
        "/api/v1/anonymize",
        json={
            "text": TEXT,
            "language": "en",
            "entities": ["PERSON"],
            "nlp_engine": "transformers",
            "anonymization_strategy": "mask",
        },
    )
    body = response.json()
    assert body["anonymization_strategy"] == "mask"
    assert body["nlp_engine_used"] == "transformers"
    assert fake.calls == [
        ("analyze", TEXT, ["PERSON"], "en"),
        ("anonymize", TEXT, ["PERSON"], "en"),
    ]


@pytest.mark.parametrize(
    ("path", "label"),
    [("/api/v1/analyze", "Text analysis"), ("/api/v1/anonymize", "Text anonymization")],
)
def test_an_analyzer_error_is_a_500(
    client: TestClient, fake: type[FakeAnalyzer], path: str, label: str
) -> None:
    fake.fail = RuntimeError("no model")
    response = client.post(path, json={"text": TEXT})
    assert response.status_code == 500
    assert response.json()["detail"] == f"{label} failed: no model"


@pytest.mark.parametrize("path", ["/api/v1/analyze", "/api/v1/anonymize"])
@pytest.mark.parametrize(
    "payload",
    [
        {"text": "   "},
        {"text": TEXT, "language": "de"},
        {"text": TEXT, "entities": ["SHOE_SIZE"]},
    ],
    ids=["empty-text", "language", "entity"],
)
def test_invalid_requests_are_a_422(
    client: TestClient, path: str, payload: dict
) -> None:
    assert client.post(path, json=payload).status_code == 422


def test_an_unknown_strategy_is_a_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/anonymize", json={"text": TEXT, "anonymization_strategy": "shred"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0.5, 0.5), ("", None), ("   ", None), (None, None), ("0.7", "0.7")],
)
def test_score_normalisation(score: object, expected: object) -> None:
    result = {"entity_type": "PERSON", "text": "Jan", "start": 0, "end": 3}
    if score is not None:
        result["score"] = score
    [entity] = text_analysis.create_pii_entities_from_results([result])
    assert entity.score == expected
