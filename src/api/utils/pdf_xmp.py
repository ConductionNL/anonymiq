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
from typing import Dict, List, Optional, Tuple

import pikepdf
import pymupdf
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.orm import Session

from src.api import database
from src.api.crud import create_document, create_tag
from src.api.dtos import DocumentAnonymizationRequest, DocumentDto, DocumentTagDto
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

        db_document = create_document(
            db,
            id=file_id,
            filename=file.filename or f"{file_id}.pdf",
            content_type=file.content_type or "application/pdf",
            source_path=str(source_path),
            anonymized_path=None,
            pii_entities=entities_json,
        )

        db_tags = []
        for tag_name in tags or []:
            tag_id = uuid.uuid4().hex
            tag = create_tag(db, tag_id, tag_name, file_id)
            db_tags.append(tag)

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


def analyze_and_anonymize_document(
    file_id: str,
    request_body: DocumentAnonymizationRequest,
    doc: database.Document,
    key: str,
) -> AnalysisAnonymizationResponse:
    """Analyze a document and anonymize identified PII entities.

    This function performs text extraction from a PDF document, analyzes it for PII entities,
    filters the entities based on the requested types to anonymize, and then creates
    an anonymized version of the PDF document.

    Args:
        file_id: The unique identifier for the document
        request_body: Request containing the PII entity types to anonymize
        doc: Database document model containing document information
        key: Private key used for encrypting PII entities

    Returns:
        AnalysisAnonymizationResponse:
            - selected_entities (list[dict]): Selected PII entities that were anonymized
            - output_path (Path): Path to the anonymized output file
            - status_text (str): Status message describing the result of the operation

    Raises:
        FileNotFoundError: If the source document cannot be found
        ValueError: If the anonymization process fails to produce a valid output file
    """
    analyzer = ModularTextAnalyzer()
    entities = _document_entities(doc, analyzer)
    selected = _select_entities(entities, request_body.pii_entities_to_anonymize)
    mapping = {e["text"]: e["entity_type"].lower() for e in selected}

    from src.api.config import settings

    anonym_dir = Path(settings.DATA_DIR) / "temp/anonymized"
    anonym_dir.mkdir(parents=True, exist_ok=True)
    out_path = anonym_dir / f"{file_id}.pdf"

    status_text = _anonymize_to_output(doc.source_path, out_path, mapping, key)
    return AnalysisAnonymizationResponse(
        selected_entities=selected,
        output_path=out_path,
        status_text=status_text,
    )


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


def _anonymize_to_output(
    source_path: str, out_path: Path, mapping: dict[str, str], key: str
) -> str:
    """Write the anonymized PDF and return the status text of the run."""
    try:
        logger.info(
            f"Starting anonymization for document {out_path.stem} with {len(mapping)} entities"
        )

        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file {source_path} not found")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        occurrences = anonymize_pdf(str(source_path), str(out_path), mapping, key)

        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            raise ValueError("Anonymization failed to produce valid output file")

        _log_occurrence_count(len(occurrences), len(mapping))
        return f"success ({len(occurrences)} entities processed)"
    except FileNotFoundError as exc:
        logger.error(f"File not found error: {exc}", exc_info=True)
        return f"failed: {exc}"
    except ValueError as exc:
        logger.error(f"Value error during anonymization: {exc}", exc_info=True)
        return f"failed: {exc}"
    except Exception as exc:  # pragma: no cover - depends on external libs
        logger.error(f"Unexpected error during anonymization: {exc}", exc_info=True)
        return f"failed: {exc}"


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


def anonymize_pdf(
    input_path: str,
    output_path: str,
    replacements: Dict[str, str],
    private_key: str,
    *,
    entity_masks: Optional[Dict[str, str]] = None,
    incremental_save: bool = False,
) -> List[_Occurrence]:
    """Anonymise *input_path* and write to *output_path*.

    Args:
        input_path (str): Path to the input PDF file.
        output_path (str): Path to save the anonymised PDF.
        replacements (Dict[str, str]): Mapping of target text to entity type.
            E.g. {"Bob": "person", "NL91ABNA": "iban"}.
        private_key (str): Private key for encrypting PII entities.
        entity_masks (Optional[Dict[str, str]]): Custom masks for entity types.
        incremental_save (bool): If True, save changes incrementally to the PDF.

    Returns:
        List[dict]: List of occurrences with metadata about each redaction.
    """
    hashed_key = hashlib.sha256(private_key.encode()).digest()
    masks = {**_DEFAULT_ENTITY_MASK, **(entity_masks or {})}

    doc: pymupdf.Document = pymupdf.open(input_path)
    occurrences: List[_Occurrence] = []

    for target, entity_type in replacements.items():
        redaction = _Redaction(
            target=target,
            entity_type=entity_type,
            mask=masks.get(entity_type, f"[{entity_type.upper()}]"),
            hashed_key=hashed_key,
            private_key=private_key,
        )
        for page_idx, page in enumerate(doc):  # type: ignore
            for r in page.search_for(target):
                occurrences.append(
                    _record_occurrence(f"ann{len(occurrences)}", page_idx, r, redaction)
                )
                _redact_rect(page, page_idx, r, redaction)

    doc.save(output_path, incremental=incremental_save)

    _embed_occurrences_xmp(output_path, occurrences)
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


def _record_occurrence(
    occurrence_id: str, page_idx: int, r: pymupdf.Rect, redaction: _Redaction
) -> _Occurrence:
    """Return the record of one occurrence, with its text encrypted.

    It is taken before redaction, so the coordinates refer to the original.
    """
    occ: _Occurrence = {  # type: ignore
        "id": occurrence_id,
        "page": page_idx + 1,
        "rect": (r.x0, r.y0, r.x1, r.y1),
        "entity_type": redaction.entity_type,
        "entity_mask": redaction.mask,
        "encrypted_entity": encrypt_entity(
            data=redaction.target.encode("utf-8"), key=redaction.hashed_key
        ),
        "key_fingerprint": get_fingerprint(data=redaction.private_key),
    }
    return occ


def _redact_rect(
    page: pymupdf.Page,  # type: ignore
    page_idx: int,
    r: pymupdf.Rect,
    redaction: _Redaction,
) -> None:
    """Redact one rectangle with the mask in the font size found there.

    A failed redaction is logged and skipped; its occurrence stays recorded.
    """
    font_size, font_name = extract_font_details(page_idx=page_idx, page=page, r=r)
    logging.debug(
        f"Found target target='{redaction.ascii_target()}"
        f"with font size {str(font_size)} and font name {str(font_name)}"
    )
    try:
        page.add_redact_annot(  # type: ignore
            r,
            fill=(1, 1, 1),
            text=redaction.mask,
            fontsize=int(font_size),
        )
        page.apply_redactions()  # type: ignore
    except Exception as e:
        target = redaction.target.encode("utf-8", errors="replace").decode(
            "ascii", errors="ignore"
        )
        logging.error(
            f"Failed to add redaction for target='{target} on page {page_idx + 1}: {e}"
        )
        return
    logging.debug(
        f"Added redaction for target='{redaction.ascii_target()}' on page {page_idx + 1}."
    )


def extract_font_details(
    page_idx: int,
    page: pymupdf.Page,  # type: ignore
    r: pymupdf.Rect,
) -> Tuple[int, str]:
    """Extract font size and name from the text span at the given rectangle.

    Args:
        page_idx (int): page index (0-based) in the document.
        page (pymupdf.Page): pymupdf Page object to extract text from.
        r (pymupdf.Rect): pymupdf Rect object representing the area to check.

    Returns:
        Tuple[int, str]: Tuple containing font size and font name.
    """
    font_size = 11  # Default font size if we can't determine
    font_name = "Helvetica"
    try:
        blocks = page.get_text("dict")["blocks"]  # type: ignore
    except Exception as e:
        if "font" in str(e):
            logging.warning(f"Could not determine font for page {page_idx + 1}: {e}")
        blocks = []  # Fallback to empty list if text extraction fails
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_rect = pymupdf.Rect(span["bbox"])
                if r.intersects(span_rect):
                    font_size = span.get("size", font_size)
                    font_name = span.get("font", font_name)
                    break
    return font_size, font_name  # For further processing/testing # type: ignore


def extract_annotations(
    input_path: str,
    *,
    decryption_key: Optional[bytes] = None,
    header: bytes = b"header",
) -> List[dict]:
    """Return list of dictionaries parsed from XMP.

    If *decryption_key* is supplied, the function will attempt to decrypt the
    ``EncryptedEntity`` field of each record and add ``entity`` (plaintext).
    """
    logging.debug(f"Extracting annotations from {input_path}")
    try:
        with pikepdf.Pdf.open(input_path) as pdf:
            if "/Metadata" not in pdf.Root:
                logging.debug("No metadata found in PDF")
                return []

            try:
                # Use errors='ignore' to handle any problematic characters
                xmp_xml = pdf.Root.Metadata.read_bytes().decode(
                    "utf-8", errors="ignore"
                )
            except UnicodeDecodeError:
                logging.error("Failed to decode XMP metadata as UTF-8")
                return []

            # Remove any byte order mark that might cause issues
            if xmp_xml.startswith("\ufeff"):
                xmp_xml = xmp_xml[1:]

            # Output debug info about the metadata structure
            safe_preview = "".join(c for c in xmp_xml[:200] if ord(c) < 128)
            logging.debug(f"Raw XMP content preview: {safe_preview}...")

    except Exception as e:
        logging.error(f"Failed to open PDF or read metadata: {e}")
        return []

    # Try multiple extraction methods for maximum compatibility
    occurrences: list[dict] = try_all_extraction_methods(
        decryption_key=decryption_key, header=header, xmp_xml=xmp_xml
    )
    if occurrences:
        logging.debug(f"Found {len(occurrences)} occurrences in XMP metadata")
        return occurrences
    else:
        # No annotations found with any method
        logging.debug("No annotations found in XMP with any extraction method")
        return []


def try_all_extraction_methods(
    decryption_key: bytes | None, header: bytes, xmp_xml: str
) -> List[dict]:
    """Try all available methods to extract occurrences from XMP XML.

    Wrapper function that attempts multiple extraction methods in order of preference.
    Includes:
        - CDATA section extraction (Method 1), fn: retrieve_occurrences_xmp_from_cdata
        - Attribute-style extraction (Method 2), fn: retrieve_occurrences_from_xmp_attributes
        - Old format with multiple Description elements (Method 3), fn: retrieve_custom_properties_from_xmp
        - JSON pattern search (Method 4), fn: retrieve_json_occurrencesfrom_xmp

    Args:
        decryption_key (bytes | None): _description_
        header (bytes): _description_
        xmp_xml (str): _description_

    Returns:
        List[dict]: _description_
    """
    # Method 1: Look for CDATA section with various patterns
    occurrences = retrieve_occurrences_xmp_from_cdata(decryption_key, header, xmp_xml)

    # return occurrences
    # Method 2: Try attribute-style extraction
    try:
        occurrences = retrieve_occurrences_from_xmp_attributes(
            decryption_key, header, xmp_xml
        )
        if occurrences:
            logging.debug(
                f"Found {len(occurrences)} occurrences using attribute pattern"
            )
            return occurrences
    except Exception as e:
        logging.error(f"Failed to retrieve occurrences from XMP attributes: {e}")

    # Method 3: Fallback to the old format with multiple Description elements
    # return occurrences
    try:
        annotations = retrieve_custom_properties_from_xmp(
            decryption_key, header, xmp_xml
        )
        if annotations:
            logging.debug(f"Found {len(annotations)} annotations using old format")
            return annotations

    except Exception as e:
        logging.error(f"Failed to retrieve custom properties from XMP: {e}")
        annotations = []

    # Method 4: Last resort - try to find JSON anywhere in the XMP
    # This is a bit risky but might catch JSON embedded in unusual ways
    try:
        occurrences = retrieve_json_occurrencesfrom_xmp(decryption_key, header, xmp_xml)
        if occurrences:
            logging.debug(
                f"Found {len(occurrences)} occurrences using JSON pattern search"
            )
        return occurrences
    except Exception as e:
        logging.error(f"Failed to retrieve JSON occurrences: {e}")

    return []


def retrieve_occurrences_xmp_from_cdata(
    decryption_key: bytes | None, header: bytes, xmp_xml: str
) -> List[dict]:
    """Retrieve occurrences from XMP XML using CDATA patterns. Method 1.

    Args:
        decryption_key (bytes | None): the key to decrypt entities, if available.
        header (bytes): the header used for decryption.
        xmp_xml (str): the XMP XML string to search for occurrences.

    Returns:
        List[dict]: A list of occurrences extracted from the XMP XML.
    """
    cdata_patterns = [
        r"<custom:AnnotationData><!\[CDATA\[(.*?)\]\]></custom:AnnotationData>",
        r"<custom:AnnotationData>\s*<!\[CDATA\[(.*?)\]\]>\s*</custom:AnnotationData>",
        r"<custom:AnnotationData>(.*?)</custom:AnnotationData>",  # Non-CDATA version
    ]

    for pattern in cdata_patterns:
        match = re.search(pattern, xmp_xml, re.DOTALL)
        if match:
            json_blob = match.group(1).strip()
            try:
                data = json.loads(json_blob)
                if isinstance(data, dict) and "occurrences" in data:
                    occurrences: list = data["occurrences"]
                    if occurrences:
                        logging.debug(
                            f"Found {len(occurrences)} occurrences using CDATA pattern"
                        )

                        # Process decryption if key is provided
                        if decryption_key:
                            for occ in occurrences:
                                if "encrypted_entity" in occ:
                                    try:
                                        plaintext = decrypt_entity(
                                            occ["encrypted_entity"],
                                            decryption_key,
                                            header,
                                        )

                                        occ["entity"] = plaintext.decode(
                                            "utf-8", errors="replace"
                                        )
                                        logging.debug(
                                            f"Decrypted entity for occurrence ID {occ.get('id', 'unknown')}"
                                        )
                                    except Exception as e:
                                        logging.error(f"Failed to decrypt entity: {e}")
                                        occ["entity"] = None
                        else:
                            logging.debug(
                                "No decryption key provided, skipping entity decryption"
                            )
                        return occurrences

            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse JSON from pattern match: {e}")
                blob_preview = json_blob[:100] if json_blob else "empty"
                logging.debug(f"JSON data preview: {blob_preview}...")
                continue  # Try the next pattern if this one fails
    logging.debug("No occurrences found in XMP using CDATA patterns")
    return []  # No occurrences found with any of the CDATA patterns


def retrieve_occurrences_from_xmp_attributes(
    decryption_key: bytes | None, header: bytes, xmp_xml: str
) -> List[dict]:
    """Retrieve occurrences from XMP XML using attribute pattern. Method 2.

    Args:
        decryption_key (bytes | None): the key to decrypt entities, if available.
        header (bytes): the header used for decryption.
        xmp_xml (str): the XMP XML string to search for occurrences.

    Returns:
        List[dict]: A list of occurrences extracted from the XMP XML.
    """
    attr_start = xmp_xml.find('custom:AnnotationData="')
    if attr_start != -1:
        attr_start += len('custom:AnnotationData="')
        attr_end = xmp_xml.find('"', attr_start)
        if attr_end != -1:
            json_blob = xmp_xml[attr_start:attr_end]
            # Unescape XML entities
            unescaped_json = saxutils.unescape(json_blob)

            try:
                data = json.loads(unescaped_json)
                if isinstance(data, dict) and "occurrences" in data:
                    occurrences: list = data["occurrences"]
                    if occurrences:
                        logging.debug(
                            f"Found {len(occurrences)} occurrences using attribute pattern"
                        )

                        # Process decryption if key is provided
                        if decryption_key:
                            for occ in occurrences:
                                if "encrypted_entity" in occ:
                                    try:
                                        plaintext = decrypt_entity(
                                            occ["encrypted_entity"],
                                            decryption_key,
                                            header,
                                        )
                                        occ["entity"] = plaintext.decode(
                                            "utf-8", errors="replace"
                                        )
                                    except Exception as e:
                                        logging.error(f"Failed to decrypt entity: {e}")
                                        occ["entity"] = None
                        return occurrences

            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse JSON from attribute: {e}")
    return []  # No occurrences found with this method


def retrieve_custom_properties_from_xmp(
    decryption_key: bytes | None, header: bytes, xmp_xml: str
) -> List[dict]:
    """Retrieve custom properties from XMP XML using regex. Method 3.

    Args:
        decryption_key (bytes | None): the key to decrypt entities, if available.
        header (bytes): the header used for decryption.
        xmp_xml (str): the XMP XML string to search for custom properties.

    Returns:
        List[dict]: A list of dictionaries containing custom properties extracted from the XMP XML.
    """
    tag_re = re.compile(r"<rdf:Description([^>]*)/>", re.DOTALL)
    prop_re = re.compile(r"custom:([A-Za-z]+)=\"([^\"]*)\"")

    annotations: List[dict] = []
    for m in tag_re.finditer(xmp_xml):
        attrs_block = m.group(1)
        props = {k: saxutils.unescape(v) for k, v in prop_re.findall(attrs_block)}
        if props:  # Only add if we found properties
            if decryption_key and "encrypted_entity" in props:
                try:
                    plaintext = decrypt_entity(
                        props["encrypted_entity"], decryption_key, header
                    )
                    props["entity"] = plaintext.decode("utf-8", errors="replace")
                except Exception:  # leave undecoded
                    props["entity"] = None  # type: ignore
            annotations.append(props)
    return annotations


def retrieve_json_occurrencesfrom_xmp(
    decryption_key: bytes | None, header: bytes, xmp_xml: str
) -> List[dict]:
    """Retrieve occurrences from XMP XML using a JSON pattern. Method 4.

    Args:
        decryption_key (bytes | None): the key to decrypt entities, if available.
        header (bytes): the header used for decryption.
        xmp_xml (str): the XMP XML string to search for occurrences.

    Returns:
        List[dict]: A list of occurrences extracted from the XMP XML.
    """
    json_pattern = r'\{"occurrences":\s*\[(.*?)\]\}'
    match = re.search(json_pattern, xmp_xml, re.DOTALL)
    if match:
        try:
            # Reconstruct the full JSON string
            json_blob = f'{{"occurrences": [{match.group(1)}]}}'
            data = json.loads(json_blob)
            occurrences: list = data.get("occurrences", [])
            if occurrences:
                logging.debug(
                    f"Found {len(occurrences)} occurrences using JSON pattern search"
                )

                # Process decryption if key is provided
                if decryption_key:
                    for occ in occurrences:
                        if "encrypted_entity" in occ:
                            try:
                                plaintext = decrypt_entity(
                                    occ["encrypted_entity"], decryption_key, header
                                )
                                occ["entity"] = plaintext.decode(
                                    "utf-8", errors="replace"
                                )
                            except Exception as e:
                                logging.error(f"Failed to decrypt entity: {e}")
                                occ["entity"] = None
                return occurrences
        except (json.JSONDecodeError, Exception) as e:
            logging.error(f"Failed to parse JSON from pattern search: {e}")

    return []  # No valid occurrences found


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

    anonymize_pdf(args.input, args.output, mapping, args.key)
    print("Done. Embedded", len(mapping), "PII item(s).")
