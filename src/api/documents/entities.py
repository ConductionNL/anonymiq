"""The distinct PII entities of a stored document."""

import json
import logging
from pathlib import Path

from src.api.documents import pdf_xmp
from src.api.documents.database import Document

logger = logging.getLogger(__name__)


async def unique_entities(doc: Document) -> list[dict[str, str]]:
    """Return the stored unique entities, or analyse the PDF again without them."""
    unique_entities = _stored_unique_entities(doc)
    if unique_entities:
        return unique_entities
    try:
        text = pdf_xmp.extract_text_from_pdf(Path(doc.source_path))
        _, unique_entities = await pdf_xmp.extract_unique_entities(text=text)
    except Exception as e:
        logger.warning(f"Failed to re-analyze document {doc.id}: {e}")
        return []
    return unique_entities


def _stored_unique_entities(doc: Document) -> list[dict[str, str]]:
    """Return the distinct (entity_type, text) pairs stored on the document."""
    if not doc.pii_entities:
        return []
    try:
        return _distinct_entities(json.loads(doc.pii_entities))
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(
            f"Failed to parse stored PII entities for document {doc.id}: {e}"
        )
        return []


def _distinct_entities(entities: list[dict]) -> list[dict[str, str]]:
    """Keep the first of each (entity_type, text) pair that has both values."""
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for entity in entities:
        key = (entity.get("entity_type", ""), entity.get("text", ""))
        if all(key) and key not in unique:
            unique[key] = {"entity_type": entity["entity_type"], "text": entity["text"]}
    return list(unique.values())
