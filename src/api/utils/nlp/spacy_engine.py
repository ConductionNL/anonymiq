from typing import List, Optional

import spacy

from src.api.config import settings
from src.api.utils.nlp.base import NLPEngine


class SpacyEngine(NLPEngine):
    """Wrapper voor SpaCy NER-engine voor Nederlandse PII-detectie.

    Laadt een opgegeven SpaCy-model en voert entity extractie uit.
    """

    def __init__(self, model_name: str = settings.DEFAULT_SPACY_MODEL) -> None:
        self.model_name = model_name
        try:
            self.nlp: spacy.language.Language = spacy.load(model_name)
        except Exception:
            # Fallback: probeer model on-the-fly te installeren (handig voor staging)
            try:
                from spacy.cli import download as spacy_download

                spacy_download(model_name)
                self.nlp = spacy.load(model_name)
            except Exception as e:  # pragma: no cover
                raise RuntimeError(
                    f"SpaCy model '{model_name}' kon niet worden geladen/geïnstalleerd: {e}"
                )

    def analyze(self, text: str, entities: Optional[List] = None) -> list:
        """Voer analyse uit op de tekst met behulp van SpaCy.

        Args:
            text (str): de tekst die geanalyseerd moet worden.
            entities (list, optional): de entities om terug te geven in de results. Defaults to None.

        Returns:
            list: een lijst van dictionaries met de resultaten van de analyse.
        """
        return [
            _result(ent)
            for ent in self.nlp(text).ents
            if entities is None or ent.label_ in entities
        ]


def _result(ent: spacy.tokens.Span) -> dict:
    """Return a spaCy entity as a result dict; spaCy gives no score."""
    return {
        "entity_type": ent.label_,
        "start": ent.start_char,
        "end": ent.end_char,
        "score": "",
        "text": ent.text,
    }
