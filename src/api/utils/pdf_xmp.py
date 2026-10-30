import hashlib
import json
import logging
import os
import re
import uuid
import xml.sax.saxutils as saxutils
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import pikepdf
import pymupdf
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.orm import Session

from src.api import database
from src.api.crud import save
from src.api.dtos import DocumentDto, DocumentTagDto
from src.api.services.text_analyzer import ModularTextAnalyzer
from src.api.utils.crypto import (
    aes_gcm_decrypt as decrypt_entity,
)
from src.api.utils.crypto import (
    aes_gcm_encrypt as encrypt_entity,
)
from src.api.utils.crypto import (
    fingerprint_sha256 as get_fingerprint,
)

_DEFAULT_ENTITY_MASK = {
    "person": "[PERSON]",
    "iban": "[IBAN]",
    "email": "[EMAIL]",
    "phone": "[PHONE]",
}

logger = logging.getLogger(__name__)


class _Occurrence(dict):
    """Typed helper for a single PII occurrence."""

    id: str  # Unique ID within the document
    page: int  # 1‑based page index
    rect: Tuple[float, float, float, float]  # (x0,y0,x1,y1)
    entity_type: str
    entity_mask: str
    encrypted_entity: str
    fingerprint: str


@dataclass
class AnalysisAnonymizationResponse:
    selected_entities: list[dict]
    output_path: Path
    status_text: str


@dataclass(frozen=True)
class DeanonymizationFiles:
    """The uploaded anonymized PDF and the restored copy written next to it.

    Unless ``keep`` is set, both are removed once the response is sent.
    """

    anon_path: Path
    deanon_path: Path
    keep: bool = False

    def remove(self) -> None:
        """Delete both files when they exist."""
        for path in (self.anon_path, self.deanon_path):
            if path.exists():
                path.unlink()


def save_document_and_cleanup(
    doc: pymupdf.Document, files: DeanonymizationFiles
) -> BackgroundTasks:
    """Save the restored PDF and return the tasks that remove the temporary files."""
    doc.save(str(files.deanon_path), incremental=False)
    doc.close()

    background = BackgroundTasks()
    if not files.keep:
        background.add_task(lambda: files.anon_path.unlink(missing_ok=True))
        background.add_task(lambda: files.deanon_path.unlink(missing_ok=True))
    return background


class UnusableRecordError(ValueError):
    """A record in the XMP packet cannot be decrypted or placed on its page."""


def process_anonymized_pdf_to_deanonymize(
    anon_path: Path, key: str
) -> pymupdf.Document:
    """Return the anonymized PDF with every recorded text written back.

    Raises:
        ValueError: when the PDF holds no records.
        UnusableRecordError: when a record does not decrypt or cannot be placed.
    """
    hashed_key = hashlib.sha256(key.encode()).digest()

    annotations = extract_annotations(str(anon_path), decryption_key=hashed_key)
    print(f"Extracted {annotations=} from the PDF")

    if not annotations:
        raise ValueError(
            "No annotations found in the PDF. Ensure the document has been properly anonymized."
        )

    return _restored(pymupdf.open(str(anon_path)), annotations)


def _restored(doc: pymupdf.Document, annotations: list[dict]) -> pymupdf.Document:
    """Write every record back into the document; close it when one is unusable."""
    try:
        for ann in annotations:
            _restore_annotation(doc, ann)
    except UnusableRecordError:
        doc.close()
        raise
    return doc


def _restore_annotation(doc: pymupdf.Document, ann: dict) -> None:
    """Write one record's plaintext over its rectangle."""
    rect, text = _annotation_rect(ann), _annotation_text(ann)
    page = doc[_annotation_page(doc, ann) - 1]  # Pages are 0-indexed in PyMuPDF
    page.add_redact_annot(rect, fill=(1, 1, 1), text=text)  # type: ignore
    page.apply_redactions()  # type: ignore
    if not _shows(page.get_textbox(rect), text):  # type: ignore
        raise _unusable(ann, f"does not fit its rect {ann.get('rect')!r}")


def _shows(written: str, text: str) -> bool:
    """Tell whether the text read back from a rectangle holds ``text``.

    Whitespace is compared loosely, because a long text wraps over lines.
    """
    return " ".join(text.split()) in " ".join(written.split())


def _annotation_text(ann: dict) -> str:
    """Return the record's decrypted text."""
    if "encrypted_entity" not in ann:
        raise _unusable(ann, "has no encrypted_entity")
    if ann.get("entity") is None:
        raise _unusable(ann, "does not decrypt with this key")
    return str(ann["entity"])


def _annotation_page(doc: pymupdf.Document, ann: dict) -> int:
    """Return the record's 1-based page number, which must be in the document."""
    try:
        page = int(ann["page"])
    except (KeyError, TypeError, ValueError):
        raise _unusable(ann, f"has no valid page: {ann.get('page')!r}")
    if not 1 <= page <= len(doc):
        raise _unusable(ann, f"names page {page} of a {len(doc)}-page document")
    return page


def _annotation_rect(ann: dict) -> pymupdf.Rect:
    """Return the record's rectangle.

    It may be stored as a list of four numbers or as a string of them, with or
    without brackets (``"[x0, y0, x1, y1]"`` or ``"x0,y0,x1,y1"``).
    """
    rect = ann.get("rect")
    parts = rect.strip().strip("[]").split(",") if isinstance(rect, str) else rect
    try:
        coords = [float(v) for v in parts]  # type: ignore[union-attr]
    except (TypeError, ValueError):
        coords = []
    if len(coords) != 4:
        raise _unusable(ann, f"has no valid rect of four numbers: {rect!r}")
    return pymupdf.Rect(*coords)


def _unusable(ann: dict, problem: str) -> UnusableRecordError:
    """Return the error for a record, named by its id."""
    return UnusableRecordError(f"Record {ann.get('id', '?')} {problem}")


async def create_temp_paths_and_save(file: UploadFile) -> DeanonymizationFiles:
    """Save an uploaded anonymized PDF and pick the path for its restored copy.

    Args:
        file (UploadFile): The uploaded file to be processed. (fastapi UploadFile)

    Returns:
        DeanonymizationFiles: the saved upload and the path for the restored copy.
    """
    content = await file.read()
    await file.close()

    from src.api.config import settings

    temp_dir = Path(settings.DATA_DIR) / "temp/deanonymized"
    temp_dir.mkdir(parents=True, exist_ok=True)

    process_id = uuid.uuid4().hex
    files = DeanonymizationFiles(
        anon_path=temp_dir / f"{process_id}_anonymized.pdf",
        deanon_path=temp_dir / f"{process_id}_deanonymized.pdf",
        keep=settings.KEEP_TEMP_FILES,
    )
    files.anon_path.write_bytes(content)
    return files


@dataclass(frozen=True)
class UploadTarget:
    """Where uploaded documents are stored and the tags they get."""

    tags: list[str]
    db: Session


async def upload_and_analyze_files(
    files: list[UploadFile], target: UploadTarget
) -> list[DocumentDto]:
    """Upload files, analyze them for PII entities, and store metadata in the database.

    Args:
        files (list[UploadFile]): List of files to be uploaded and analyzed.
        target (UploadTarget): the tags for every document and the database session.

    Returns:
        list[DocumentDto]: the stored documents, in upload order.
    """
    return [await _upload_and_analyze(file, target) for file in files]


async def _upload_and_analyze(file: UploadFile, target: UploadTarget) -> DocumentDto:
    """Store one upload, its entities and its tags, and describe it."""
    source = await _AnalyzedSource.of(file)
    db_document = save(target.db, source.document_row(file))
    db_tags = [
        save(
            target.db,
            database.Tag(id=uuid.uuid4().hex, name=name, document_id=source.file_id),
        )
        for name in target.tags
    ]
    db_document._entities = source.entities
    return source.dto(db_document, db_tags)


@dataclass(frozen=True)
class _AnalyzedSource:
    """An uploaded PDF saved under a new id, with the entities found in it."""

    file_id: str
    source_path: Path
    entities: list[dict]
    unique: list[dict[str, str]]

    @classmethod
    async def of(cls, file: UploadFile) -> "_AnalyzedSource":
        """Save the upload under a new id and analyze its text."""
        content = await file.read()
        await file.close()
        file_id = uuid.uuid4().hex
        source_path = _source_path(file_id)
        source_path.write_bytes(content)
        entities, unique = await extract_unique_entities(
            text=extract_text_from_pdf(source_path)
        )
        return cls(file_id, source_path, entities, unique)

    def document_row(self, file: UploadFile) -> database.Document:
        """Return the database row for this upload."""
        return database.Document(
            id=self.file_id,
            filename=file.filename or f"{self.file_id}.pdf",
            content_type=file.content_type or "application/pdf",
            source_path=str(self.source_path),
            anonymized_path=None,
            pii_entities=json.dumps(self.entities) if self.entities else None,
        )

    def dto(self, document: database.Document, tags: list[database.Tag]) -> DocumentDto:
        """Describe the stored upload, with the current time as upload time."""
        return DocumentDto(
            id=self.file_id,
            filename=str(document.filename),
            content_type=str(document.content_type),
            uploaded_at=datetime.now(),
            tags=[DocumentTagDto(id=str(tag.id), name=str(tag.name)) for tag in tags],
            pii_entities=self.unique,
        )


def _source_path(file_id: str) -> Path:
    """Return the path an upload is saved under, creating its directory."""
    from src.api.config import settings

    source_dir = Path(settings.DATA_DIR) / "temp/source"
    source_dir.mkdir(parents=True, exist_ok=True)
    return source_dir / f"{file_id}.pdf"


@dataclass(frozen=True)
class AnonymizationOrder:
    """Which entity types to anonymize in a stored document, and the sealing key."""

    file_id: str
    entity_types: list[str]
    key: str


def analyze_and_anonymize_document(
    doc: database.Document, order: AnonymizationOrder
) -> AnalysisAnonymizationResponse:
    """Analyze a document and anonymize identified PII entities.

    This function performs text extraction from a PDF document, analyzes it for PII entities,
    filters the entities based on the requested types to anonymize, and then creates
    an anonymized version of the PDF document.

    Args:
        doc: Database document model containing document information
        order: the document id, the PII entity types to anonymize and the
            private key used for encrypting PII entities

    Returns:
        AnalysisAnonymizationResponse:
            - selected_entities (list[dict]): Selected PII entities that were anonymized
            - output_path (Path): Path to the anonymized output file
            - status_text (str): Status message describing the result of the operation
    """
    entities = _document_entities(doc, ModularTextAnalyzer())
    selected = _select_entities(entities, order.entity_types)
    job = RedactionJob(
        input_path=doc.source_path,
        output_path=str(_anonymized_path(order.file_id)),
        replacements={e["text"]: e["entity_type"].lower() for e in selected},
        private_key=order.key,
    )
    return AnalysisAnonymizationResponse(
        selected_entities=selected,
        output_path=Path(job.output_path),
        status_text=_anonymize_to_output(job),
    )


def _anonymized_path(file_id: str) -> Path:
    """Return the output path for a document, creating its directory."""
    from src.api.config import settings

    anonym_dir = Path(settings.DATA_DIR) / "temp/anonymized"
    anonym_dir.mkdir(parents=True, exist_ok=True)
    return anonym_dir / f"{file_id}.pdf"


def _document_entities(
    doc: database.Document, analyzer: ModularTextAnalyzer
) -> list[dict]:
    """Return the PII entities of a document, analyzing its text once.

    The result is cached on the document as ``_entities``.
    """
    entities = getattr(doc, "_entities", None)
    if not entities:
        text = extract_text_from_pdf(Path(doc.source_path))
        entities = analyzer.analyze_text(text) if text else []
        doc._entities = entities
    return entities


def _select_entities(entities: list[dict], entity_types: list[str]) -> list[dict]:
    """Return copies of the entities of the requested types.

    The ``start``, ``end`` and ``score`` fields are turned into strings.
    """
    selected = []
    for e in entities:
        if e["entity_type"] in entity_types:
            e_copy = e.copy()
            for field in ("start", "end", "score"):
                if field in e_copy:
                    e_copy[field] = str(e_copy[field])
            selected.append(e_copy)
    return selected


def _anonymize_to_output(job: "RedactionJob") -> str:
    """Write the anonymized PDF and return the status text of the run."""
    try:
        return _write_anonymized(job)
    except Exception as exc:
        logger.error(_failure_message(exc), exc_info=True)
        return f"failed: {exc}"


def _write_anonymized(job: "RedactionJob") -> str:
    """Run the redaction and check that it produced a file."""
    out_path = Path(job.output_path)
    logger.info(
        f"Starting anonymization for document {out_path.stem} with {len(job.replacements)} entities"
    )
    if not os.path.exists(job.input_path):
        raise FileNotFoundError(f"Source file {job.input_path} not found")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    occurrences = anonymize_pdf(job)
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise ValueError("Anonymization failed to produce valid output file")
    _log_occurrence_count(len(occurrences), len(job.replacements))
    return f"success ({len(occurrences)} entities processed)"


# Log prefix per expected failure; anything else is unexpected.
_FAILURE_LABELS: tuple[tuple[type[Exception], str], ...] = (
    (FileNotFoundError, "File not found error"),
    (ValueError, "Value error during anonymization"),
)


def _failure_message(exc: Exception) -> str:
    """Return the log line for a failed anonymization."""
    for kind, label in _FAILURE_LABELS:
        if isinstance(exc, kind):
            return f"{label}: {exc}"
    return f"Unexpected error during anonymization: {exc}"


def _log_occurrence_count(occurrence_count: int, entity_count: int) -> None:
    """Log when the redacted occurrences differ from the unique entities."""
    if occurrence_count < entity_count:
        logger.warning(
            f"Only {occurrence_count} out of {entity_count} entities were processed"
        )
    elif occurrence_count > entity_count:
        logger.info(
            f"Processed {occurrence_count} occurrences of {entity_count} unique entities"
        )


def extract_text_from_pdf(source_path: Path) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    text = ""
    try:
        doc = pymupdf.open(str(source_path))
        text = "\n".join(page.get_text() for page in doc)  # type: ignore
        doc.close()
    except Exception:
        text = ""
    return text


async def extract_unique_entities(
    text: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Extract unique entities from the given text using the provided analyzer.

    Args:
        text (str): The text to analyze for entities.

    Returns:
        tuple[list[dict[str, str]], list[dict[str, str]]]: the first list contains all entities found,
            the second list contains unique entities with their types and text.
    """
    analyzer = ModularTextAnalyzer()
    entities = analyzer.analyze_text(text) if text else []
    unique: list[dict[str, str]] = []
    seen = set()
    for ent in entities:
        key = (ent["entity_type"], ent["text"])
        if key not in seen:
            unique.append({"entity_type": ent["entity_type"], "text": ent["text"]})
            seen.add(key)
    return entities, unique


@dataclass(frozen=True)
class RedactionJob:
    """One PDF to anonymise: where it is, where the result goes, what to redact.

    Attributes:
        input_path: Path to the input PDF file.
        output_path: Path to save the anonymised PDF.
        replacements: Mapping of target text to entity type.
            E.g. {"Bob": "person", "NL91ABNA": "iban"}.
        private_key: Private key for encrypting PII entities.
        entity_masks: Custom masks for entity types.
        incremental_save: If True, save changes incrementally to the PDF.
    """

    input_path: str
    output_path: str
    replacements: Dict[str, str]
    private_key: str
    entity_masks: Optional[Dict[str, str]] = None
    incremental_save: bool = False

    def redactions(self) -> Iterator["_Redaction"]:
        """Yield one redaction per replacement, with its mask and keys."""
        hashed_key = hashlib.sha256(self.private_key.encode()).digest()
        masks = {**_DEFAULT_ENTITY_MASK, **(self.entity_masks or {})}
        for target, entity_type in self.replacements.items():
            yield _Redaction(
                target=target,
                entity_type=entity_type,
                mask=masks.get(entity_type, f"[{entity_type.upper()}]"),
                hashed_key=hashed_key,
                private_key=self.private_key,
            )


def anonymize_pdf(job: RedactionJob) -> List[_Occurrence]:
    """Anonymise ``job.input_path`` and write to ``job.output_path``.

    Returns:
        List[dict]: List of occurrences with metadata about each redaction.
    """
    doc: pymupdf.Document = pymupdf.open(job.input_path)
    occurrences: List[_Occurrence] = []
    for redaction in job.redactions():
        for hit in _hits(doc, redaction.target):
            record = {"id": f"ann{len(occurrences)}", **_record(hit, redaction)}
            occurrences.append(record)  # type: ignore[arg-type]
            _redact_rect(hit, redaction)
    doc.save(job.output_path, incremental=job.incremental_save)
    _embed_occurrences_xmp(job.output_path, occurrences)
    return occurrences


@dataclass(frozen=True)
class _Redaction:
    """One text to redact, with its mask and the keys its record is sealed with."""

    target: str
    entity_type: str
    mask: str
    hashed_key: bytes
    private_key: str

    def ascii_target(self) -> str:
        """Return the target with non-ASCII characters dropped, for logging."""
        return self.target.encode("utf-8", errors="ignore").decode(
            "ascii", errors="ignore"
        )


@dataclass(frozen=True)
class _Hit:
    """One place a target text was found."""

    page: pymupdf.Page  # type: ignore[valid-type]
    page_idx: int
    rect: pymupdf.Rect


def _hits(doc: pymupdf.Document, target: str) -> Iterator[_Hit]:
    """Yield every place the target occurs, page by page."""
    for page_idx, page in enumerate(doc):  # type: ignore
        for r in page.search_for(target):
            yield _Hit(page=page, page_idx=page_idx, rect=r)


def _record(hit: _Hit, redaction: _Redaction) -> dict:
    """Return the record of one occurrence, with its text encrypted.

    It is taken before redaction, so the coordinates refer to the original.
    """
    r = hit.rect
    return {
        "page": hit.page_idx + 1,
        "rect": (r.x0, r.y0, r.x1, r.y1),
        "entity_type": redaction.entity_type,
        "entity_mask": redaction.mask,
        "encrypted_entity": encrypt_entity(
            data=redaction.target.encode("utf-8"), key=redaction.hashed_key
        ),
        "key_fingerprint": get_fingerprint(data=redaction.private_key),
    }


def _redact_rect(hit: _Hit, redaction: _Redaction) -> None:
    """Redact one rectangle with the mask in the font size found there.

    A failed redaction is logged and skipped; its occurrence stays recorded.
    """
    font_size, font_name = extract_font_details(hit)
    target = redaction.ascii_target()
    logging.debug(
        f"Found target target='{target}with font size {font_size} and font name {font_name}"
    )
    try:
        hit.page.add_redact_annot(  # type: ignore[attr-defined]
            hit.rect, fill=(1, 1, 1), text=redaction.mask, fontsize=int(font_size)
        )
        hit.page.apply_redactions()  # type: ignore[attr-defined]
    except Exception as e:
        logging.error(
            f"Failed to add redaction for target='{target} on page {hit.page_idx + 1}: {e}"
        )
        return
    logging.debug(f"Added redaction for target='{target}' on page {hit.page_idx + 1}.")


def extract_font_details(hit: _Hit) -> Tuple[int, str]:
    """Extract font size and name from the text span at the hit.

    The first intersecting span of each text line is taken, so the last line
    with one wins. Without any, the defaults are 11 and Helvetica.

    Returns:
        Tuple[int, str]: Tuple containing font size and font name.
    """
    font_size, font_name = 11, "Helvetica"
    for line in _text_lines(hit):
        span = next(
            (
                s
                for s in line.get("spans", [])
                if hit.rect.intersects(pymupdf.Rect(s["bbox"]))
            ),
            None,
        )
        if span is not None:
            font_size = span.get("size", font_size)
            font_name = span.get("font", font_name)
    return font_size, font_name


def _text_lines(hit: _Hit) -> list[dict]:
    """Return the text lines of the hit's page, or none when they cannot be read."""
    try:
        blocks = hit.page.get_text("dict")["blocks"]  # type: ignore[attr-defined]
    except Exception as e:
        if "font" in str(e):
            logging.warning(
                f"Could not determine font for page {hit.page_idx + 1}: {e}"
            )
        return []
    return [line for block in blocks for line in block.get("lines", [])]


def extract_annotations(
    input_path: str, *, decryption_key: Optional[bytes] = None
) -> List[dict]:
    """Return list of dictionaries parsed from XMP.

    If *decryption_key* is supplied, the function will attempt to decrypt the
    ``EncryptedEntity`` field of each record and add ``entity`` (plaintext).
    """
    logging.debug(f"Extracting annotations from {input_path}")
    xmp_xml = _read_xmp_packet(input_path)
    if xmp_xml is None:
        return []

    # Try multiple extraction methods for maximum compatibility
    occurrences = try_all_extraction_methods(
        XmpSource(xmp_xml=xmp_xml, decryption_key=decryption_key)
    )
    if occurrences:
        logging.debug(f"Found {len(occurrences)} occurrences in XMP metadata")
        return occurrences
    logging.debug("No annotations found in XMP with any extraction method")
    return []


def _read_xmp_packet(input_path: str) -> Optional[str]:
    """Return the XMP packet of a PDF without a byte order mark.

    None when the PDF cannot be read or has no metadata stream.
    """
    try:
        with pikepdf.Pdf.open(input_path) as pdf:
            if "/Metadata" not in pdf.Root:
                logging.debug("No metadata found in PDF")
                return None
            # Use errors='ignore' to handle any problematic characters
            xmp_xml = pdf.Root.Metadata.read_bytes().decode("utf-8", errors="ignore")
    except Exception as e:
        logging.error(f"Failed to open PDF or read metadata: {e}")
        return None

    # Remove any byte order mark that might cause issues
    xmp_xml = xmp_xml.removeprefix("\ufeff")

    safe_preview = "".join(c for c in xmp_xml[:200] if ord(c) < 128)
    logging.debug(f"Raw XMP content preview: {safe_preview}...")
    return xmp_xml


@dataclass(frozen=True)
class XmpSource:
    """An XMP packet, with the key and header to decrypt its entities."""

    xmp_xml: str
    decryption_key: Optional[bytes] = None
    header: bytes = b"header"


def try_all_extraction_methods(source: XmpSource) -> List[dict]:
    """Try all available methods to extract occurrences from XMP XML.

    The readers run in order of preference and the first non-empty result wins:
        - AnnotationData element, with or without CDATA,
          fn: retrieve_occurrences_xmp_from_cdata
        - Attribute-style extraction, fn: retrieve_occurrences_from_xmp_attributes
        - Old format with multiple Description elements,
          fn: retrieve_custom_properties_from_xmp
        - JSON pattern search, fn: retrieve_json_occurrencesfrom_xmp

    Args:
        source (XmpSource): the XMP packet and the key to decrypt entities with.

    Returns:
        List[dict]: the occurrences found, or an empty list.
    """
    for reader in _READERS:
        try:
            occurrences = reader(source)
        except Exception as e:
            logging.error(f"Failed to retrieve occurrences with {reader.__name__}: {e}")
            continue
        if occurrences:
            logging.debug(
                f"Found {len(occurrences)} occurrences with {reader.__name__}"
            )
            return occurrences
    return []


_CDATA_PATTERNS = (
    r"<custom:AnnotationData><!\[CDATA\[(.*?)\]\]></custom:AnnotationData>",
    r"<custom:AnnotationData>\s*<!\[CDATA\[(.*?)\]\]>\s*</custom:AnnotationData>",
    r"<custom:AnnotationData>(.*?)</custom:AnnotationData>",  # Non-CDATA version
)


def retrieve_occurrences_xmp_from_cdata(source: XmpSource) -> List[dict]:
    """Retrieve occurrences from XMP XML using CDATA patterns.

    Args:
        source (XmpSource): the XMP packet and the key to decrypt entities with.

    Returns:
        List[dict]: A list of occurrences extracted from the XMP XML.
    """
    for pattern in _CDATA_PATTERNS:
        match = re.search(pattern, source.xmp_xml, re.DOTALL)
        occurrences = _parsed_cdata(match.group(1).strip()) if match else []
        if occurrences:
            return _decrypt_records(occurrences, source)
    logging.debug("No occurrences found in XMP using CDATA patterns")
    return []


def _parsed_cdata(json_blob: str) -> list:
    """Return the occurrence list of a CDATA blob; broken JSON is logged as none."""
    try:
        return _occurrence_list(json_blob)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON from pattern match: {e}")
        logging.debug(f"JSON data preview: {json_blob[:100] or 'empty'}...")
        return []


def retrieve_occurrences_from_xmp_attributes(source: XmpSource) -> List[dict]:
    """Retrieve occurrences from XMP XML using attribute pattern.

    Args:
        source (XmpSource): the XMP packet and the key to decrypt entities with.

    Returns:
        List[dict]: A list of occurrences extracted from the XMP XML.
    """
    value = _attribute_value(source.xmp_xml, "custom:AnnotationData")
    if value is None:
        return []
    try:
        occurrences = _occurrence_list(_unescape_attribute(value))
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON from attribute: {e}")
        return []
    return _decrypt_records(occurrences, source)


def _attribute_value(xml: str, name: str) -> Optional[str]:
    """Return the raw value of the first ``name="..."`` attribute, or None."""
    marker = f'{name}="'
    start = xml.find(marker)
    if start == -1:
        return None
    start += len(marker)
    end = xml.find('"', start)
    return None if end == -1 else xml[start:end]


def _unescape_attribute(value: str) -> str:
    """Return an XML attribute value with its entities, ``&quot;`` included, unescaped."""
    return saxutils.unescape(value, {"&quot;": '"'})


def retrieve_custom_properties_from_xmp(source: XmpSource) -> List[dict]:
    """Retrieve custom properties from XMP XML using regex.

    Args:
        source (XmpSource): the XMP packet and the key to decrypt entities with.

    Returns:
        List[dict]: A list of dictionaries containing custom properties extracted from the XMP XML.
    """
    tag_re = re.compile(r"<rdf:Description([^>]*)/>", re.DOTALL)
    prop_re = re.compile(r"custom:([A-Za-z_]+)=\"([^\"]*)\"")

    annotations: List[dict] = []
    for m in tag_re.finditer(source.xmp_xml):
        props = {k: _unescape_attribute(v) for k, v in prop_re.findall(m.group(1))}
        if props:  # Only add if we found properties
            annotations.append(props)
    return _decrypt_records(annotations, source)


def retrieve_json_occurrencesfrom_xmp(source: XmpSource) -> List[dict]:
    """Retrieve occurrences from XMP XML using a JSON pattern.

    Args:
        source (XmpSource): the XMP packet and the key to decrypt entities with.

    Returns:
        List[dict]: A list of occurrences extracted from the XMP XML.
    """
    match = re.search(r'\{"occurrences":\s*\[(.*?)\]\}', source.xmp_xml, re.DOTALL)
    if not match:
        return []
    try:
        # Reconstruct the full JSON string
        occurrences = _occurrence_list(f'{{"occurrences": [{match.group(1)}]}}')
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON from pattern search: {e}")
        return []
    return _decrypt_records(occurrences, source)


_READERS = (
    retrieve_occurrences_xmp_from_cdata,
    retrieve_occurrences_from_xmp_attributes,
    retrieve_custom_properties_from_xmp,
    retrieve_json_occurrencesfrom_xmp,
)


def _occurrence_list(json_blob: str) -> list:
    """Return the ``occurrences`` list of a JSON blob, or an empty list.

    Raises:
        json.JSONDecodeError: when the blob is not JSON.
    """
    data = json.loads(json_blob)
    if not isinstance(data, dict):
        return []
    occurrences: list = data.get("occurrences") or []
    return occurrences


def _decrypt_records(records: list, source: XmpSource) -> list:
    """Add the plaintext ``entity`` to every record that holds a ciphertext.

    Without a decryption key the records are returned unchanged.
    """
    if not source.decryption_key:
        return records
    for record in records:
        if "encrypted_entity" in record:
            record["entity"] = _decrypt_or_none(record["encrypted_entity"], source)
    return records


def _decrypt_or_none(ciphertext: str, source: XmpSource) -> Optional[str]:
    """Return the decrypted text, or None when it does not decrypt."""
    try:
        plaintext = decrypt_entity(
            ciphertext, source.decryption_key or b"", source.header
        )
    except Exception as e:
        logging.error(f"Failed to decrypt entity: {e}")
        return None
    return plaintext.decode("utf-8", errors="replace")


# XMP packet that holds the occurrences as one JSON blob in a CDATA section.
_XMP_PACKET = """<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:custom="http://example.com/custom/">
  <rdf:Description rdf:about="">
    <custom:AnnotationData><![CDATA[{json_blob}]]></custom:AnnotationData>
  </rdf:Description>
</rdf:RDF>
<?xpacket end='w'?>"""


def _embed_occurrences_xmp(pdf_path: str, occs: List[_Occurrence]) -> None:
    """Replace the PDF's /Metadata with an XMP packet holding the occurrences.

    A failure is logged, not raised.
    """
    # ASCII-only JSON avoids Unicode issues in the packet.
    json_blob = json.dumps(
        {"occurrences": [_plain_occurrence(occ) for occ in occs]}, ensure_ascii=True
    )
    xmp = _XMP_PACKET.format(json_blob=json_blob)
    logging.debug(f"XMP metadata preview (first 200 chars): {xmp[:200]}...")
    try:
        with pikepdf.Pdf.open(pdf_path, allow_overwriting_input=True) as pdf:
            pdf.Root.Metadata = pdf.make_stream(xmp.encode("utf-8"))
            pdf.save(pdf_path)
            logging.debug(
                f"Embedded {len(occs)} occurrences in XMP metadata for {pdf_path}"
            )
    except Exception as e:
        logging.error(f"Failed to embed XMP metadata: {e}")
        logging.error(f"XMP content preview: {xmp[:500]}...")


def _plain_occurrence(occ: _Occurrence) -> dict:
    """Return an occurrence with only standard Python types, in a fixed key order."""
    return {
        "id": str(occ.get("id", "")),
        "page": int(occ.get("page", 0)),
        "rect": [float(v) for v in occ.get("rect", (0, 0, 0, 0))],
        "entity_type": str(occ.get("entity_type", "")),
        "entity_mask": str(occ.get("entity_mask", "")),
        "encrypted_entity": str(occ.get("encrypted_entity", "")),
        "key_fingerprint": str(occ.get("key_fingerprint", "")),
    }


if __name__ == "__main__":
    res = extract_annotations("test.pdf")
    print(res)
    exit(0)
    import argparse

    parser = argparse.ArgumentParser(description="PDF anonymiser util")
    parser.add_argument("input", help="Input PDF path")
    parser.add_argument("output", help="Output PDF path")
    parser.add_argument(
        "--mapping",
        nargs="*",
        metavar="S=TYPE",
        help="Replacement mapping e.g. 'Bob=person' 'NL91ABNA=iban'",
    )
    parser.add_argument(
        "--key",
        default="your_private_key_here",
        help="Private key for encryption (will be hashed to appropriate length)",
    )
    args = parser.parse_args()

    mapping = {}
    for pair in args.mapping or []:
        try:
            key, etype = pair.split("=", 1)
            mapping[key] = etype
        except ValueError:
            parser.error(f"Invalid mapping pair: {pair}")

    anonymize_pdf(RedactionJob(args.input, args.output, mapping, args.key))
    print("Done. Embedded", len(mapping), "PII item(s).")
