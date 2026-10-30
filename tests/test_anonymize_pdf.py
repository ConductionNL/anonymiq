"""Characterization tests for pdf_xmp.anonymize_pdf."""

import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree

import pikepdf
import pymupdf

from src.api.documents import pdf_xmp
from src.api.documents.crypto import aes_gcm_decrypt, fingerprint_sha256


def make_pdf(path: Path, *pages: str) -> str:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return str(path)


def page_texts(path: str) -> list[str]:
    doc = pymupdf.open(path)
    texts = [page.get_text() for page in doc]
    doc.close()
    return texts


def embedded_occurrences(path: str) -> list[dict]:
    with pikepdf.open(path) as pdf:
        xmp = pdf.Root.Metadata.read_bytes().decode("utf-8")
    rdf = ElementTree.fromstring(re.sub(r"<\?xpacket[^>]*\?>", "", xmp).strip())
    node = rdf.find(".//{http://example.com/custom/}AnnotationData")
    return json.loads(node.text)["occurrences"]


def test_redacts_every_occurrence_and_records_it(tmp_path):
    source = make_pdf(
        tmp_path / "in.pdf", "Jan Jansen belt Jan Jansen", "IBAN NL91ABNA0417164300"
    )
    out = str(tmp_path / "out.pdf")

    occurrences = pdf_xmp.anonymize_pdf(
        pdf_xmp.RedactionJob(
            source,
            out,
            {"Jan Jansen": "person", "NL91ABNA0417164300": "iban", "Niemand": "person"},
            "secret",
        )
    )

    assert [o["id"] for o in occurrences] == ["ann0", "ann1", "ann2"]
    assert [o["page"] for o in occurrences] == [1, 1, 2]
    assert [o["entity_type"] for o in occurrences] == ["person", "person", "iban"]
    assert [o["entity_mask"] for o in occurrences] == ["[PERSON]", "[PERSON]", "[IBAN]"]
    assert list(occurrences[0].keys()) == [
        "id",
        "page",
        "rect",
        "entity_type",
        "entity_mask",
        "encrypted_entity",
        "key_fingerprint",
    ]
    assert all(
        o["key_fingerprint"] == fingerprint_sha256("secret") for o in occurrences
    )
    key = hashlib.sha256(b"secret").digest()
    assert aes_gcm_decrypt(occurrences[2]["encrypted_entity"], key) == (
        b"NL91ABNA0417164300"
    )
    assert len(occurrences[0]["rect"]) == 4

    texts = page_texts(out)
    assert "Jan Jansen" not in texts[0]
    assert "NL91ABNA0417164300" not in texts[1]
    assert [o["id"] for o in embedded_occurrences(out)] == ["ann0", "ann1", "ann2"]


def test_custom_and_unknown_masks(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", "Jan Jansen woont in Utrecht")
    out = str(tmp_path / "out.pdf")

    occurrences = pdf_xmp.anonymize_pdf(
        pdf_xmp.RedactionJob(
            source,
            out,
            {"Jan Jansen": "person", "Utrecht": "location"},
            "k",
            entity_masks={"person": "[NAAM]"},
        )
    )

    assert [o["entity_mask"] for o in occurrences] == ["[NAAM]", "[LOCATION]"]


def test_a_failed_redaction_is_still_recorded(monkeypatch, tmp_path):
    source = make_pdf(tmp_path / "in.pdf", "Jan Jansen")
    out = str(tmp_path / "out.pdf")

    def refuse(self, *args, **kwargs):
        raise RuntimeError("cannot redact")

    monkeypatch.setattr(pymupdf.Page, "add_redact_annot", refuse)

    occurrences = pdf_xmp.anonymize_pdf(pdf_xmp.RedactionJob(source, out, {"Jan Jansen": "person"}, "k"))

    assert [o["id"] for o in occurrences] == ["ann0"]
    assert "Jan Jansen" in page_texts(out)[0]


def test_nothing_found_writes_an_unchanged_copy(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", "Geen namen hier")
    out = str(tmp_path / "out.pdf")

    occurrences = pdf_xmp.anonymize_pdf(pdf_xmp.RedactionJob(source, out, {"Jan": "person"}, "k"))

    assert occurrences == []
    assert page_texts(out)[0].strip() == "Geen namen hier"
    assert embedded_occurrences(out) == []


def test_save_mode_is_passed_on(monkeypatch, tmp_path):
    source = make_pdf(tmp_path / "in.pdf", "Jan")
    out = str(tmp_path / "out.pdf")
    seen = {}
    original = pymupdf.Document.save

    def spy(self, filename, *args, **kwargs):
        seen["incremental"] = kwargs.get("incremental")
        return original(self, filename, *args, **kwargs)

    monkeypatch.setattr(pymupdf.Document, "save", spy)

    pdf_xmp.anonymize_pdf(
        pdf_xmp.RedactionJob(source, out, {"Jan": "person"}, "k", incremental_save=False)
    )

    assert seen["incremental"] is False
