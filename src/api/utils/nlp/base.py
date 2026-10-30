from abc import ABC, abstractmethod
from typing import List, Optional


class NLPEngine(ABC):
    """Abstracte basisinterface voor NLP-engines in het systeem.

    Alle concrete NLP-engines (zoals SpaCy of Transformers) moeten deze interface implementeren.
    """

    @abstractmethod
    def analyze(self, text: str, entities: Optional[List] = None) -> list:
        """Analyseer tekst en retourneer een lijst van gevonden entiteiten.

        Args:
            text (str): De te analyseren tekst.
            entities (list, optional): Optionele lijst van te detecteren entiteiten. Defaults to None.

        Returns:
            list: Lijst van entiteiten (dicts of Presidio RecognizerResult).
        """
        pass
