"""Characterization tests for the font size a redaction mask is written in.

The mask takes the size of the text span under the hit; when a line has
several, the first intersecting span of the last such line wins, and without
one the default is 11.
"""

import pymupdf
import pytest

from src.api.documents import pdf_xmp


def make_pdf(path, *lines: tuple[float, float, str]) -> str:
    doc = pymupdf.open()
    page = doc.new_page()
    for y, size, text in lines:
        page.insert_text((72, y), text, fontsize=size)
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def mask_sizes(monkeypatch: pytest.MonkeyPatch) -> list:
    sizes: list = []
    original = pymupdf.Page.add_redact_annot

    def spy(self, rect, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        sizes.append(kwargs.get("fontsize"))
        return original(self, rect, *args, **kwargs)

    monkeypatch.setattr(pymupdf.Page, "add_redact_annot", spy)
    return sizes


def test_the_mask_takes_the_size_of_the_span(tmp_path, mask_sizes: list) -> None:
    source = make_pdf(
        tmp_path / "in.pdf", (72, 20, "Jan groot"), (144, 8, "Piet klein")
    )
    pdf_xmp.anonymize_pdf(
        pdf_xmp.RedactionJob(source, str(tmp_path / "out.pdf"), {"Jan": "person", "Piet": "person"}, "k")
    )
    assert mask_sizes == [20, 8]


def test_an_unreadable_page_falls_back_to_size_11(
    tmp_path, mask_sizes: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_pdf(tmp_path / "in.pdf", (72, 20, "Jan groot"))
    original = pymupdf.Page.get_text

    def no_dict(self, option="text", *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        if option == "dict":
            raise RuntimeError("font table broken")
        return original(self, option, *args, **kwargs)

    monkeypatch.setattr(pymupdf.Page, "get_text", no_dict)
    pdf_xmp.anonymize_pdf(
        pdf_xmp.RedactionJob(source, str(tmp_path / "out.pdf"), {"Jan": "person"}, "k")
    )
    assert mask_sizes == [11]


def test_the_size_is_truncated_to_an_int(tmp_path, mask_sizes: list) -> None:
    source = make_pdf(tmp_path / "in.pdf", (72, 12.7, "Jan"))
    pdf_xmp.anonymize_pdf(
        pdf_xmp.RedactionJob(source, str(tmp_path / "out.pdf"), {"Jan": "person"}, "k")
    )
    assert mask_sizes == [12]


def test_font_details_of_a_hit_between_spans(tmp_path) -> None:
    """A rectangle touching two lines takes the span of the last one."""
    source = make_pdf(tmp_path / "in.pdf", (72, 20, "Jan"), (100, 9, "Jan"))
    doc = pymupdf.open(source)
    page = doc[0]
    both = pymupdf.Rect(0, 0, 600, 200)
    assert pdf_xmp.extract_font_details(pdf_xmp._Hit(page=page, page_idx=0, rect=both))[0] == 9
    nothing = pymupdf.Rect(500, 700, 510, 710)
    assert pdf_xmp.extract_font_details(pdf_xmp._Hit(page=page, page_idx=0, rect=nothing)) == (
        11,
        "Helvetica",
    )
    doc.close()
