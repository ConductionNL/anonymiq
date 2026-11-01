"""Public surface of the text analysis component.

Other components use only this module: the analysis defaults and the
``text_analyzer`` factory. Each caller types the analyzer by the methods it
calls. The engine, the pattern recognizers and the NLP engines stay internal.
"""

import os
from typing import TYPE_CHECKING, Optional

from dotenv import load_dotenv

if TYPE_CHECKING:
    from src.api.analysis.engine import ModularTextAnalyzer

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


def text_analyzer(nlp_engine: Optional[str] = None) -> "ModularTextAnalyzer":
    """Return an analyzer on the given NLP engine, or on the default one."""
    # Imported here: the engine reads the defaults defined above.
    from src.api.analysis.engine import ModularTextAnalyzer

    return ModularTextAnalyzer(
        nlp_engine=nlp_engine or analysis_settings.DEFAULT_NLP_ENGINE
    )
