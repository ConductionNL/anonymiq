import logging
from typing import List, Optional

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider

from src.api.config import settings
from src.api.utils.nlp.loader import load_nlp_engine
from src.api.utils.patterns import (
    CaseNumberRecognizer,
    DutchBSNRecognizer,
    DutchDateRecognizer,
    DutchDriversLicenseRecognizer,
    DutchIBANRecognizer,
    DutchPassportIdRecognizer,
    DutchPhoneNumberRecognizer,
    EmailRecognizer,
)


class ModularTextAnalyzer:
    """Modulaire analyzer-klasse voor Nederlandse tekst.

    Deze klasse combineert een configureerbare NLP-engine (zoals SpaCy of een
    HuggingFace transformers-model) met pattern recognizers voor het detecteren
    en anonimiseren van PII (zoals namen, telefoonnummers, e-mails, IBAN) in
    Nederlandse tekst. De workflow bestaat uit:

    1. Uitvoeren van NER via de gekozen NLP-engine.
    2. Toepassen van pattern recognizers (zoals custom regex voor IBAN, telefoon).
    3. Combineren en dedupliceren van resultaten.

    De klasse is uitbreidbaar met nieuwe modellen en recognizers en vormt de kern
    van de modulaire architectuur van deze service.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        nlp_engine: str = settings.DEFAULT_NLP_ENGINE,
    ) -> None:
        if model_name is None:
            model_name = (
                settings.DEFAULT_SPACY_MODEL
                if nlp_engine == "spacy"
                else settings.DEFAULT_TRANSFORMERS_MODEL
            )
        self.nlp_engine = load_nlp_engine(
            config_dict={"nlp_engine": nlp_engine, "model_name": model_name}
        )
        self.analyzer = _pattern_analyzer()

    def analyze_text(
        self,
        text: str,
        entities: list = settings.DEFAULT_ENTITIES,
        language: str = settings.DEFAULT_LANGUAGE,
    ) -> list:
        """Analyseer tekst met behulp van de NLP-engine en pattern recognizers.

        Args:
            text (str): de tekst om te analyseren.
            entities (list, optional): entities om te analyseren. Defaults to DEFAULT_ENTITIES.
            language (str, optional): taal om in te analyseren. Defaults to DEFAULT_LANGUAGE.

        Returns:
            list: lijst van gedetecteerde entiteiten met hun start- en eindposities, type en score.
        """
        logging.debug(f"Analyzing text with {entities=} and {language=}")

        # Analyze with NLP engine (supports entity filtering)
        nlp_results = self.nlp_engine.analyze(text, entities, language)
        print(f"nlp_results: {nlp_results}")

        all_results = nlp_results + self._pattern_results(text, language)
        if entities and entities != settings.DEFAULT_ENTITIES:
            all_results = [r for r in all_results if r["entity_type"] in entities]
        return _distinct_spans(all_results)

    def _pattern_results(self, text: str, language: str) -> list[dict]:
        """Run every pattern recognizer and return the results as dicts.

        A failing pattern analysis is logged and gives no results.
        """
        try:
            pattern_results: List[RecognizerResult] = self.analyzer.analyze(
                text=text,
                entities=None,
                language=language,  # Don't filter here
            )
            print(f"pattern_results: {pattern_results}")
        except Exception as e:
            logging.warning(f"Pattern analysis failed: {e}")
            return []
        return [_result_dict(text, r) for r in pattern_results]

    def anonymize_text(
        self,
        text: str,
        entities: Optional[List] = None,
        language: str = settings.DEFAULT_LANGUAGE,
    ) -> str:
        """Function to anonymize text by replacing detected entities with placeholders.

        Args:
            text (str): the text to anonymize.
            entities (list, optional): the entities to anonymize. Defaults to None.
            language (str, optional): the language to anonymize in. Defaults to DEFAULT_LANGUAGE.

        Returns:
            str: the anonymized text with placeholders for detected entities.
        """
        results = self.analyze_text(text, entities, language)  # type: ignore
        return _replace_with_types(text, results)


# Pattern recognizers registered on presidio's AnalyzerEngine, in this order.
_RECOGNIZERS = (
    DutchPhoneNumberRecognizer,
    DutchIBANRecognizer,
    DutchBSNRecognizer,
    DutchDateRecognizer,
    EmailRecognizer,
    DutchPassportIdRecognizer,
    DutchDriversLicenseRecognizer,
    CaseNumberRecognizer,
)


def _pattern_analyzer() -> AnalyzerEngine:
    """Return presidio's AnalyzerEngine with the Dutch pattern recognizers.

    Presidio always uses SpaCy for pattern recognizers, regardless of the NLP
    engine chosen for named entities.
    """
    spacy_config = _presidio_spacy_config()
    registry = _pattern_registry()
    analyzer = AnalyzerEngine(
        nlp_engine=NlpEngineProvider(nlp_configuration=spacy_config).create_engine(),
        registry=registry,
        supported_languages=registry.supported_languages,
    )
    logging.debug(
        f"ModularTextAnalyzer is initialized with {len(_RECOGNIZERS)} recognizers, {spacy_config=}"
    )
    return analyzer


def _presidio_spacy_config() -> dict:
    """Return presidio's NLP configuration: the default spaCy model."""
    return {
        "nlp_engine_name": "spacy",  # Presidio only supports spacy
        "models": [
            {
                "lang_code": settings.DEFAULT_LANGUAGE,
                "model_name": settings.DEFAULT_SPACY_MODEL,
            }
        ],
    }


def _pattern_registry() -> RecognizerRegistry:
    """Return a registry for the default language with every pattern recognizer."""
    registry = RecognizerRegistry()
    registry.supported_languages = [settings.DEFAULT_LANGUAGE]
    for recognizer in _RECOGNIZERS:
        registry.add_recognizer(recognizer=recognizer())
    return registry


def _result_dict(text: str, result: RecognizerResult) -> dict:
    """Return a presidio result as a dict with the matched text."""
    return {
        "entity_type": result.entity_type,
        "start": result.start,
        "end": result.end,
        "score": result.score,
        "text": text[result.start : result.end],
    }


def _distinct_spans(results: list[dict]) -> list[dict]:
    """Keep the first result of each (start, end, entity_type)."""
    unique: dict[tuple, dict] = {}
    for r in results:
        unique.setdefault((r["start"], r["end"], r["entity_type"]), r)
    return list(unique.values())


def _replace_with_types(text: str, results: list[dict]) -> str:
    """Replace every result's span with ``<ENTITY_TYPE>``, from the back."""
    for ent in sorted(results, key=lambda x: x["start"], reverse=True):
        text = text[: ent["start"]] + f"<{ent['entity_type']}>" + text[ent["end"] :]
    return text
