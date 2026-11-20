"""The NLP models the analysis loads when a caller names none."""

import os

from dotenv import load_dotenv

load_dotenv()


class ModelSettings:
    """The spaCy and transformers models loaded by default."""

    DEFAULT_SPACY_MODEL = os.getenv("DEFAULT_SPACY_MODEL", "nl_core_news_md")
    DEFAULT_TRANSFORMERS_MODEL = os.getenv(
        "DEFAULT_TRANSFORMERS_MODEL", "pdelobelle/robbert-v2-dutch-base"
    )


model_settings = ModelSettings()
