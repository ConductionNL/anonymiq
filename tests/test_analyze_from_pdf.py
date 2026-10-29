import os
from pathlib import Path

import pytest
import pymupdf  # alias: fitz
import requests


def get_base_url() -> str:
    # ANONYMIQ_BASE_URL is canonical; OPENANONYMISER_BASE_URL is still read
    # because it is what every README, CI job and shell profile written before
    # the rename sets. Dropping it would not error — os.getenv() would fall
    # through to the localhost default and the suite would quietly test a
    # different target than the operator asked for. Remove the legacy name
    # once nothing sets it.
    return os.getenv(
        "ANONYMIQ_BASE_URL",
        os.getenv("OPENANONYMISER_BASE_URL", "http://localhost:8080"),
    )


def extract_text_from_pdf(pdf_path: Path) -> str:
    doc = pymupdf.open(pdf_path)  # type: ignore[attr-defined]
    try:
        texts: list[str] = []
        for page in doc:
            texts.append(page.get_text())
        return "\n".join(texts).strip()
    finally:
        doc.close()


@pytest.mark.integration
def test_analyze_text_extracted_from_mock_pdf() -> None:
    base = get_base_url()
    pdf_path = Path("tests") / "mock_persoonsgegevens.pdf"

    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found at {pdf_path}")

    text = extract_text_from_pdf(pdf_path)
    # Guard: if extraction fails or returns empty, skip to avoid false negatives
    if not text or len(text.split()) < 3:
        pytest.skip("Extracted PDF text is empty or too short for meaningful analysis")

    payload = {
        "text": text,
        "language": "nl",
        # Laat de engine en entities defaults bepalen; zo pakken we zowel NER als patterns
    }
    resp = requests.post(f"{base}/api/v1/analyze", json=payload, timeout=120)

    assert resp.status_code in (200, 201), f"HTTP {resp.status_code}: {resp.text[:500]}"
    data = resp.json()

    assert isinstance(data, dict)
    assert "pii_entities" in data
    assert "text_length" in data
    assert isinstance(data["pii_entities"], list)
    # Verwacht minstens 1 entiteit; PDF bevat voorbeeld-PII
    assert len(data["pii_entities"]) >= 1

    # Basisvalidaties voor entiteiten
    for ent in data["pii_entities"]:
        assert "entity_type" in ent
        assert "text" in ent
        assert "start" in ent and "end" in ent
        assert 0 <= ent["start"] < ent["end"] <= data["text_length"]
