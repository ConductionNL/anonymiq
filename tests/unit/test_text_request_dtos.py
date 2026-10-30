"""Characterization tests for the text request DTOs and the entity settings."""

import pytest
from pydantic import ValidationError

from src.api.analysis.analyzer import analysis_settings
from src.api.config import settings
from src.api.dtos import AnalyzeTextRequest, AnonymizeTextRequest

REQUESTS = [AnalyzeTextRequest, AnonymizeTextRequest]
IDS = ["analyze", "anonymize"]


@pytest.mark.parametrize("cls", REQUESTS, ids=IDS)
def test_defaults_and_stripping(cls: type) -> None:
    request = cls(text="  Jan  ")
    assert request.text == "Jan"
    assert request.language == analysis_settings.DEFAULT_LANGUAGE
    assert request.entities is None
    assert request.nlp_engine is None


@pytest.mark.parametrize("cls", REQUESTS, ids=IDS)
@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"text": "   "}, "Value error, Text cannot be empty"),
        (
            {"text": "x", "language": "de"},
            "Value error, Unsupported language: de. Supported: nl, en",
        ),
        (
            {"text": "x", "entities": ["PERSON", "SHOE", "HAT"]},
            "Value error, Unsupported entities: SHOE, HAT. Supported: "
            + ", ".join(settings.SUPPORTED_PII_ENTITIES_TO_ANONYMIZE),
        ),
    ],
    ids=["text", "language", "entities"],
)
def test_validation_messages(cls: type, fields: dict, message: str) -> None:
    with pytest.raises(ValidationError) as info:
        cls(**fields)
    assert [e["msg"] for e in info.value.errors()] == [message]


@pytest.mark.parametrize("cls", REQUESTS, ids=IDS)
def test_valid_options_are_kept(cls: type) -> None:
    request = cls(text="x", language="en", entities=["EMAIL"], nlp_engine="spacy")
    assert (request.language, request.entities, request.nlp_engine) == (
        "en",
        ["EMAIL"],
        "spacy",
    )


def test_analyze_has_no_strategy() -> None:
    assert "anonymization_strategy" not in AnalyzeTextRequest.model_fields


@pytest.mark.parametrize("strategy", ["replace", "mask", "redact", "hash"])
def test_supported_strategies(strategy: str) -> None:
    assert AnonymizeTextRequest(text="x", anonymization_strategy=strategy)


def test_default_and_unknown_strategy() -> None:
    assert AnonymizeTextRequest(text="x").anonymization_strategy == "replace"
    with pytest.raises(ValidationError) as info:
        AnonymizeTextRequest(text="x", anonymization_strategy="shred")
    assert info.value.errors()[0]["msg"] == (
        "Value error, Unsupported strategy: shred. Supported: replace, mask, redact, hash"
    )


def test_the_entity_lists() -> None:
    expected = [
        "PERSON",
        "LOCATION",
        "PHONE_NUMBER",
        "EMAIL",
        "ORGANIZATION",
        "IBAN",
        "DATE_TIME",
        "ADDRESS",
    ]
    assert analysis_settings.DEFAULT_ENTITIES == expected
    assert settings.SUPPORTED_PII_ENTITIES_TO_ANONYMIZE == expected
    assert settings.SUPPORTED_PII_ENTITIES_TO_ANONYMIZE is not analysis_settings.DEFAULT_ENTITIES
