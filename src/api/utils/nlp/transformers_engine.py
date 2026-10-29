from typing import List, Optional

from transformers import pipeline

from src.api.utils.nlp.base import NLPEngine


class TransformersEngine(NLPEngine):
    """Wrapper voor een HuggingFace Transformers NER-model voor Nederlandse PII-detectie.

    Ondersteunt elk model dat compatibel is met de transformers pipeline API.
    """

    def __init__(self, model_name: str = "GroNLP/bert-base-dutch-cased") -> None:
        """Initialiseer de Transformers-engine met een specifiek model.

        Args:
            model_name (str): Naam van het model dat gebruikt moet worden.
                Standaard is "GroNLP/bert-base-dutch-cased".
        """
        self.model_name = model_name
        # The typed overloads of pipeline() omit task-specific kwargs such as
        # aggregation_strategy, which the token-classification pipeline accepts.
        self.ner_pipeline = pipeline(  # type: ignore[call-overload]
            "ner", model=model_name, aggregation_strategy="simple"
        )

    def analyze(
        self, text: str, entities: Optional[List] = None, language: str = "nl"
    ) -> list:
        """Voert NER-analyse uit op de tekst met het gekozen transformers-model.

        Args:
            text (str): De tekst om te analyseren.
            entities (list, optional): Lijst van entiteitstypen om te filteren. Defaults to None (alle).
            language (str, optional): Taalcode (standaard 'nl').

        Returns:
            list: Lijst van gevonden entiteiten met type, start, end, score en tekst.
        """
        results = []
        for ent in self.ner_pipeline(text):
            # Mapping van model-labels naar Presidio/standaard labels kan hier uitgebreid worden
            entity_type = ent.get("entity_group", ent.get("entity", ""))
            if entities is None or entity_type in entities:
                results.append(
                    {
                        "entity_type": entity_type,
                        "start": ent["start"],
                        "end": ent["end"],
                        "score": ent["score"],
                        "text": ent["word"]
                        if "word" in ent
                        else text[ent["start"] : ent["end"]],
                    }
                )
        return results
