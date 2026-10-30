"""Characterization tests for ModularTextAnalyzer without a spaCy model.

The NLP engine, presidio's spaCy engine and the AnalyzerEngine are replaced by
fakes, so these tests pin how the analyzer is assembled and how it combines,
filters, deduplicates and replaces results.
"""

from dataclasses import dataclass

import pytest

from src.api.analysis.analyzer import analysis_settings as settings
from src.api.analysis import engine as ta
from src.api.analysis import patterns


@dataclass
class Hit:
    entity_type: str
    start: int
    end: int
    score: float


class FakeNlp:
    def __init__(self, results: list[dict]) -> None:
        self.results = results
        self.calls: list[tuple] = []

    def analyze(self, text: str, entities: list) -> list:
        self.calls.append((text, entities))
        return list(self.results)


class FakePatterns:
    def __init__(self, hits: list[Hit] | Exception) -> None:
        self.hits = hits
        self.calls: list[dict] = []

    def analyze(self, **kwargs: object) -> list[Hit]:
        self.calls.append(kwargs)
        if isinstance(self.hits, Exception):
            raise self.hits
        return self.hits


def analyzer(nlp: list[dict], hits: list[Hit] | Exception) -> ta.ModularTextAnalyzer:
    obj = ta.ModularTextAnalyzer.__new__(ta.ModularTextAnalyzer)
    obj.nlp_engine = FakeNlp(nlp)  # type: ignore[assignment]
    obj.analyzer = FakePatterns(hits)  # type: ignore[assignment]
    return obj


TEXT = "Jan Jansen mailt jan@example.nl"
PERSON = {
    "entity_type": "PERSON",
    "start": 0,
    "end": 10,
    "score": 0.85,
    "text": "Jan Jansen",
}
EMAIL_HIT = Hit("EMAIL", 17, 31, 0.6)
EMAIL = {
    "entity_type": "EMAIL",
    "start": 17,
    "end": 31,
    "score": 0.6,
    "text": "jan@example.nl",
}


def test_nlp_and_pattern_results_are_combined() -> None:
    a = analyzer([PERSON], [EMAIL_HIT])
    assert a.analyze_text(TEXT) == [PERSON, EMAIL]
    assert a.nlp_engine.calls == [(TEXT, settings.DEFAULT_ENTITIES)]
    assert a.analyzer.calls == [
        {"text": TEXT, "entities": None, "language": settings.DEFAULT_LANGUAGE}
    ]


def test_duplicate_spans_of_one_type_are_dropped() -> None:
    a = analyzer(
        [PERSON, dict(PERSON, score=0.5)], [Hit("PERSON", 0, 10, 0.3), EMAIL_HIT]
    )
    assert a.analyze_text(TEXT) == [PERSON, EMAIL]


def test_requested_entities_filter_the_combined_results() -> None:
    a = analyzer([PERSON], [EMAIL_HIT])
    assert a.analyze_text(TEXT, ["EMAIL"], "en") == [EMAIL]
    assert a.nlp_engine.calls[0][1:] == (["EMAIL"],)
    assert a.analyzer.calls[0]["language"] == "en"


@pytest.mark.parametrize("entities", [[], settings.DEFAULT_ENTITIES])
def test_empty_or_default_entities_do_not_filter(entities: list) -> None:
    other = {"entity_type": "BSN", "start": 0, "end": 3, "score": 1, "text": "Jan"}
    a = analyzer([other], [EMAIL_HIT])
    assert a.analyze_text(TEXT, entities) == [other, EMAIL]


def test_a_failing_pattern_analysis_is_skipped() -> None:
    a = analyzer([PERSON], RuntimeError("no model"))
    assert a.analyze_text(TEXT) == [PERSON]


def test_anonymize_replaces_every_entity_with_its_type() -> None:
    a = analyzer([PERSON], [EMAIL_HIT])
    assert a.anonymize_text(TEXT) == "<PERSON> mailt <EMAIL>"
    assert a.nlp_engine.calls[0][1:] == (None,)


def test_anonymize_passes_entities_and_language() -> None:
    a = analyzer([PERSON], [EMAIL_HIT])
    assert a.anonymize_text(TEXT, ["PERSON"], "en") == "<PERSON> mailt jan@example.nl"
    assert a.nlp_engine.calls[0][1:] == (["PERSON"],)


class Recorder:
    """Stands in for a presidio class and records how it was built."""

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    def create_engine(self) -> str:
        return "presidio-spacy-engine"


@pytest.fixture
def built(monkeypatch: pytest.MonkeyPatch) -> dict:
    seen: dict = {}

    def fake_loader(config_dict: dict) -> str:
        seen["config_dict"] = config_dict
        return "nlp-engine"

    monkeypatch.setattr(ta, "load_nlp_engine", fake_loader)
    monkeypatch.setattr(ta, "NlpEngineProvider", Recorder)
    monkeypatch.setattr(ta, "AnalyzerEngine", Recorder)
    return seen


@pytest.mark.parametrize(
    ("engine", "model"),
    [
        ("spacy", settings.DEFAULT_SPACY_MODEL),
        ("transformers", settings.DEFAULT_TRANSFORMERS_MODEL),
    ],
)
def test_the_default_model_follows_the_engine(
    built: dict, engine: str, model: str
) -> None:
    a = ta.ModularTextAnalyzer(nlp_engine=engine)
    assert a.nlp_engine == "nlp-engine"
    assert built["config_dict"] == {"nlp_engine": engine, "model_name": model}


def test_an_explicit_model_is_used(built: dict) -> None:
    ta.ModularTextAnalyzer(model_name="m", nlp_engine="transformers")
    assert built["config_dict"] == {"nlp_engine": "transformers", "model_name": "m"}


def test_the_pattern_analyzer_uses_spacy_and_the_dutch_recognizers(built: dict) -> None:
    a = ta.ModularTextAnalyzer()
    engine = a.analyzer.kwargs  # type: ignore[attr-defined]
    assert engine["nlp_engine"] == "presidio-spacy-engine"
    assert engine["supported_languages"] == [settings.DEFAULT_LANGUAGE]
    registry = engine["registry"]
    assert registry.supported_languages == [settings.DEFAULT_LANGUAGE]
    assert [type(r) for r in registry.recognizers] == [
        patterns.DutchPhoneNumberRecognizer,
        patterns.DutchIBANRecognizer,
        patterns.DutchBSNRecognizer,
        patterns.DutchDateRecognizer,
        patterns.EmailRecognizer,
        patterns.DutchPassportIdRecognizer,
        patterns.DutchDriversLicenseRecognizer,
        patterns.CaseNumberRecognizer,
    ]


def test_the_presidio_spacy_configuration(
    built: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    configs: list = []

    class Provider(Recorder):
        def __init__(self, **kwargs: object) -> None:
            configs.append(kwargs["nlp_configuration"])

    monkeypatch.setattr(ta, "NlpEngineProvider", Provider)
    ta.ModularTextAnalyzer(nlp_engine="transformers")
    assert configs == [
        {
            "nlp_engine_name": "spacy",
            "models": [
                {
                    "lang_code": settings.DEFAULT_LANGUAGE,
                    "model_name": settings.DEFAULT_SPACY_MODEL,
                }
            ],
        }
    ]


@pytest.mark.parametrize(
    ("asked", "engine"),
    [(None, settings.DEFAULT_NLP_ENGINE), ("", settings.DEFAULT_NLP_ENGINE), ("transformers", "transformers")],
)
def test_the_factory_builds_the_engine_asked_for(
    built: dict, asked: str | None, engine: str
) -> None:
    """text_analyzer is the public way in: the asked engine, else the default."""
    from src.api.analysis.analyzer import text_analyzer

    a = text_analyzer(asked)
    assert isinstance(a, ta.ModularTextAnalyzer)
    assert built["config_dict"]["nlp_engine"] == engine
