"""Public surface of the documents component: the operations the HTTP routes use.

PDF redaction, the XMP records, encryption and the database stay internal.
"""

import os
from dataclasses import dataclass
from typing import Generator

import pymupdf
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.orm import Session

from src.api.documents import entities, pdf_xmp
from src.api.documents.crud import get_document, save
from src.api.documents.database import AnonymizationEvent, Document
from src.api.documents.session import SessionLocal
from src.api.documents.settings import document_settings

# The types in the signatures below.
AnalysisAnonymizationResponse = pdf_xmp.AnalysisAnonymizationResponse
DeanonymizationFiles = pdf_xmp.DeanonymizationFiles
StoredUpload = pdf_xmp.StoredUpload
UnusableRecordError = pdf_xmp.UnusableRecordError
UploadTarget = pdf_xmp.UploadTarget


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for one request and close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def store_uploads(
    files: list[UploadFile], target: UploadTarget
) -> list[StoredUpload]:
    """Store each upload with its tags and the PII entities found in it."""
    return await pdf_xmp.upload_and_analyze_files(files, target)


def find_document(db: Session, document_id: str) -> Document | None:
    """Return the stored document with this id, or None."""
    return get_document(db, document_id)


async def unique_entities(doc: Document) -> list[dict[str, str]]:
    """Return the document's distinct entities, analyzing it again if none are stored."""
    return await entities.unique_entities(doc)


@dataclass(frozen=True)
class AnonymizationRun:
    """One anonymization of a stored document and how long it took."""

    doc: Document
    result: AnalysisAnonymizationResponse
    time_ms_taken: int

    @property
    def failed(self) -> bool:
        """Tell whether the run's status reports a failure."""
        return self.result.status_text.startswith("failed")


def anonymize(doc: Document, entity_types: list[str]) -> AnalysisAnonymizationResponse:
    """Anonymize the requested entity types of a stored document."""
    return pdf_xmp.analyze_and_anonymize_document(
        doc,
        pdf_xmp.AnonymizationOrder(
            file_id=str(doc.id),
            entity_types=entity_types,
            key=document_settings.CRYPTO_KEY.decode(),
        ),
    )


def record_run(db: Session, run: AnonymizationRun) -> None:
    """Record a run as an event; keep the output of a success, remove a failure's."""
    save(
        db,
        AnonymizationEvent(
            document_id=str(run.doc.id),
            time_taken=run.time_ms_taken,
            status=run.result.status_text,
        ),
    )
    if not run.failed:
        run.doc.anonymized_path = str(run.result.output_path)
        save(db, run.doc)
    elif os.path.exists(run.result.output_path):
        os.unlink(run.result.output_path)


async def save_for_restore(file: UploadFile) -> DeanonymizationFiles:
    """Save an uploaded anonymized PDF and choose the path of its restored copy."""
    return await pdf_xmp.create_temp_paths_and_save(file)


def restored_pdf(files: DeanonymizationFiles) -> pymupdf.Document:
    """Return the PDF with its records written back; ValueError when it has none."""
    return pdf_xmp.process_anonymized_pdf_to_deanonymize(
        anon_path=files.anon_path, key=document_settings.CRYPTO_KEY.decode()
    )


def save_restored(
    doc: pymupdf.Document, files: DeanonymizationFiles
) -> BackgroundTasks:
    """Write the restored PDF and return the tasks that remove both files."""
    return pdf_xmp.save_document_and_cleanup(doc, files)
