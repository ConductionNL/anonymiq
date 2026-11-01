from typing import List, Optional

from pydantic import BaseModel, Field

from src.api.analysis.analyzer import analysis_settings


class AnalyzeRequest(BaseModel):
    """Request-model voor het analyseren van tekst op PII."""

    text: str
    entities: Optional[List[str]] = Field(
        default_factory=lambda: ["PERSON", "LOCATION", "PHONE_NUMBER", "EMAIL", "IBAN"]
    )
    language: Optional[str] = analysis_settings.DEFAULT_LANGUAGE


class EntityResult(BaseModel):
    """Model voor een gevonden entiteit in de tekst."""

    entity_type: str
    text: str
    start: int
    end: int
    score: float


class AnalyzeResponse(BaseModel):
    """Response-model voor analyse-resultaten (gevonden entiteiten)."""

    text: str
    entities_found: List[EntityResult]


class AnonymizeResponse(BaseModel):
    """Response-model voor geanonimiseerde tekst."""

    text: str
    anonymized: str
