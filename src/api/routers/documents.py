import logging
import os
import time
import uuid
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
from src.api.crud import (
    create_anonymization_event,
    get_document,
    update_document_anonymized_path,
)
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

    anon_path, deanon_path = await pdf_xmp.create_temp_paths_and_save(file)

    try:
        key = settings.CRYPTO_KEY.decode()
        try:
            doc = pdf_xmp.process_anonymized_pdf_to_deanonymize(
                anon_path=anon_path, key=key
            )
        except ValueError as ve:
            logger.error(
                f"Value error during deanonymization: {str(ve)}", exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No anonymization metadata found in the document",
            )
        background = pdf_xmp.save_document_and_cleanup(
            anon_path=anon_path,
            deanon_path=deanon_path,
            doc=doc,
            keep_temp_files=settings.KEEP_TEMP_FILES,
        )

        end = time.perf_counter()
        logger.debug(f"Deanonymization completed in {end - start:.2f} seconds")

        filename = (
            f"deanonymized_{file.filename}" if file.filename else "deanonymized.pdf"
        )
        return FileResponse(
            path=str(deanon_path),
            filename=filename,
            media_type="application/pdf",
            background=background,
        )
    except HTTPException as http_exc:
        # Clean up temporary files in case of HTTP error
        if anon_path.exists():
            anon_path.unlink()
        if deanon_path.exists():
            deanon_path.unlink()

        logger.error(
            f"HTTP error during deanonymization: {http_exc.detail}", exc_info=True
        )
        raise http_exc

    except Exception as e:
        # Clean up temporary files in case of error
        if anon_path.exists():
            anon_path.unlink()
        if deanon_path.exists():
            deanon_path.unlink()

        logger.error(f"Error during deanonymization: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deanonymize document: {str(e)}",
        )


@documents_router.get("/{file_id}/metadata", response_model=DocumentDto)
async def get_document_metadata(
    file_id: str,
    details: bool = False,
    db: Session = Depends(get_db),
) -> DocumentDto:
    """Get metadata for a specific document. Same response as upload."""
    file_id_check(file_id)
    doc = get_document(db, file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    tags = [DocumentTagDto(id=str(tag.id), name=str(tag.name)) for tag in doc.tags]

    if details:
        # Try to use stored PII entities first
        unique_entities = []
        if doc.pii_entities:
            try:
                import json

                stored_entities = json.loads(doc.pii_entities)
                # Convert to unique entities format (entity_type and text only)
                seen = set()
                for entity in stored_entities:
                    key = (entity.get("entity_type", ""), entity.get("text", ""))
                    if (
                        key not in seen
                        and entity.get("entity_type")
                        and entity.get("text")
                    ):
                        unique_entities.append(
                            {
                                "entity_type": entity["entity_type"],
                                "text": entity["text"],
                            }
                        )
                        seen.add(key)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(
                    f"Failed to parse stored PII entities for document {file_id}: {e}"
                )

        # Fallback: re-analyze if no stored entities found
        if not unique_entities:
            try:
                text = pdf_xmp.extract_text_from_pdf(Path(doc.source_path))
                _, unique_entities = await pdf_xmp.extract_unique_entities(text=text)
            except Exception as e:
                logger.warning(f"Failed to re-analyze document {file_id}: {e}")
                unique_entities = []
    else:
        unique_entities = []

    return DocumentDto(
        id=str(doc.id),
        filename=str(doc.filename),
        content_type=str(doc.content_type),
        uploaded_at=datetime.now(),  # Use current time as fallback
        tags=tags,
        pii_entities=unique_entities,
    )


@documents_router.post("/{file_id}/anonymize")
async def anonymize_document(
    file_id: str,
    request_body: DocumentAnonymizationRequest,
    db: Session = Depends(get_db),
) -> DocumentAnonymizationResponse:
    """Anonymize a specific document."""
    start = time.perf_counter()
    file_id_check(file_id)
    doc = get_document(db, file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        result: pdf_xmp.AnalysisAnonymizationResponse = (
            pdf_xmp.analyze_and_anonymize_document(
                file_id=file_id,
                request_body=request_body,
                doc=doc,
                key=settings.CRYPTO_KEY.decode(),
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during document anonymization: {str(e)}",
        )
    # unpack the result
    out_path = result.output_path
    selected = result.selected_entities
    status_text = result.status_text

    end = time.perf_counter()
    time_ms_taken = int((end - start) * 1000)  # Convert to milliseconds

    if result.status_text.startswith("failed"):
        # Remove the output file if it exists but anonymization failed
        if os.path.exists(out_path):
            os.unlink(out_path)

        # Create anonymization event to record the failure
        event = create_anonymization_event(
            db,
            document_id=file_id,
            time_taken=time_ms_taken,
            status=status_text,
        )
        event._pii_entities = selected

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document anonymization failed: {status_text}",
        )

    # update DB entries
    updated_doc = update_document_anonymized_path(db, file_id, str(out_path))
    event = create_anonymization_event(
        db,
        document_id=file_id,
        time_taken=time_ms_taken,
        status=status_text,
    )
    event._pii_entities = selected

    return DocumentAnonymizationResponse(
        id=file_id,
        filename=str(updated_doc.filename) if updated_doc else "",
        anonymized_at=datetime.now(),  # Use current time for response
        time_taken=time_ms_taken,
        status=status_text,
        pii_entities=selected,
    )


@documents_router.get("/{file_id}/download")
async def download_document(
    file_id: str,
    keep_on_server: bool = False,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download a specific document.

    Now we can use FastAPI's FileResponse to serve the file directly from disk;
    however in the future, we may use StreamingResponse to stream large files (from memory or disk) to the client.
    """
    file_id_check(file_id)
    doc = get_document(db, file_id)
    if not doc or not doc.anonymized_path:
        raise HTTPException(status_code=404, detail="Document not anonymized")

    path = Path(str(doc.anonymized_path))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    background = BackgroundTasks()
    if not keep_on_server:
        background.add_task(path.unlink)
        source_path = Path(str(doc.source_path))
        background.add_task(source_path.unlink)

    return FileResponse(path=str(path), filename=path.name, background=background)


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
