"""Characterization tests for the document routes and what they store.

The NLP analyzer is replaced by a fake that finds one fixed name, so the
routes run end to end on real PDFs without a spaCy model or torch.
"""

import json
import uuid
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from src.api.config import settings
from src.api.database import AnonymizationEvent, Document, Tag
from src.api.dependencies import SessionLocal
from src.api.utils import pdf_xmp
from tests.unit.conftest import VALID_AUTH

NAME = "Jan Jansen"


class FakeAnalyzer:
    """Finds every occurrence of NAME as a PERSON entity."""

    def analyze_text(self, text: str) -> list[dict]:
        found, start = [], text.find(NAME)
        while start != -1:
            found.append(
                {
                    "entity_type": "PERSON",
                    "text": NAME,
                    "start": start,
                    "end": start + len(NAME),
                    "score": 0.85,
                }
            )
            start = text.find(NAME, start + 1)
        return found


@pytest.fixture(autouse=True)
def fake_analyzer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_xmp, "ModularTextAnalyzer", FakeAnalyzer)


def pdf_bytes(text: str) -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def upload(client: TestClient, text: str, tags: list[str] | None = None) -> dict:
    response = client.post(
        "/api/v1/documents/upload",
        auth=VALID_AUTH,
        data={"tags": tags or []},
        files={"files": ("brief.pdf", pdf_bytes(text), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    return response.json()["files"][0]


def stored(file_id: str) -> Document:
    with SessionLocal() as db:
        doc = db.get(Document, file_id)
        assert doc is not None
        db.expunge(doc)
        return doc


def events(file_id: str) -> list[tuple[str, int]]:
    with SessionLocal() as db:
        rows = db.query(AnonymizationEvent).filter_by(document_id=file_id).all()
        return [(e.status, e.time_taken) for e in rows]


def tag_names(file_id: str) -> list[str]:
    with SessionLocal() as db:
        return sorted(t.name for t in db.query(Tag).filter_by(document_id=file_id))


# --- upload -------------------------------------------------------------------


def test_upload_stores_the_document_entities_and_tags(client: TestClient) -> None:
    meta = upload(client, f"{NAME} belt {NAME}", tags=["a", "b"])
    assert meta["filename"] == "brief.pdf"
    assert meta["content_type"] == "application/pdf"
    assert meta["pii_entities"] == [{"entity_type": "PERSON", "text": NAME}]
    assert sorted(t["name"] for t in meta["tags"]) == ["a", "b"]

    doc = stored(meta["id"])
    assert len(meta["id"]) == 32
    assert doc.filename == "brief.pdf"
    assert doc.anonymized_path is None
    assert Path(doc.source_path).read_bytes().startswith(b"%PDF")
    assert [e["text"] for e in json.loads(doc.pii_entities or "[]")] == [NAME, NAME]
    assert tag_names(meta["id"]) == ["a", "b"]


def test_upload_without_entities_stores_none(client: TestClient) -> None:
    meta = upload(client, "niets bijzonders")
    assert meta["pii_entities"] == []
    assert meta["tags"] == []
    assert stored(meta["id"]).pii_entities is None


def test_upload_refuses_another_extension(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents/upload",
        auth=VALID_AUTH,
        files={"files": ("brief.txt", b"x", "text/plain")},
    )
    assert response.status_code == 422
    assert "pdf" in response.json()["detail"]


# --- metadata -----------------------------------------------------------------


def test_metadata_without_details(client: TestClient) -> None:
    meta = upload(client, NAME, tags=["t"])
    response = client.get(f"/api/v1/documents/{meta['id']}/metadata", auth=VALID_AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == meta["id"]
    assert body["filename"] == "brief.pdf"
    assert body["pii_entities"] == []
    assert [t["name"] for t in body["tags"]] == ["t"]


def test_metadata_details_come_from_the_stored_entities(client: TestClient) -> None:
    meta = upload(client, f"{NAME} en {NAME}")
    with SessionLocal() as db:
        doc = db.get(Document, meta["id"])
        assert doc is not None
        doc.pii_entities = json.dumps(
            [
                {"entity_type": "PERSON", "text": "A"},
                {"entity_type": "PERSON", "text": "A"},
                {"entity_type": "", "text": "B"},
                {"entity_type": "EMAIL", "text": "a@b.nl"},
            ]
        )
        db.commit()
    response = client.get(
        f"/api/v1/documents/{meta['id']}/metadata?details=true", auth=VALID_AUTH
    )
    assert response.json()["pii_entities"] == [
        {"entity_type": "PERSON", "text": "A"},
        {"entity_type": "EMAIL", "text": "a@b.nl"},
    ]


@pytest.mark.parametrize("stored_value", [None, "not json", "[]"])
def test_metadata_details_fall_back_to_analysing_the_pdf(
    client: TestClient, stored_value: str | None
) -> None:
    meta = upload(client, NAME)
    with SessionLocal() as db:
        doc = db.get(Document, meta["id"])
        assert doc is not None
        doc.pii_entities = stored_value
        db.commit()
    response = client.get(
        f"/api/v1/documents/{meta['id']}/metadata?details=true", auth=VALID_AUTH
    )
    assert response.json()["pii_entities"] == [{"entity_type": "PERSON", "text": NAME}]


def test_metadata_of_an_unknown_document(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/documents/{uuid.uuid4().hex}/metadata", auth=VALID_AUTH
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


@pytest.mark.parametrize(
    ("method", "suffix", "kwargs"),
    [
        ("GET", "metadata", {}),
        ("GET", "download", {}),
        ("POST", "anonymize", {"json": {"pii_entities_to_anonymize": ["PERSON"]}}),
    ],
)
def test_a_file_id_that_is_not_a_uuid(
    client: TestClient, method: str, suffix: str, kwargs: dict
) -> None:
    response = client.request(
        method, f"/api/v1/documents/not-a-uuid/{suffix}", auth=VALID_AUTH, **kwargs
    )
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Invalid file ID format")


# --- anonymize and download -----------------------------------------------------


def anonymize(client: TestClient, file_id: str, entities: list[str]):
    return client.post(
        f"/api/v1/documents/{file_id}/anonymize",
        auth=VALID_AUTH,
        json={"pii_entities_to_anonymize": entities},
    )


def test_anonymize_redacts_records_an_event_and_stores_the_path(
    client: TestClient,
) -> None:
    meta = upload(client, f"{NAME} belt {NAME}")
    response = anonymize(client, meta["id"], ["PERSON"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == meta["id"]
    assert body["filename"] == "brief.pdf"
    assert body["status"] == "success (2 entities processed)"
    assert [e["text"] for e in body["pii_entities"]] == [NAME, NAME]
    assert body["pii_entities"][0]["score"] == "0.85"

    doc = stored(meta["id"])
    out = Path(str(doc.anonymized_path))
    assert out.name == f"{meta['id']}.pdf"
    with pymupdf.open(str(out)) as pdf:
        assert NAME not in pdf[0].get_text()
    assert [s for s, _ in events(meta["id"])] == [body["status"]]
    assert events(meta["id"])[0][1] == body["time_taken"]


def test_anonymize_of_an_unknown_document(client: TestClient) -> None:
    response = anonymize(client, uuid.uuid4().hex, ["PERSON"])
    assert response.status_code == 404


def test_anonymize_refuses_an_unsupported_entity(client: TestClient) -> None:
    meta = upload(client, NAME)
    response = anonymize(client, meta["id"], ["SHOE_SIZE"])
    assert response.status_code == 422


def test_a_failed_anonymization_records_the_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    meta = upload(client, NAME)
    leftover = Path(settings.DATA_DIR) / "temp/anonymized" / f"{meta['id']}.pdf"

    def failing(job):  # noqa: ANN001, ANN202
        Path(job.output_path).write_bytes(b"partial")
        raise ValueError("boom")

    monkeypatch.setattr(pdf_xmp, "anonymize_pdf", failing)
    response = anonymize(client, meta["id"], ["PERSON"])
    assert response.status_code == 500
    assert response.json()["detail"] == "Document anonymization failed: failed: boom"
    assert not leftover.exists()
    assert [s for s, _ in events(meta["id"])] == ["failed: boom"]
    assert stored(meta["id"]).anonymized_path is None


def test_an_unexpected_error_is_a_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    meta = upload(client, NAME)

    def broken(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise RuntimeError("kapot")

    monkeypatch.setattr(pdf_xmp, "analyze_and_anonymize_document", broken)
    response = anonymize(client, meta["id"], ["PERSON"])
    assert response.status_code == 500
    assert response.json()["detail"].endswith("kapot")
    assert events(meta["id"]) == []


def test_download_keeps_the_files_when_asked(client: TestClient) -> None:
    meta = upload(client, NAME)
    anonymize(client, meta["id"], ["PERSON"])
    doc = stored(meta["id"])
    response = client.get(
        f"/api/v1/documents/{meta['id']}/download?keep_on_server=true",
        auth=VALID_AUTH,
    )
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert Path(str(doc.anonymized_path)).exists()
    assert Path(doc.source_path).exists()


def test_download_removes_the_files_by_default(client: TestClient) -> None:
    meta = upload(client, NAME)
    anonymize(client, meta["id"], ["PERSON"])
    doc = stored(meta["id"])
    response = client.get(f"/api/v1/documents/{meta['id']}/download", auth=VALID_AUTH)
    assert response.status_code == 200
    assert not Path(str(doc.anonymized_path)).exists()
    assert not Path(doc.source_path).exists()

    again = client.get(f"/api/v1/documents/{meta['id']}/download", auth=VALID_AUTH)
    assert again.status_code == 404
    assert again.json()["detail"] == "Document not found"


def test_download_before_anonymizing(client: TestClient) -> None:
    meta = upload(client, NAME)
    response = client.get(f"/api/v1/documents/{meta['id']}/download", auth=VALID_AUTH)
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not anonymized"


# --- deanonymize ----------------------------------------------------------------


def test_deanonymize_restores_the_redacted_text(client: TestClient, tmp_path) -> None:
    source, out = tmp_path / "in.pdf", tmp_path / "out.pdf"
    source.write_bytes(pdf_bytes(f"{NAME} belt"))
    pdf_xmp.anonymize_pdf(
        pdf_xmp.RedactionJob(
            str(source), str(out), {NAME: "person"}, settings.CRYPTO_KEY.decode()
        )
    )
    response = client.post(
        "/api/v1/documents/deanonymize",
        auth=VALID_AUTH,
        files={"file": ("anon.pdf", out.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    assert 'filename="deanonymized_anon.pdf"' in response.headers["content-disposition"]
    restored = pymupdf.open(stream=response.content, filetype="pdf")
    assert NAME in restored[0].get_text()
    temp = Path(settings.DATA_DIR) / "temp/deanonymized"
    assert list(temp.glob("*")) == []


def test_deanonymize_without_metadata_is_a_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents/deanonymize",
        auth=VALID_AUTH,
        files={"file": ("plain.pdf", pdf_bytes("niets"), "application/pdf")},
    )
    assert response.status_code == 422
    assert (
        response.json()["detail"] == "No anonymization metadata found in the document"
    )
    temp = Path(settings.DATA_DIR) / "temp/deanonymized"
    assert list(temp.glob("*")) == []
