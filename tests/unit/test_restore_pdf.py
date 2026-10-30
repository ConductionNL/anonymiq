"""Characterization tests for restoring redacted text from the XMP records.

``process_anonymized_pdf_to_deanonymize`` writes each record's plaintext back
over its rectangle; records it cannot place are skipped.
"""

import hashlib
import json

import pikepdf
import pymupdf
import pytest

from src.api.utils import pdf_xmp
from src.api.utils.crypto import aes_gcm_encrypt

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
    "bad",
    [
        {"page": 0},
        {"page": 3},
        {"rect": "72,60,200,80"},
        {"rect": [72.0, 60.0, 200.0]},
    ],
    ids=["page-zero", "page-past-end", "rect-not-a-list", "rect-of-three"],
)
def test_records_that_cannot_be_placed_are_skipped(tmp_path, bad: dict) -> None:
    rec = record("Jan Jansen", page=bad.get("page", 1), rect=bad.get("rect"))
    good = dict(record("Piet"), id="ann1")
    texts = restored_text(tmp_path, rec, good, pages=2)
    assert "Jan Jansen" not in "".join(texts)
    assert "Piet" in texts[0]


def test_a_record_without_a_field_is_skipped(tmp_path) -> None:
    rec = record("Jan Jansen")
    del rec["rect"]
    assert "Jan Jansen" not in restored_text(tmp_path, rec)[0]


def test_a_wrong_key_restores_nothing(tmp_path) -> None:
    """An undecryptable record still gets a blank redaction, with no text."""
    doc = pdf_xmp.process_anonymized_pdf_to_deanonymize(
        pdf_with_records(tmp_path, record("Jan Jansen")), "other"
    )
    text = doc[0].get_text()
    doc.close()
    assert "Jan Jansen" not in text
    assert "vaste tekst" in text


def test_a_pdf_without_records_is_refused(tmp_path) -> None:
    path = tmp_path / "plain.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    with pytest.raises(ValueError, match="No annotations found"):
        pdf_xmp.process_anonymized_pdf_to_deanonymize(path, KEY)
