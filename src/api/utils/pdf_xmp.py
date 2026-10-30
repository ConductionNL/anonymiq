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


def save_document_and_cleanup(
    anon_path: Path,
    deanon_path: Path,
    doc: pymupdf.Document,
    keep_temp_files: bool = False,
) -> BackgroundTasks:
    doc.save(str(deanon_path), incremental=False)
    doc.close()

    background = BackgroundTasks()
    if not keep_temp_files:
        background.add_task(lambda: anon_path.unlink(missing_ok=True))
        background.add_task(lambda: deanon_path.unlink(missing_ok=True))
    return background


def process_anonymized_pdf_to_deanonymize(
    anon_path: Path, key: str
) -> pymupdf.Document:
    hashed_key = hashlib.sha256(key.encode()).digest()

    annotations = extract_annotations(str(anon_path), decryption_key=hashed_key)
    print(f"Extracted {annotations=} from the PDF")

    if not annotations:
        raise ValueError(
            "No annotations found in the PDF. Ensure the document has been properly anonymized."
        )

    doc = pymupdf.open(str(anon_path))

    for ann in annotations:
        if "entity" in ann and "page" in ann and "rect" in ann:
            page_num = int(ann["page"]) - 1  # Pages are 0-indexed in PyMuPDF
            if 0 <= page_num < len(doc):
                page = doc[page_num]

                # Parse the rectangle coordinates
                rect = ann["rect"]
                if not isinstance(rect, list):
                    logging.error(
                        f"Invalid rectangle format: {rect}. Expected a list of coordinates."
                    )
                    continue
                if len(rect) == 4:
                    rect = pymupdf.Rect(*rect)

                    original_text = ann["entity"]
                    page.add_redact_annot(rect, fill=(1, 1, 1), text=original_text)  # type: ignore
                    page.apply_redactions()  # type: ignore
    return doc


async def create_temp_paths_and_save(file: UploadFile) -> Tuple[Path, Path]:
    """Create temporary paths for the uploaded file and save its content.

    Extracted from documents router to keep the code DRY.

    Args:
        file (UploadFile): The uploaded file to be processed. (fastapi UploadFile)

    Returns:
        Tuple[Path, Path]: A tuple containing the paths to the anonymized and deanonymized files.
    """
    content = await file.read()
    await file.close()

    from src.api.config import settings

    temp_dir = Path(settings.DATA_DIR) / "temp/deanonymized"
    temp_dir.mkdir(parents=True, exist_ok=True)

    process_id = uuid.uuid4().hex
    anon_path = temp_dir / f"{process_id}_anonymized.pdf"
    deanon_path = temp_dir / f"{process_id}_deanonymized.pdf"

    with open(anon_path, "wb") as f:
        f.write(content)
    return anon_path, deanon_path


async def upload_and_analyze_files(
    files: list[UploadFile], tags: Optional[list[str]], db: Session
) -> list[DocumentDto]:
    """Upload files, analyze them for PII entities, and store metadata in the database.

    Args:
        files (list[UploadFile]): List of files to be uploaded and analyzed.
        tags (list[str]): List of tags to be associated with the documents.
        db (Session): Database session for storing document metadata.

    Returns:
        _type_: list[DocumentDto]
    """
    docs: list[DocumentDto] = []

    for file in files:
        content = await file.read()
        await file.close()

        file_id = uuid.uuid4().hex
        from src.api.config import settings

        source_dir = Path(settings.DATA_DIR) / "temp/source"
        source_dir.mkdir(parents=True, exist_ok=True)
        source_path = source_dir / f"{file_id}.pdf"
        with open(source_path, "wb") as f:
            f.write(content)

        text = extract_text_from_pdf(source_path)

        entities, unique = await extract_unique_entities(text=text)

        # Convert entities to JSON string for database storage
        import json

        entities_json = json.dumps(entities) if entities else None

        db_document = save(
            db,
            database.Document(
                id=file_id,
                filename=file.filename or f"{file_id}.pdf",
                content_type=file.content_type or "application/pdf",
                source_path=str(source_path),
                anonymized_path=None,
                pii_entities=entities_json,
            ),
        )

        db_tags = [
            save(
                db,
                database.Tag(id=uuid.uuid4().hex, name=tag_name, document_id=file_id),
            )
            for tag_name in tags or []
        ]

        db_document._entities = entities

        stored_tags = [
            DocumentTagDto(id=str(tag.id), name=str(tag.name)) for tag in db_tags
        ]
        doc_meta = DocumentDto(
            id=file_id,
            filename=str(db_document.filename),
            content_type=str(db_document.content_type),
            uploaded_at=datetime.now(),  # Use current time for response
            tags=stored_tags,
            pii_entities=unique,
        )

        docs.append(doc_meta)
    return docs


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
    if xmp_xml.startswith("﻿"):
        xmp_xml = xmp_xml[1:]

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
        - Attribute-style extraction, fn: retrieve_occurrences_from_xmp_attributes
        - Old format with multiple Description elements,
          fn: retrieve_custom_properties_from_xmp
        - JSON pattern search, fn: retrieve_json_occurrencesfrom_xmp

    The CDATA reader (retrieve_occurrences_xmp_from_cdata) runs first, but its
    result is not used: the JSON pattern search reads the same CDATA blob.

    Args:
        source (XmpSource): the XMP packet and the key to decrypt entities with.

    Returns:
        List[dict]: the occurrences found, or an empty list.
    """
    retrieve_occurrences_xmp_from_cdata(source)
    for reader in _FALLBACK_READERS:
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
        if not match:
            continue
        json_blob = match.group(1).strip()
        try:
            occurrences = _occurrence_list(json_blob)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON from pattern match: {e}")
            logging.debug(f"JSON data preview: {json_blob[:100] or 'empty'}...")
            continue
        if occurrences:
            return _decrypt_records(occurrences, source)
    logging.debug("No occurrences found in XMP using CDATA patterns")
    return []


def retrieve_occurrences_from_xmp_attributes(source: XmpSource) -> List[dict]:
    """Retrieve occurrences from XMP XML using attribute pattern.

    Args:
        source (XmpSource): the XMP packet and the key to decrypt entities with.

    Returns:
        List[dict]: A list of occurrences extracted from the XMP XML.
    """
    marker = 'custom:AnnotationData="'
    attr_start = source.xmp_xml.find(marker)
    if attr_start == -1:
        return []
    attr_start += len(marker)
    attr_end = source.xmp_xml.find('"', attr_start)
    if attr_end == -1:
        return []
    try:
        occurrences = _occurrence_list(
            saxutils.unescape(source.xmp_xml[attr_start:attr_end])
        )
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON from attribute: {e}")
        return []
    return _decrypt_records(occurrences, source)


def retrieve_custom_properties_from_xmp(source: XmpSource) -> List[dict]:
    """Retrieve custom properties from XMP XML using regex.

    Args:
        source (XmpSource): the XMP packet and the key to decrypt entities with.

    Returns:
        List[dict]: A list of dictionaries containing custom properties extracted from the XMP XML.
    """
    tag_re = re.compile(r"<rdf:Description([^>]*)/>", re.DOTALL)
    prop_re = re.compile(r"custom:([A-Za-z]+)=\"([^\"]*)\"")

    annotations: List[dict] = []
    for m in tag_re.finditer(source.xmp_xml):
        props = {k: saxutils.unescape(v) for k, v in prop_re.findall(m.group(1))}
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


_FALLBACK_READERS = (
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


def _embed_occurrences_xmp(pdf_path: str, occs: List[_Occurrence]) -> None:
    """Create /Metadata with one <rdf:Description> element per occurrence."""
    # Convert occurrences to JSON for embedding in CDATA section
    import json

    # Format the occurrences into a proper dictionary
    # Make sure to convert all values to standard Python types
    safe_occs = []
    for occ in occs:
        # Create a clean dictionary from the occurrence
        safe_occ = {
            "id": str(occ.get("id", "")),
            "page": int(occ.get("page", 0)),
            "rect": [float(v) for v in occ.get("rect", (0, 0, 0, 0))],
            "entity_type": str(occ.get("entity_type", "")),
            "entity_mask": str(occ.get("entity_mask", "")),
            "encrypted_entity": str(occ.get("encrypted_entity", "")),
            "key_fingerprint": str(occ.get("key_fingerprint", "")),
        }
        safe_occs.append(safe_occ)

    occurrences_dict = {"occurrences": safe_occs}

    # Convert to JSON string - ensure ASCII encoding to avoid Unicode issues
    json_blob = json.dumps(occurrences_dict, ensure_ascii=True)

    # Use a standard packet ID as seen in the working example
    xmp = f"""<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:custom="http://example.com/custom/">
  <rdf:Description rdf:about="">
    <custom:AnnotationData><![CDATA[{json_blob}]]></custom:AnnotationData>
  </rdf:Description>
</rdf:RDF>
<?xpacket end='w'?>"""

    # Debug output to help diagnose any issues
    logging.debug(f"XMP metadata preview (first 200 chars): {xmp[:200]}...")

    # First clear any existing metadata to avoid conflicts
    try:
        # Try to open and clean up the PDF before adding new metadata
        with pikepdf.Pdf.open(pdf_path, allow_overwriting_input=True) as pdf:
            # Create a clean XMP metadata object
            pdf.Root.Metadata = pdf.make_stream(xmp.encode("utf-8"))
            # Save without any additional options
            pdf.save(pdf_path)
            logging.debug(
                f"Embedded {len(occs)} occurrences in XMP metadata for {pdf_path}"
            )
    except Exception as e:
        logging.error(f"Failed to embed XMP metadata: {e}")
        # Print the first part of the XMP for debugging
        logging.error(f"XMP content preview: {xmp[:500]}...")


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
