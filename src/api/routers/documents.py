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

from src.api.auth import get_user
from src.api.config import settings
from src.api.documents import service
from src.api.documents.service import get_db
from src.api.dtos import (
    AddDocumentResponse,
    AddDocumentResponseSuccess,
    DocumentAnonymizationRequest,
    DocumentAnonymizationResponse,
    DocumentDto,
    DocumentTagDto,
)

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
    uploads = await service.store_uploads(
        files, service.UploadTarget(tags=tags or [], db=db)
    )

    return AddDocumentResponseSuccess(files=[_document_dto(u) for u in uploads])


def _document_dto(stored: service.StoredUpload) -> DocumentDto:
    """Describe a stored document, with the current time as upload time."""
    doc = stored.document
    return DocumentDto(
        id=str(doc.id),
        filename=str(doc.filename),
        content_type=str(doc.content_type),
        uploaded_at=datetime.now(),
        tags=[DocumentTagDto(id=str(t.id), name=str(t.name)) for t in stored.tags],
        pii_entities=stored.unique_entities,
    )


@dataclass(frozen=True)
class DocumentRequest:
    """The document id from the path, with the database session of the request."""

    file_id: str
    db: Session


def document_request(file_id: str, db: Session = Depends(get_db)) -> DocumentRequest:
    """FastAPI dependency that bundles the path id and the session."""
    return DocumentRequest(file_id=file_id, db=db)


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
    temp = await service.save_for_restore(file)
    try:
        response = _restored_file_response(temp, file.filename)
    except Exception as exc:
        temp.remove()
        raise _deanonymization_error(exc)
    elapsed = time.perf_counter() - start
    logger.debug(f"Deanonymization completed in {elapsed:.2f} seconds")
    return response


def _restored_file_response(
    temp: service.DeanonymizationFiles, filename: Optional[str]
) -> FileResponse:
    """Serve the restored PDF, cleaning up the temporary files afterwards."""
    return FileResponse(
        path=str(temp.deanon_path),
        filename=f"deanonymized_{filename}" if filename else "deanonymized.pdf",
        media_type="application/pdf",
        background=_restore(temp),
    )


def _restore(temp: service.DeanonymizationFiles) -> BackgroundTasks:
    """Write the restored PDF and return its cleanup.

    422 without records, or with a record that does not decrypt or fit.
    """
    try:
        doc = service.restored_pdf(temp)
    except ValueError as error:
        raise _unrestorable(error)
    return service.save_restored(doc, temp)


def _unrestorable(error: ValueError) -> HTTPException:
    """Log why a PDF cannot be restored and return the 422 to raise."""
    if isinstance(error, service.UnusableRecordError):
        logger.error(f"Unusable record during deanonymization: {error}")
        detail = f"The document cannot be restored: {error}"
    else:
        logger.error(f"Value error during deanonymization: {str(error)}", exc_info=True)
        detail = "No anonymization metadata found in the document"
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail
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
    entities = await service.unique_entities(doc) if details else []
    return _document_dto(service.StoredUpload(doc, doc.tags, entities))


def _existing_document(request: DocumentRequest) -> service.Document:
    """Return the requested document; 422 for a malformed id, 404 when unknown."""
    file_id_check(request.file_id)
    doc = service.find_document(request.db, request.file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@documents_router.post("/{file_id}/anonymize")
async def anonymize_document(
    request_body: DocumentAnonymizationRequest,
    request: DocumentRequest = Depends(document_request),
) -> DocumentAnonymizationResponse:
    """Anonymize a specific document."""
    start = time.perf_counter()
    doc = _existing_document(request)
    run = service.AnonymizationRun(
        doc=doc,
        result=_analyze_and_anonymize(doc, request_body),
        time_ms_taken=int((time.perf_counter() - start) * 1000),
    )
    service.record_run(request.db, run)
    return _anonymized_response(request, run)


def _anonymized_response(
    request: DocumentRequest, run: service.AnonymizationRun
) -> DocumentAnonymizationResponse:
    """Describe a successful run; a failed run is a 500 with its status."""
    if run.failed:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document anonymization failed: {run.result.status_text}",
        )
    return DocumentAnonymizationResponse(
        id=request.file_id,
        filename=str(run.doc.filename),
        anonymized_at=datetime.now(),  # Use current time for response
        time_taken=run.time_ms_taken,
        status=run.result.status_text,
        pii_entities=run.result.selected_entities,
    )


def _analyze_and_anonymize(
    doc: service.Document, request_body: DocumentAnonymizationRequest
) -> service.AnalysisAnonymizationResponse:
    """Run the anonymization; any error becomes a 500."""
    try:
        return service.anonymize(doc, request_body.pii_entities_to_anonymize)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during document anonymization: {str(e)}",
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


def _anonymized_document(request: DocumentRequest) -> service.Document:
    """Return the requested document; 404 unless it has been anonymized."""
    file_id_check(request.file_id)
    doc = service.find_document(request.db, request.file_id)
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
