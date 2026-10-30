from fastapi.testclient import TestClient

from src.api.analysis.engine import ModularTextAnalyzer
from src.api.main import app


def test_analyze_text_person_and_email():
    """Test of de analyzer zowel PERSON als EMAIL entiteiten kan vinden in een voorbeeldzin."""
    analyzer = ModularTextAnalyzer()
    text = "Mijn naam is Mark Rutte en mijn email is test@example.com."
    entities = ["PERSON", "EMAIL"]
    results = analyzer.analyze_text(text, entities)
    # Check dat zowel PERSON als EMAIL gevonden worden
    assert any(
        ent["entity_type"] == "PERSON" and "Mark Rutte" in ent["text"]
        for ent in results
    )
    assert any(
        ent["entity_type"] == "EMAIL" and "test@example.com" in ent["text"]
        for ent in results
    )


def test_api_analyze_person_and_email():
    """Test of de API endpoint /analyze correct werkt voor PERSON en EMAIL entiteiten."""
    client = TestClient(app)
    payload = {
        "text": "Mijn naam is Mark Rutte en mijn email is test@example.com.",
        "entities": ["PERSON", "EMAIL"],
        "language": "nl",
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert any(
        ent["entity_type"] == "PERSON" and "Mark Rutte" in ent["text"]
        for ent in data["entities_found"]
    )
    assert any(
        ent["entity_type"] == "EMAIL" and "test@example.com" in ent["text"]
        for ent in data["entities_found"]
    )
