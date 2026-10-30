"""Characterization tests for restoring redacted text from the XMP records.

``process_anonymized_pdf_to_deanonymize`` writes each record's plaintext back
over its rectangle; a record it cannot place or decrypt is refused.
"""

import hashlib
import json

import pikepdf
import pymupdf
import pytest

from src.api.documents import pdf_xmp
from src.api.documents.crypto import aes_gcm_encrypt

KEY = "secret"


def record(text: str, page: object = 1, rect: object = None) -> dict:
    hashed = hashlib.sha256(KEY.encode()).digest()
    return {
        "id": "ann0",
        "page": page,
        "rect": [72.0, 60.0, 200.0, 80.0] if rect is None else rect,
        "entity_type": "person",
        "entity_mask": "[PERSON]",
        "encrypted_entity": aes_gcm_encrypt(text.encode(), hashed),
        "key_fingerprint": "fp",
    }


def pdf_with_records(tmp_path, *records: dict, pages: int = 1) -> str:
    path = tmp_path / "anon.pdf"
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page().insert_text((72, 300), "vaste tekst")
    doc.save(str(path))
    doc.close()
    blob = json.dumps({"occurrences": list(records)})
    xmp = (
        "<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>\n"
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:custom="http://example.com/custom/"><rdf:Description rdf:about="">'
        f"<custom:AnnotationData><![CDATA[{blob}]]></custom:AnnotationData>"
        "</rdf:Description></rdf:RDF>\n<?xpacket end='w'?>"
    )
    with pikepdf.Pdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.Root.Metadata = pdf.make_stream(xmp.encode())
        pdf.save(path)
    return str(path)


def restored_text(tmp_path, *records: dict, pages: int = 1) -> list[str]:
    doc = pdf_xmp.process_anonymized_pdf_to_deanonymize(
        pdf_with_records(tmp_path, *records, pages=pages), KEY
    )
    texts = [page.get_text() for page in doc]
    doc.close()
    return texts


def test_the_plaintext_is_written_over_its_rectangle(tmp_path) -> None:
    [text] = restored_text(tmp_path, record("Jan Jansen"))
    assert "Jan Jansen" in text
    assert "vaste tekst" in text


def test_a_record_on_page_two(tmp_path) -> None:
    texts = restored_text(tmp_path, record("Jan Jansen", page="2"), pages=2)
    assert "Jan Jansen" not in texts[0]
    assert "Jan Jansen" in texts[1]


@pytest.mark.parametrize(
    "rect",
    [
        "[72.0, 60.0, 200.0, 80.0]",
        "72,60,200,80",
        (72, 60, 200, 80),
    ],
    ids=["json-string", "comma-string", "tuple"],
)
def test_a_rect_in_another_form_is_placed(tmp_path, rect: object) -> None:
    [text] = restored_text(tmp_path, record("Jan Jansen", rect=rect))
    assert "Jan Jansen" in text


@pytest.mark.parametrize(
    "bad",
    [
        {"page": 0},
        {"page": 3},
        {"page": "een"},
        {"rect": "72,60,200"},
        {"rect": [72.0, 60.0, 200.0]},
        {"rect": "geen getallen"},
        {"rect": 72},
    ],
    ids=[
        "page-zero",
        "page-past-end",
        "page-not-a-number",
        "rect-string-of-three",
        "rect-of-three",
        "rect-not-numbers",
        "rect-a-number",
    ],
)
def test_a_record_that_cannot_be_placed_is_refused(tmp_path, bad: dict) -> None:
    rec = record("Jan Jansen", page=bad.get("page", 1), rect=bad.get("rect"))
    good = dict(record("Piet"), id="ann1")
    with pytest.raises(pdf_xmp.UnusableRecordError, match="ann0"):
        restored_text(tmp_path, good, rec, pages=2)


def test_a_record_without_a_field_is_refused(tmp_path) -> None:
    rec = record("Jan Jansen")
    del rec["rect"]
    with pytest.raises(pdf_xmp.UnusableRecordError, match="ann0.*rect"):
        restored_text(tmp_path, rec)


def test_a_wrong_key_is_refused(tmp_path) -> None:
    """A record that does not decrypt is an error, not a blank redaction."""
    with pytest.raises(pdf_xmp.UnusableRecordError, match="does not decrypt"):
        pdf_xmp.process_anonymized_pdf_to_deanonymize(
            pdf_with_records(tmp_path, record("Jan Jansen")), "other"
        )


def test_a_pdf_without_records_is_refused(tmp_path) -> None:
    path = tmp_path / "plain.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    with pytest.raises(ValueError, match="No annotations found"):
        pdf_xmp.process_anonymized_pdf_to_deanonymize(path, KEY)


def test_a_text_that_does_not_fit_its_rect_is_refused(tmp_path) -> None:
    """A rectangle too small for the text is an error, not a blank redaction."""
    with pytest.raises(pdf_xmp.UnusableRecordError, match="does not fit"):
        restored_text(tmp_path, record("Jan Jansen", rect=[72.0, 60.0, 80.0, 62.0]))


@pytest.mark.parametrize("size", [6, 8, 11, 24])
def test_anonymize_then_restore_brings_the_text_back(tmp_path, size: int) -> None:
    """End to end at several font sizes: the original text is back on the page."""
    source, out = tmp_path / "in.pdf", tmp_path / "out.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Jan Jansen belt Piet", fontsize=size)
    doc.save(str(source))
    doc.close()
    pdf_xmp.anonymize_pdf(
        pdf_xmp.RedactionJob(str(source), str(out), {"Jan Jansen": "person"}, KEY)
    )
    restored = pdf_xmp.process_anonymized_pdf_to_deanonymize(out, KEY)
    text = restored[0].get_text()
    restored.close()
    assert "Jan Jansen" in text
    assert "belt Piet" in text
