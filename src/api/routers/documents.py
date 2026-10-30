import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    UploadFile,
    status,
)
from fastapi import File as FastAPIFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.config import settings
from src.api.crud import get_document, save
from src.api.database import AnonymizationEvent, Document
from src.api.dependencies import get_db, get_user
from src.api.dtos import (
    AddDocumentResponse,
    AddDocumentResponseSuccess,
    DocumentAnonymizationRequest,
    DocumentAnonymizationResponse,
    DocumentDto,
    DocumentTagDto,
)
from src.api.utils import pdf_xmp

logger = logging.getLogger(__name__)
# Every document route requires HTTP Basic credentials. Documents reach this
# service before redaction, so they carry personal data. The dependency sits on
# the router, so a route added here later is protected without remembering to.
documents_router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(get_user)],
)


def validate_files_extensions(files: list[UploadFile]) -> None:
    """Validate that all uploaded files have supported extensions."""
    if any(
        f
        for f in files
        if f.filename is None
        or os.path.splitext(f.filename)[1][1:]
        not in settings.SUPPORTED_UPLOAD_EXTENSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Only files with the following extensions are supported: {', '.join(settings.SUPPORTED_UPLOAD_EXTENSIONS)}",
        )


@documents_router.post(
    "/upload",
)
async def upload_document(
    files: list[UploadFile] = FastAPIFile(...),
    tags: Optional[list[str]] = None,
    db: Session = Depends(get_db),
) -> AddDocumentResponse:
    validate_files_extensions(files)
    docs = await pdf_xmp.upload_and_analyze_files(files=files, tags=tags, db=db)

    return AddDocumentResponseSuccess(files=docs)


@dataclass(frozen=True)
class DocumentRequest:
    """The document id from the path, with the database session of the request."""

    file_id: str
    db: Session


def document_request(file_id: str, db: Session = Depends(get_db)) -> DocumentRequest:
    """FastAPI dependency that bundles the path id and the session."""
    return DocumentRequest(file_id=file_id, db=db)


@dataclass(frozen=True)
class _TempFiles:
    """The uploaded file and the restored copy of one deanonymization."""

    anon_path: Path
    deanon_path: Path

    def remove(self) -> None:
        """Delete both files when they exist."""
        for path in (self.anon_path, self.deanon_path):
            if path.exists():
                path.unlink()


@documents_router.post("/deanonymize")
async def deanonymize_document(
    file: UploadFile = FastAPIFile(...),
    db: Session = Depends(get_db),
) -> FileResponse:
    """The endpoint where the user can submit a document to deanonymize.

    The document contains metadata that was previously anonymized.
    The endpoint returns the original document with metadata restored.
    """
    start = time.perf_counter()
    validate_files_extensions([file])
    temp = _TempFiles(*await pdf_xmp.create_temp_paths_and_save(file))
    try:
        response = _restored_file_response(temp, file.filename)
    except Exception as exc:
        temp.remove()
        raise _deanonymization_error(exc)
    elapsed = time.perf_counter() - start
    logger.debug(f"Deanonymization completed in {elapsed:.2f} seconds")
    return response


def _restored_file_response(temp: _TempFiles, filename: Optional[str]) -> FileResponse:
    """Serve the restored PDF, cleaning up the temporary files afterwards."""
    return FileResponse(
        path=str(temp.deanon_path),
        filename=f"deanonymized_{filename}" if filename else "deanonymized.pdf",
        media_type="application/pdf",
        background=_restore(temp),
    )


def _restore(temp: _TempFiles) -> BackgroundTasks:
    """Write the restored PDF and return its cleanup; 422 without a record."""
    try:
        doc = pdf_xmp.process_anonymized_pdf_to_deanonymize(
            anon_path=temp.anon_path, key=settings.CRYPTO_KEY.decode()
        )
    except ValueError as ve:
        logger.error(f"Value error during deanonymization: {str(ve)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No anonymization metadata found in the document",
        )
    return pdf_xmp.save_document_and_cleanup(
        anon_path=temp.anon_path,
        deanon_path=temp.deanon_path,
        doc=doc,
        keep_temp_files=settings.KEEP_TEMP_FILES,
    )


def _deanonymization_error(exc: Exception) -> HTTPException:
    """Log a failed deanonymization and return the HTTP error to raise."""
    if isinstance(exc, HTTPException):
        logger.error(f"HTTP error during deanonymization: {exc.detail}", exc_info=True)
        return exc
    logger.error(f"Error during deanonymization: {str(exc)}", exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to deanonymize document: {str(exc)}",
    )


@documents_router.get("/{file_id}/metadata", response_model=DocumentDto)
async def get_document_metadata(
    details: bool = False,
    request: DocumentRequest = Depends(document_request),
) -> DocumentDto:
    """Get metadata for a specific document. Same response as upload."""
    doc = _existing_document(request)
    return DocumentDto(
        id=str(doc.id),
        filename=str(doc.filename),
        content_type=str(doc.content_type),
        uploaded_at=datetime.now(),  # Use current time as fallback
        tags=[DocumentTagDto(id=str(tag.id), name=str(tag.name)) for tag in doc.tags],
        pii_entities=await _unique_entities(doc) if details else [],
    )


def _existing_document(request: DocumentRequest) -> Document:
    """Return the requested document; 422 for a malformed id, 404 when unknown."""
    file_id_check(request.file_id)
    doc = get_document(request.db, request.file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


async def _unique_entities(doc: Document) -> list[dict[str, str]]:
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


@dataclass(frozen=True)
class _AnonymizeRun:
    """One anonymization of a stored document and how long it took."""

    doc: Document
    result: pdf_xmp.AnalysisAnonymizationResponse
    time_ms_taken: int


@documents_router.post("/{file_id}/anonymize")
async def anonymize_document(
    request_body: DocumentAnonymizationRequest,
    request: DocumentRequest = Depends(document_request),
) -> DocumentAnonymizationResponse:
    """Anonymize a specific document."""
    start = time.perf_counter()
    doc = _existing_document(request)
    run = _AnonymizeRun(
        doc=doc,
        result=_analyze_and_anonymize(doc, request_body),
        time_ms_taken=int((time.perf_counter() - start) * 1000),
    )
    _record_event(request, run)
    _raise_when_failed(run.result)
    return _anonymized_response(request, run)


def _record_event(request: DocumentRequest, run: _AnonymizeRun) -> None:
    """Store the outcome of a run as an anonymization event."""
    save(
        request.db,
        AnonymizationEvent(
            document_id=request.file_id,
            time_taken=run.time_ms_taken,
            status=run.result.status_text,
        ),
    )


def _anonymized_response(
    request: DocumentRequest, run: _AnonymizeRun
) -> DocumentAnonymizationResponse:
    """Store the output path of a successful run and describe the run."""
    run.doc.anonymized_path = str(run.result.output_path)
    return DocumentAnonymizationResponse(
        id=request.file_id,
        filename=str(save(request.db, run.doc).filename),
        anonymized_at=datetime.now(),  # Use current time for response
        time_taken=run.time_ms_taken,
        status=run.result.status_text,
        pii_entities=run.result.selected_entities,
    )


def _analyze_and_anonymize(
    doc: Document, request_body: DocumentAnonymizationRequest
) -> pdf_xmp.AnalysisAnonymizationResponse:
    """Run the anonymization; any error becomes a 500."""
    try:
        return pdf_xmp.analyze_and_anonymize_document(
            doc,
            pdf_xmp.AnonymizationOrder(
                file_id=str(doc.id),
                entity_types=request_body.pii_entities_to_anonymize,
                key=settings.CRYPTO_KEY.decode(),
            ),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during document anonymization: {str(e)}",
        )


def _raise_when_failed(result: pdf_xmp.AnalysisAnonymizationResponse) -> None:
    """Remove the output of a failed run and raise a 500 with its status."""
    if not result.status_text.startswith("failed"):
        return
    if os.path.exists(result.output_path):
        os.unlink(result.output_path)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Document anonymization failed: {result.status_text}",
    )


@documents_router.get("/{file_id}/download")
async def download_document(
    keep_on_server: bool = False,
    request: DocumentRequest = Depends(document_request),
) -> FileResponse:
    """Download a specific document.

    Now we can use FastAPI's FileResponse to serve the file directly from disk;
    however in the future, we may use StreamingResponse to stream large files (from memory or disk) to the client.
    """
    doc = _anonymized_document(request)
    path = Path(str(doc.anonymized_path))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    background = BackgroundTasks()
    if not keep_on_server:
        background.add_task(path.unlink)
        background.add_task(Path(str(doc.source_path)).unlink)
    return FileResponse(path=str(path), filename=path.name, background=background)


def _anonymized_document(request: DocumentRequest) -> Document:
    """Return the requested document; 404 unless it has been anonymized."""
    file_id_check(request.file_id)
    doc = get_document(request.db, request.file_id)
    if not doc or not doc.anonymized_path:
        raise HTTPException(status_code=404, detail="Document not anonymized")
    return doc


def file_id_check(file_id: str) -> None:
    """Check if the given file_id is a valid UUID."""
    if not check_is_uuid(file_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid file ID format. Must be a valid UUID.",
        )


def check_is_uuid(value: str) -> bool:
    """Check if the given value is a valid UUID."""
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
