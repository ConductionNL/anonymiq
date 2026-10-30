"""Characterization tests for the spaCy and transformers NLP engine wrappers.

The spaCy model and the transformers pipeline are replaced by fakes, so these
tests pin how each wrapper turns raw entities into result dicts and filters
them.
"""

from dataclasses import dataclass

import pytest

from src.api.utils.nlp.spacy_engine import SpacyEngine
from src.api.utils.nlp.transformers_engine import TransformersEngine


@dataclass
class Ent:
    label_: str
    start_char: int
    end_char: int
    text: str


@dataclass
class Doc:
    ents: list[Ent]


def spacy_engine(ents: list[Ent]) -> SpacyEngine:
    engine = SpacyEngine.__new__(SpacyEngine)
    engine.nlp = lambda text: Doc(ents)  # type: ignore[assignment]
    return engine


SPACY_ENTS = [Ent("PERSON", 0, 10, "Jan Jansen"), Ent("LOCATION", 15, 22, "Utrecht")]


def test_spacy_results_without_a_filter() -> None:
    assert spacy_engine(SPACY_ENTS).analyze("Jan Jansen uit Utrecht") == [
        {
            "entity_type": "PERSON",
            "start": 0,
            "end": 10,
            "score": "",
            "text": "Jan Jansen",
        },
        {
            "entity_type": "LOCATION",
            "start": 15,
            "end": 22,
            "score": "",
            "text": "Utrecht",
        },
    ]


@pytest.mark.parametrize(
    ("entities", "types"),
    [(["LOCATION"], ["LOCATION"]), ([], []), (["EMAIL"], [])],
)
def test_spacy_filter(entities: list, types: list) -> None:
    results = spacy_engine(SPACY_ENTS).analyze("x", entities)
    assert [r["entity_type"] for r in results] == types


def transformers_engine(raw: list[dict]) -> TransformersEngine:
    engine = TransformersEngine.__new__(TransformersEngine)
    engine.ner_pipeline = lambda text: raw  # type: ignore[assignment]
    return engine


TEXT = "Jan Jansen uit Utrecht"
RAW = [
    {"entity_group": "PER", "start": 0, "end": 10, "score": 0.9, "word": "Jan Jansen"},
    {"entity": "LOC", "start": 15, "end": 22, "score": 0.8},
    {"start": 11, "end": 14, "score": 0.1, "word": "uit"},
]


def test_transformers_results_without_a_filter() -> None:
    assert transformers_engine(RAW).analyze(TEXT) == [
        {
            "entity_type": "PER",
            "start": 0,
            "end": 10,
            "score": 0.9,
            "text": "Jan Jansen",
        },
        {"entity_type": "LOC", "start": 15, "end": 22, "score": 0.8, "text": "Utrecht"},
        {"entity_type": "", "start": 11, "end": 14, "score": 0.1, "text": "uit"},
    ]


def test_entity_group_wins_over_entity() -> None:
    raw = [{"entity_group": "A", "entity": "B", "start": 0, "end": 1, "score": 1}]
    assert transformers_engine(raw).analyze("x")[0]["entity_type"] == "A"


@pytest.mark.parametrize(
    ("entities", "types"),
    [(["LOC"], ["LOC"]), ([], []), (["PER", ""], ["PER", ""])],
)
def test_transformers_filter(entities: list, types: list) -> None:
    results = transformers_engine(RAW).analyze(TEXT, entities)
    assert [r["entity_type"] for r in results] == types
