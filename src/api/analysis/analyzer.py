"""Public surface of the text analysis component.

Other components use only this module: the analysis defaults, the
``TextAnalyzer`` interface and the ``text_analyzer`` factory. The engine, the
pattern recognizers and the NLP engines behind it stay internal.
"""

import os
from typing import Optional, Protocol

from dotenv import load_dotenv

load_dotenv()


class AnalysisSettings:
    """The entity types, language and NLP engine the analysis uses by default."""

    DEFAULT_ENTITIES = [
        "PERSON",
        "LOCATION",
        "PHONE_NUMBER",
        "EMAIL",
        "ORGANIZATION",
        "IBAN",
        "DATE_TIME",
        "ADDRESS",
    ]
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "nl")
    DEFAULT_NLP_ENGINE = os.getenv("DEFAULT_NLP_ENGINE", "spacy").lower()


analysis_settings = AnalysisSettings()


class TextAnalyzer(Protocol):
    """Finds PII entities in a text and replaces them with their type."""

    def analyze_text(
        self, text: str, entities: list = ..., language: str = ...
    ) -> list:
        """Return the entities found, as dicts with type, text, span and score."""

    def anonymize_text(
        self, text: str, entities: Optional[list] = None, language: str = ...
    ) -> str:
        """Return the text with every entity found replaced by ``<TYPE>``."""


def text_analyzer(nlp_engine: Optional[str] = None) -> TextAnalyzer:
    """Return an analyzer on the given NLP engine, or on the default one."""
    # Imported here: the engine reads the defaults defined above.
    from src.api.analysis.engine import ModularTextAnalyzer

    return ModularTextAnalyzer(
        nlp_engine=nlp_engine or analysis_settings.DEFAULT_NLP_ENGINE
    )
