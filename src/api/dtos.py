from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, field_validator

from src.api.config import settings


class DocumentTagDto(BaseModel):
    id: str
    name: str


class DocumentDto(BaseModel):
    id: str
    filename: str
    content_type: str
    uploaded_at: datetime
    tags: list[DocumentTagDto]
    pii_entities: Optional[list[dict[str, str]]] = None


class AddDocumentResponseInvalid(BaseModel):
    message: str


class AddDocumentResponseSuccess(BaseModel):
    files: list[DocumentDto]


AddDocumentResponse = AddDocumentResponseSuccess | AddDocumentResponseInvalid


class DocumentAnonymizationRequest(BaseModel):
    pii_entities_to_anonymize: list[str]  # List of PII entities to anonymize

    @field_validator("pii_entities_to_anonymize")
    def validate_pii_entities(cls, value: list[str]) -> list[str]:
        """Check if the PII entities are in list settings.SUPPORTED_PII_ENTITIES_TO_ANONYMIZE."""
        unsupported_entities = [
            entity
            for entity in value
            if entity not in settings.SUPPORTED_PII_ENTITIES_TO_ANONYMIZE
        ]
        if unsupported_entities:
            raise ValueError(
                f"Unsupported PII entities: {', '.join(unsupported_entities)}. "
                f"Supported entities are: {', '.join(settings.SUPPORTED_PII_ENTITIES_TO_ANONYMIZE)}"
            )
        return value


class DocumentAnonymizationResponse(BaseModel):
    id: str
    filename: str
    anonymized_at: datetime
    time_taken: int  # Time taken for anonymization in seconds
    status: str  # e.g., "success", "failed"
    pii_entities: Optional[list[dict[str, str]]] = (
        None  # Anonymized entities if applicable
    )


# ===== STRING-BASED ENDPOINT DTOs =====


class PIIEntity(BaseModel):
    """PII Entity with optional score and position info (model-dependent)."""

    entity_type: str
    text: str
    start: int  # Start position in original text
    end: int  # End position in original text
    score: Optional[Union[float, str]] = (
        None  # Some models return empty string, others float
    )


class _TextRequest(BaseModel):
    """Fields and validation shared by the text analysis requests."""

    text: str
    language: str = settings.DEFAULT_LANGUAGE
    entities: Optional[list[str]] = None  # Filter specific entity types
    nlp_engine: Optional[str] = None  # Override default engine

    @field_validator("text")
    def validate_text_not_empty(cls, value: str) -> str:
        """Ensure text is not empty."""
        if not value or not value.strip():
            raise ValueError("Text cannot be empty")
        return value.strip()

    @field_validator("language")
    def validate_language(cls, value: str) -> str:
        """Validate language code."""
        supported_languages = ["nl", "en"]  # Extend as needed
        if value not in supported_languages:
            raise ValueError(
                f"Unsupported language: {value}. Supported: {', '.join(supported_languages)}"
            )
        return value

    @field_validator("entities")
    def validate_entities(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        """Validate entity types if provided."""
        if value is not None:
            unsupported_entities = [
                entity
                for entity in value
                if entity not in settings.SUPPORTED_PII_ENTITIES_TO_ANONYMIZE
            ]
            if unsupported_entities:
                raise ValueError(
                    f"Unsupported entities: {', '.join(unsupported_entities)}. "
                    f"Supported: {', '.join(settings.SUPPORTED_PII_ENTITIES_TO_ANONYMIZE)}"
                )
        return value


class AnalyzeTextRequest(_TextRequest):
    """Request DTO for POST /api/v1/analyze endpoint."""


class AnalyzeTextResponse(BaseModel):
    """Response DTO for POST /api/v1/analyze endpoint."""

    pii_entities: list[PIIEntity]
    text_length: int
    processing_time_ms: Optional[int] = None
    nlp_engine_used: Optional[str] = None


class AnonymizeTextRequest(_TextRequest):
    """Request DTO for POST /api/v1/anonymize endpoint."""

    anonymization_strategy: str = "replace"  # replace, mask, redact, etc.

    @field_validator("anonymization_strategy")
    def validate_strategy(cls, value: str) -> str:
        """Validate anonymization strategy."""
        supported_strategies = ["replace", "mask", "redact", "hash"]
        if value not in supported_strategies:
            raise ValueError(
                f"Unsupported strategy: {value}. Supported: {', '.join(supported_strategies)}"
            )
        return value


class AnonymizeTextResponse(BaseModel):
    """Response DTO for POST /api/v1/anonymize endpoint (consistent with Presidio)."""

    original_text: str
    anonymized_text: str
    entities_found: list[PIIEntity]
    text_length: int
    processing_time_ms: Optional[int] = None
    nlp_engine_used: Optional[str] = None
    anonymization_strategy: Optional[str] = None
