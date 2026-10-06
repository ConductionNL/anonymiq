import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.config import settings
from src.api.dependencies import get_user
from src.api.dtos import (
    AnalyzeTextRequest,
    AnalyzeTextResponse,
    AnonymizeTextRequest,
    AnonymizeTextResponse,
    PIIEntity,
)
from src.api.services.text_analyzer import ModularTextAnalyzer

logger = logging.getLogger(__name__)
# The text routes take raw text that still carries personal data, the same
# exposure as the document routes, so they sit behind the same HTTP Basic
# dependency. It is on the router, so a text route added later is protected
# without remembering to.
text_analysis_router = APIRouter(
    tags=["text-analysis"],
    dependencies=[Depends(get_user)],
)


def create_pii_entities_from_results(results: list[dict]) -> list[PIIEntity]:
    """Convert ModularTextAnalyzer results to PIIEntity DTOs."""
    pii_entities = []
    for result in results:
        # Handle different score types (some models return empty string, others float)
        score = result.get("score")
        if score == "" or score is None:
            score = None
        elif isinstance(score, str) and score.strip() == "":
            score = None

        pii_entities.append(
            PIIEntity(
                entity_type=result["entity_type"],
                text=result["text"],
                start=result["start"],
                end=result["end"],
                score=score,
            )
        )
    return pii_entities


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
    start_time = time.perf_counter()

    try:
        # Initialize analyzer with specified engine or use default
        nlp_engine = request.nlp_engine or settings.DEFAULT_NLP_ENGINE
        analyzer = ModularTextAnalyzer(nlp_engine=nlp_engine)

        # Perform analysis
        entities_to_analyze = request.entities or settings.DEFAULT_ENTITIES
        results = analyzer.analyze_text(
            text=request.text,
            entities=entities_to_analyze,
            language=request.language,
        )

        # Convert results to DTOs
        pii_entities = create_pii_entities_from_results(results)

        end_time = time.perf_counter()
        processing_time_ms = int((end_time - start_time) * 1000)

        logger.info(
            f"Text analysis completed: {len(pii_entities)} entities found "
            f"in {processing_time_ms}ms using {nlp_engine} engine"
        )

        return AnalyzeTextResponse(
            pii_entities=pii_entities,
            text_length=len(request.text),
            processing_time_ms=processing_time_ms,
            nlp_engine_used=nlp_engine,
        )

    except Exception as e:
        logger.error(f"Text analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text analysis failed: {str(e)}",
        )


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
    start_time = time.perf_counter()

    try:
        # Initialize analyzer with specified engine or use default
        nlp_engine = request.nlp_engine or settings.DEFAULT_NLP_ENGINE
        analyzer = ModularTextAnalyzer(nlp_engine=nlp_engine)

        # First analyze to find entities
        entities_to_analyze = request.entities or settings.DEFAULT_ENTITIES
        analysis_results = analyzer.analyze_text(
            text=request.text,
            entities=entities_to_analyze,
            language=request.language,
        )

        # Then anonymize the text
        anonymized_text = analyzer.anonymize_text(
            text=request.text,
            entities=entities_to_analyze,
            language=request.language,
        )

        # Convert analysis results to DTOs
        entities_found = create_pii_entities_from_results(analysis_results)

        end_time = time.perf_counter()
        processing_time_ms = int((end_time - start_time) * 1000)

        logger.info(
            f"Text anonymization completed: {len(entities_found)} entities anonymized "
            f"in {processing_time_ms}ms using {nlp_engine} engine and {request.anonymization_strategy} strategy"
        )

        return AnonymizeTextResponse(
            original_text=request.text,
            anonymized_text=anonymized_text,
            entities_found=entities_found,
            text_length=len(request.text),
            processing_time_ms=processing_time_ms,
            nlp_engine_used=nlp_engine,
            anonymization_strategy=request.anonymization_strategy,
        )

    except Exception as e:
        logger.error(f"Text anonymization failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text anonymization failed: {str(e)}",
        )
