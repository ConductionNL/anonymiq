"""Public surface of the documents component: the operations the HTTP routes use.

PDF redaction, the XMP records, encryption and the database stay internal.
"""

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.orm import Session

from src.api.documents import crud, entities, pdf_xmp, runs
from src.api.documents.database import Document
from src.api.documents.session import get_db as get_db

# The types in the signatures below.
AnalysisAnonymizationResponse = pdf_xmp.AnalysisAnonymizationResponse
AnonymizationRun = runs.AnonymizationRun
DeanonymizationFiles = pdf_xmp.DeanonymizationFiles
StoredUpload = pdf_xmp.StoredUpload
UnusableRecordError = pdf_xmp.UnusableRecordError
UploadTarget = pdf_xmp.UploadTarget


async def store_uploads(
    files: list[UploadFile], target: UploadTarget
) -> list[StoredUpload]:
    """Store each upload with its tags and the PII entities found in it."""
    return await pdf_xmp.upload_and_analyze_files(files, target)


def find_document(db: Session, document_id: str) -> Document | None:
    """Return the stored document with this id, or None."""
    return crud.get_document(db, document_id)


async def unique_entities(doc: Document) -> list[dict[str, str]]:
    """Return the document's distinct entities, analyzing it again if none are stored."""
    return await entities.unique_entities(doc)


def anonymize(doc: Document, entity_types: list[str]) -> AnalysisAnonymizationResponse:
    """Anonymize the requested entity types of a stored document."""
    return runs.anonymize(doc, entity_types)


def record_run(db: Session, run: AnonymizationRun) -> None:
    """Record a run as an event; keep the output of a success, remove a failure's."""
    runs.record_run(db, run)


async def save_for_restore(file: UploadFile) -> DeanonymizationFiles:
    """Save an uploaded anonymized PDF and choose the path of its restored copy."""
    return await pdf_xmp.create_temp_paths_and_save(file)


def restore(files: DeanonymizationFiles) -> BackgroundTasks:
    """Write the PDF with its records back and return the tasks that clean up.

    Raises ValueError when the PDF holds no records, and its subclass
    UnusableRecordError when a record does not decrypt or cannot be placed.
    """
    return runs.restore(files)
