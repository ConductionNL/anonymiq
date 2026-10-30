import logging
import time
from dataclasses import dataclass
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, status

from src.api.analysis.analyzer import TextAnalyzer, analysis_settings, text_analyzer
from src.api.dtos import (
    AnalyzeTextRequest,
    AnalyzeTextResponse,
    AnonymizeTextRequest,
    AnonymizeTextResponse,
    PIIEntity,
)

logger = logging.getLogger(__name__)
text_analysis_router = APIRouter(tags=["text-analysis"])


def create_pii_entities_from_results(results: list[dict]) -> list[PIIEntity]:
    """Convert text analyzer results to PIIEntity DTOs."""
    return [
        PIIEntity(
            entity_type=result["entity_type"],
            text=result["text"],
            start=result["start"],
            end=result["end"],
            score=_score(result),
        )
        for result in results
    ]


def _score(result: dict) -> Optional[Union[float, str]]:
    """Return the result's score, or None when it is missing or blank.

    Some models return an empty string, others a float.
    """
    score = result.get("score")
    if score is None or (isinstance(score, str) and score.strip() == ""):
        return None
    return score  # type: ignore[no-any-return]


@dataclass(frozen=True)
class _Anonymized:
    """The entities found in a text and the text with them replaced."""

    entities_found: list[PIIEntity]
    anonymized_text: str


@dataclass(frozen=True)
class _Analysis:
    """The analyzer for one request, with its engine, entity types and start time."""

    nlp_engine: str
    analyzer: TextAnalyzer
    entities: list[str]
    start_time: float

    @classmethod
    def of(cls, request: AnalyzeTextRequest | AnonymizeTextRequest) -> "_Analysis":
        """Build the analyzer the request asks for, or the default one."""
        start_time = time.perf_counter()
        nlp_engine = request.nlp_engine or analysis_settings.DEFAULT_NLP_ENGINE
        return cls(
            nlp_engine=nlp_engine,
            analyzer=text_analyzer(nlp_engine),
            entities=request.entities or analysis_settings.DEFAULT_ENTITIES,
            start_time=start_time,
        )

    def entities_in(
        self, request: AnalyzeTextRequest | AnonymizeTextRequest
    ) -> list[PIIEntity]:
        """Analyze the request's text and return the entities found."""
        results = self.analyzer.analyze_text(
            text=request.text, entities=self.entities, language=request.language
        )
        return create_pii_entities_from_results(results)

    def anonymize(self, request: AnonymizeTextRequest) -> _Anonymized:
        """Find the entities in the request's text and replace them."""
        return _Anonymized(
            entities_found=self.entities_in(request),
            anonymized_text=self.analyzer.anonymize_text(
                text=request.text, entities=self.entities, language=request.language
            ),
        )

    def elapsed_ms(self) -> int:
        """Return the milliseconds since the request started."""
        return int((time.perf_counter() - self.start_time) * 1000)

    def analyze_response(
        self, request: AnalyzeTextRequest, pii_entities: list[PIIEntity]
    ) -> AnalyzeTextResponse:
        """Log the analysis and describe it in the response."""
        processing_time_ms = self.elapsed_ms()
        logger.info(
            f"Text analysis completed: {len(pii_entities)} entities found "
            f"in {processing_time_ms}ms using {self.nlp_engine} engine"
        )
        return AnalyzeTextResponse(
            pii_entities=pii_entities,
            text_length=len(request.text),
            processing_time_ms=processing_time_ms,
            nlp_engine_used=self.nlp_engine,
        )

    def anonymize_response(
        self, request: AnonymizeTextRequest, result: _Anonymized
    ) -> AnonymizeTextResponse:
        """Log the anonymization and describe it in the response."""
        processing_time_ms = self.elapsed_ms()
        logger.info(
            f"Text anonymization completed: {len(result.entities_found)} entities anonymized "
            f"in {processing_time_ms}ms using {self.nlp_engine} engine and {request.anonymization_strategy} strategy"
        )
        return AnonymizeTextResponse(
            original_text=request.text,
            anonymized_text=result.anonymized_text,
            entities_found=result.entities_found,
            text_length=len(request.text),
            processing_time_ms=processing_time_ms,
            nlp_engine_used=self.nlp_engine,
            anonymization_strategy=request.anonymization_strategy,
        )


def _failure(action: str, error: Exception) -> HTTPException:
    """Log a failed request and return the 500 to raise for it."""
    logger.error(f"{action} failed: {str(error)}", exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"{action} failed: {str(error)}",
    )


@text_analysis_router.post("/analyze")
async def analyze_text(
    request: AnalyzeTextRequest,
) -> AnalyzeTextResponse:
    """Analyze text for PII entities using the specified NLP engine.

    This endpoint accepts a text string and returns detected PII entities
    with their positions, types, and confidence scores (when available).

    Args:
        request: AnalyzeTextRequest containing text and analysis parameters

    Returns:
        AnalyzeTextResponse with detected PII entities and metadata

    Raises:
        HTTPException: On analysis failure or invalid parameters
    """
    try:
        analysis = _Analysis.of(request)
        pii_entities = analysis.entities_in(request)
    except Exception as e:
        raise _failure("Text analysis", e)
    return analysis.analyze_response(request, pii_entities)


@text_analysis_router.post("/anonymize")
async def anonymize_text(
    request: AnonymizeTextRequest,
) -> AnonymizeTextResponse:
    """Anonymize PII entities in text using the specified strategy.

    This endpoint accepts a text string and returns the anonymized version
    along with details about the entities that were found and anonymized.

    Args:
        request: AnonymizeTextRequest containing text and anonymization parameters

    Returns:
        AnonymizeTextResponse with original text, anonymized text, and entities found

    Raises:
        HTTPException: On anonymization failure or invalid parameters
    """
    try:
        analysis = _Analysis.of(request)
        result = analysis.anonymize(request)
    except Exception as e:
        raise _failure("Text anonymization", e)
    return analysis.anonymize_response(request, result)
