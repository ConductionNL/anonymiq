"""Characterization tests for CaseNumberRecognizer."""

import pytest

from src.api.utils.patterns import CaseNumberRecognizer

EXPECTED_PATTERNS = [
    ("CASE_Z", r"\bZ[-\/]?\d{4}[-\/]?\d{4,6}\b", 0.55),
    ("CASE_PREFIXED", r"\b(?:WOO|BEZWAAR|INT|VTH|WP)[-\/]?\d{4}[-\/]?\d{3,6}\b", 0.6),
    ("CASE_YEAR_NUMBER", r"\b\d{4}[-\/]\d{4,6}\b", 0.45),
    ("CASE_BAG_ID", r"\b\d{16}\b", 0.4),
    (
        "CASE_UUID",
        r"(?i)\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b",
        0.6,
    ),
    ("CASE_C_CIVIL", r"\bC\/\d{2}\/\d{5,8}\b", 0.55),
    ("CASE_AWB", r"\bAWB\s?\d{2}\/\d{3,6}\b", 0.6),
    ("CASE_HR", r"\bHR\s?\d{2}\/\d{5}\b", 0.6),
    ("CASE_GERECHTSHOF", r"\b200\.\d{5}\b", 0.55),
    ("CASE_OM", r"\b\d{2}\/\d{6}-\d{2}\b", 0.6),
    ("CASE_COURT_GENERIC", r"\b[A-Z]{4,5}\s?\d{2}\/\d{3,6}\b", 0.55),
]


def test_patterns_entity_and_language_are_unchanged():
    recognizer = CaseNumberRecognizer()

    assert recognizer.supported_entities == ["CASE_NO"]
    assert recognizer.supported_language == "nl"
    assert [(p.name, p.regex, p.score) for p in recognizer.patterns] == (
        EXPECTED_PATTERNS
    )


def test_context_and_language_are_passed_on():
    recognizer = CaseNumberRecognizer(context=["zaak"], supported_language="en")

    assert recognizer.context == ["zaak"]
    assert recognizer.supported_language == "en"


def test_each_instance_gets_its_own_pattern_objects():
    first, second = CaseNumberRecognizer(), CaseNumberRecognizer()

    assert first.patterns is not second.patterns
    assert first.patterns[0] is not second.patterns[0]


@pytest.mark.parametrize(
    "text",
    ["Z-2024-123456", "WOO-2024-001", "C/13/123456", "AWB 21/12345", "08/123456-89"],
)
def test_recognizes_case_numbers(text):
    results = CaseNumberRecognizer().analyze(f"Zie {text} graag.", ["CASE_NO"])

    assert any(r.entity_type == "CASE_NO" for r in results)
