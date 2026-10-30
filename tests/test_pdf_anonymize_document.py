"""Characterization tests for pdf_xmp.analyze_and_anonymize_document."""

from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pymupdf
import pytest

from src.api.config import settings
from src.api.utils import pdf_xmp


class FakeAnalyzer:
    """Stands in for the NLP analyzer and records what it was asked."""

    calls: ClassVar[list[str]] = []
    result: ClassVar[list[dict]] = []

    def analyze_text(self, text: str) -> list[dict]:
        FakeAnalyzer.calls.append(text)
        return [dict(e) for e in FakeAnalyzer.result]


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    FakeAnalyzer.calls = []
    FakeAnalyzer.result = []
    monkeypatch.setattr(pdf_xmp, "text_analyzer", FakeAnalyzer)
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path / "data"))


def make_pdf(path: Path, text: str) -> str:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return str(path)


def order(file_id: str, *types: str) -> pdf_xmp.AnonymizationOrder:
    return pdf_xmp.AnonymizationOrder(file_id=file_id, entity_types=list(types), key="k")


def entity(entity_type: str, text: str, start: int, end: int) -> dict:
    return {
        "entity_type": entity_type,
        "text": text,
        "start": start,
        "end": end,
        "score": 0.85,
    }


def test_uses_cached_entities_and_filters_the_requested_types(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", "Jan Jansen mailt jan@example.com")
    cached = [
        entity("PERSON", "Jan Jansen", 0, 10),
        entity("EMAIL", "jan@example.com", 17, 32),
    ]
    doc = SimpleNamespace(source_path=source, _entities=cached)

    result = pdf_xmp.analyze_and_anonymize_document(doc, order("f1", "PERSON"))

    assert FakeAnalyzer.calls == []
    assert result.selected_entities == [
        {
            "entity_type": "PERSON",
            "text": "Jan Jansen",
            "start": "0",
            "end": "10",
            "score": "0.85",
        }
    ]
    assert cached[0]["start"] == 0, "the cached entity itself is not changed"
    assert result.output_path == Path(settings.DATA_DIR) / "temp/anonymized/f1.pdf"
    assert result.output_path.exists()
    assert result.status_text == "success (1 entities processed)"


def test_analyzes_the_text_when_nothing_is_cached(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", "Jan Jansen woont hier")
    FakeAnalyzer.result = [entity("PERSON", "Jan Jansen", 0, 10)]
    doc = SimpleNamespace(source_path=source)

    result = pdf_xmp.analyze_and_anonymize_document(doc, order("f2", "PERSON"))

    assert len(FakeAnalyzer.calls) == 1
    assert "Jan Jansen" in FakeAnalyzer.calls[0]
    assert doc._entities == FakeAnalyzer.result
    assert result.status_text == "success (1 entities processed)"


def test_reports_more_occurrences_than_unique_entities(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", "Jan Jansen en nog eens Jan Jansen")
    doc = SimpleNamespace(
        source_path=source, _entities=[entity("PERSON", "Jan Jansen", 0, 10)]
    )

    result = pdf_xmp.analyze_and_anonymize_document(doc, order("f3", "PERSON"))

    assert result.status_text == "success (2 entities processed)"


def test_an_unreadable_source_gives_no_entities_and_fails(tmp_path):
    doc = SimpleNamespace(source_path=str(tmp_path / "missing.pdf"))

    result = pdf_xmp.analyze_and_anonymize_document(doc, order("f4", "PERSON"))

    assert FakeAnalyzer.calls == []
    assert doc._entities == []
    assert result.selected_entities == []
    assert result.status_text == (
        f"failed: Source file {tmp_path / 'missing.pdf'} not found"
    )


def test_an_empty_output_fails(monkeypatch, tmp_path):
    source = make_pdf(tmp_path / "in.pdf", "tekst")
    monkeypatch.setattr(pdf_xmp, "anonymize_pdf", lambda *args: [])
    doc = SimpleNamespace(source_path=source, _entities=[])

    result = pdf_xmp.analyze_and_anonymize_document(doc, order("f5", "PERSON"))

    assert result.status_text == (
        "failed: Anonymization failed to produce valid output file"
    )


def test_an_unexpected_error_fails_with_its_message(monkeypatch, tmp_path):
    source = make_pdf(tmp_path / "in.pdf", "tekst")

    def broken(*args):
        raise RuntimeError("pdf engine crashed")

    monkeypatch.setattr(pdf_xmp, "anonymize_pdf", broken)
    doc = SimpleNamespace(source_path=source, _entities=[entity("PERSON", "x", 0, 1)])

    result = pdf_xmp.analyze_and_anonymize_document(doc, order("f6", "PERSON"))

    assert result.status_text == "failed: pdf engine crashed"
    assert result.output_path == Path(settings.DATA_DIR) / "temp/anonymized/f6.pdf"
