"""The anonymization and restore runs behind the documents component's surface."""

import os
from dataclasses import dataclass

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from src.api.documents import pdf_xmp
from src.api.documents.crud import save
from src.api.documents.database import AnonymizationEvent, Document
from src.api.documents.settings import document_settings


@dataclass(frozen=True)
class AnonymizationRun:
    """One anonymization of a stored document and how long it took."""

    doc: Document
    result: pdf_xmp.AnalysisAnonymizationResponse
    time_ms_taken: int

    @property
    def failed(self) -> bool:
        """Tell whether the run's status reports a failure."""
        return self.result.status_text.startswith("failed")


def anonymize(
    doc: Document, entity_types: list[str]
) -> pdf_xmp.AnalysisAnonymizationResponse:
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


def restore(files: pdf_xmp.DeanonymizationFiles) -> BackgroundTasks:
    """Write the PDF with its records back and return the tasks that clean up."""
    doc = pdf_xmp.process_anonymized_pdf_to_deanonymize(
        anon_path=files.anon_path, key=document_settings.CRYPTO_KEY.decode()
    )
    return pdf_xmp.save_document_and_cleanup(doc, files)
