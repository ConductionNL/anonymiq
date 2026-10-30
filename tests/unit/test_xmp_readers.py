"""Characterization tests for reading occurrences back from a PDF's XMP packet.

``extract_annotations`` tries four readers in turn (CDATA element, attribute,
self-closing Description elements, bare JSON search). These tests pin what it
returns for each layout, with and without a key, so the readers can be
restructured without changing the result.
"""

import hashlib
import json
import xml.sax.saxutils as saxutils
from pathlib import Path

import pikepdf
import pymupdf
import pytest

from src.api.utils import pdf_xmp
from src.api.utils.crypto import aes_gcm_encrypt

KEY = hashlib.sha256(b"secret").digest()
WRONG_KEY = hashlib.sha256(b"other").digest()


def occurrence(text: str, occ_id: str = "ann0") -> dict:
    return {
        "id": occ_id,
        "page": 1,
        "rect": [1.0, 2.0, 3.0, 4.0],
        "entity_type": "person",
        "entity_mask": "[PERSON]",
        "encrypted_entity": aes_gcm_encrypt(text.encode("utf-8"), KEY),
        "key_fingerprint": "fp",
    }


def packet(body: str) -> str:
    return (
        "<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>\n"
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"\n'
        '         xmlns:custom="http://example.com/custom/">\n'
        f"{body}\n</rdf:RDF>\n<?xpacket end='w'?>"
    )


def pdf_with_xmp(tmp_path: Path, xmp: str | None) -> str:
    path = tmp_path / "doc.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    if xmp is not None:
        with pikepdf.Pdf.open(path, allow_overwriting_input=True) as pdf:
            pdf.Root.Metadata = pdf.make_stream(xmp.encode("utf-8"))
            pdf.save(path)
    return str(path)


def blob(*occs: dict) -> str:
    return json.dumps({"occurrences": list(occs)}, ensure_ascii=True)


def cdata_xmp(*occs: dict) -> str:
    return packet(
        '  <rdf:Description rdf:about="">\n'
        f"    <custom:AnnotationData><![CDATA[{blob(*occs)}]]></custom:AnnotationData>\n"
        "  </rdf:Description>"
    )


def plain_element_xmp(*occs: dict) -> str:
    return packet(
        '  <rdf:Description rdf:about="">\n'
        f"    <custom:AnnotationData>{blob(*occs)}</custom:AnnotationData>\n"
        "  </rdf:Description>"
    )


def attribute_xmp(*occs: dict) -> str:
    escaped = saxutils.escape(blob(*occs), {'"': "&quot;"})
    return packet(
        f'  <rdf:Description rdf:about="" custom:AnnotationData="{escaped}"/>'
    )


def description_xmp(*records: dict) -> str:
    rows = []
    for rec in records:
        attrs = " ".join(
            f'custom:{k}="{saxutils.escape(str(v), {chr(34): "&quot;"})}"'
            for k, v in rec.items()
        )
        rows.append(f'  <rdf:Description rdf:about="" {attrs}/>')
    return packet("\n".join(rows))


def read(tmp_path: Path, xmp: str | None, key: bytes | None = KEY) -> list[dict]:
    return pdf_xmp.extract_annotations(pdf_with_xmp(tmp_path, xmp), decryption_key=key)


@pytest.mark.parametrize(
    "layout", [cdata_xmp, plain_element_xmp], ids=lambda f: f.__name__
)
def test_json_layouts_are_read_and_decrypted(tmp_path, layout) -> None:
    """Each JSON layout yields the occurrences with the plaintext added."""
    first, second = occurrence("Jan Jansen"), occurrence("Piet", "ann1")
    found = read(tmp_path, layout(first, second))
    assert found == [
        {**first, "entity": "Jan Jansen"},
        {**second, "entity": "Piet"},
    ]


@pytest.mark.parametrize(
    "layout", [cdata_xmp, plain_element_xmp], ids=lambda f: f.__name__
)
def test_without_a_key_nothing_is_decrypted(tmp_path, layout) -> None:
    """With no key the occurrences come back as stored."""
    occ = occurrence("Jan Jansen")
    assert read(tmp_path, layout(occ), key=None) == [occ]


def test_a_wrong_key_leaves_the_entity_empty(tmp_path) -> None:
    """An occurrence that does not decrypt gets ``entity`` None."""
    occ = occurrence("Jan Jansen")
    assert read(tmp_path, cdata_xmp(occ), key=WRONG_KEY) == [{**occ, "entity": None}]


def test_an_attribute_blob_with_quotes_is_read_and_decrypted(tmp_path) -> None:
    """The attribute reader unescapes ``&quot;``, so its JSON parses."""
    first, second = occurrence("Jan Jansen"), occurrence("Piet", "ann1")
    assert read(tmp_path, attribute_xmp(first, second)) == [
        {**first, "entity": "Jan Jansen"},
        {**second, "entity": "Piet"},
    ]


def test_a_description_property_with_quotes_is_unescaped(tmp_path) -> None:
    """A Description property value gets its ``&quot;`` back as a quote."""
    found = read(tmp_path, description_xmp({"id": 'ann "0" & co'}))
    assert found == [{"id": 'ann "0" & co'}]


def test_an_occurrence_without_ciphertext_is_returned_as_is(tmp_path) -> None:
    """Only records with ``encrypted_entity`` are decrypted."""
    occ = {"id": "ann0", "page": 1}
    assert read(tmp_path, cdata_xmp(occ)) == [occ]


def test_description_elements_are_read_as_string_properties(tmp_path) -> None:
    """The old layout gives one dict of string properties per element.

    Property names with an underscore are not matched, so
    ``encrypted_entity`` is dropped and nothing is decrypted.
    """
    occ = occurrence("Jan Jansen")
    record = {"id": "ann0", "page": "1", "encrypted_entity": occ["encrypted_entity"]}
    found = read(tmp_path, description_xmp(record, {"id": "ann1", "page": "2"}))
    assert found == [{"id": "ann0", "page": "1"}, {"id": "ann1", "page": "2"}]


def test_a_description_record_without_ciphertext(tmp_path) -> None:
    """A record without ``encrypted_entity`` gets no ``entity`` either."""
    found = read(tmp_path, description_xmp({"id": "ann0"}), key=WRONG_KEY)
    assert found == [{"id": "ann0"}]


def test_a_blob_with_more_keys_than_occurrences_is_read(tmp_path) -> None:
    """The CDATA reader parses the whole blob, so keys after the occurrence
    list do not hide the occurrences."""
    occ = occurrence("Jan Jansen")
    body = json.dumps({"occurrences": [occ], "version": 1})
    xmp = packet(
        '  <rdf:Description rdf:about="">\n'
        f"    <custom:AnnotationData><![CDATA[{body}]]></custom:AnnotationData>\n"
        "  </rdf:Description>"
    )
    assert read(tmp_path, xmp) == [{**occ, "entity": "Jan Jansen"}]


def test_a_cdata_blob_wins_over_a_json_search_elsewhere(tmp_path) -> None:
    """The CDATA element is read first; a bare JSON blob later in the packet
    is not used when the element holds occurrences."""
    first, other = occurrence("Jan Jansen"), occurrence("Piet", "ann1")
    xmp = packet(
        '  <rdf:Description rdf:about="">\n'
        f"    <custom:AnnotationData><![CDATA[{json.dumps({'occurrences': [first], 'v': 1})}]]>"
        "</custom:AnnotationData>\n"
        f"    <custom:Other>{blob(other)}</custom:Other>\n"
        "  </rdf:Description>"
    )
    assert read(tmp_path, xmp) == [{**first, "entity": "Jan Jansen"}]


def test_an_empty_occurrence_list_is_not_found(tmp_path) -> None:
    assert read(tmp_path, cdata_xmp()) == []


def test_broken_json_is_not_found(tmp_path) -> None:
    xmp = packet(
        '  <rdf:Description rdf:about="">\n'
        '    <custom:AnnotationData><![CDATA[{"occurrences": [}]]></custom:AnnotationData>\n'
        "  </rdf:Description>"
    )
    assert read(tmp_path, xmp) == []


def test_a_byte_order_mark_is_ignored(tmp_path) -> None:
    occ = occurrence("Jan Jansen")
    assert read(tmp_path, "﻿" + cdata_xmp(occ)) == [{**occ, "entity": "Jan Jansen"}]


def test_a_pdf_without_metadata_has_no_annotations(tmp_path) -> None:
    assert read(tmp_path, None) == []


def test_a_file_that_is_not_a_pdf_has_no_annotations(tmp_path) -> None:
    path = tmp_path / "not.pdf"
    path.write_bytes(b"not a pdf")
    assert pdf_xmp.extract_annotations(str(path), decryption_key=KEY) == []


def test_round_trip_through_anonymize_pdf(tmp_path) -> None:
    """What anonymize_pdf embeds, extract_annotations reads back in plaintext."""
    source = tmp_path / "in.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Jan Jansen belt Piet")
    doc.save(str(source))
    doc.close()
    out = str(tmp_path / "out.pdf")
    pdf_xmp.anonymize_pdf(
        pdf_xmp.RedactionJob(str(source), out, {"Jan Jansen": "person"}, "secret")
    )
    found = pdf_xmp.extract_annotations(out, decryption_key=KEY)
    assert [(o["id"], o["entity"], o["entity_type"]) for o in found] == [
        ("ann0", "Jan Jansen", "person")
    ]
