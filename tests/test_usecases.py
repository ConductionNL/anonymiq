import os
import time
from pathlib import Path

import pytest
import requests


def get_base_url() -> str:
    # Prefer explicit env var; default to local dev.
    # ANONYMIQ_BASE_URL is canonical; OPENANONYMISER_BASE_URL is still read
    # because it is what every README, CI job and shell profile written before
    # the rename sets. Dropping it would not error — os.getenv() would fall
    # through to the localhost default and the suite would quietly test a
    # different target than the operator asked for.
    return os.getenv(
        "ANONYMIQ_BASE_URL",
        os.getenv("OPENANONYMISER_BASE_URL", "http://localhost:8080"),
    )


def _assert_ok(resp: requests.Response) -> None:
    assert resp.status_code in (200, 201), f"HTTP {resp.status_code}: {resp.text}"


@pytest.mark.integration
def test_health() -> None:
    base = get_base_url()
    resp = requests.get(f"{base}/api/v1/health", timeout=30)
    _assert_ok(resp)
    data = resp.json()
    assert isinstance(data, dict)
    assert data.get("ping") == "pong"


@pytest.mark.integration
def test_analyze_text_spacy() -> None:
    base = get_base_url()
    payload = {
        "text": "Jan Jansen woont op Kerkstraat 10, 1234 AB Amsterdam. IBAN: NL91ABNA0417164300.",
        "language": "nl",
        "entities": ["PERSON", "IBAN", "ADDRESS"],
        "nlp_engine": "spacy",
    }
    resp = requests.post(f"{base}/api/v1/analyze", json=payload, timeout=60)
    _assert_ok(resp)
    data = resp.json()
    assert "pii_entities" in data
    # Expect at least one entity recognized
    assert isinstance(data["pii_entities"], list)
    assert len(data["pii_entities"]) >= 1


@pytest.mark.integration
def test_anonymize_text() -> None:
    base = get_base_url()
    payload = {
        "text": "Mail Jan op jan.jansen@example.com of bel 0612345678.",
        "language": "nl",
        "anonymization_strategy": "replace",
    }
    resp = requests.post(f"{base}/api/v1/anonymize", json=payload, timeout=60)
    _assert_ok(resp)
    data = resp.json()
    assert "original_text" in data and "anonymized_text" in data
    assert data["original_text"] != data["anonymized_text"]
    assert isinstance(data.get("entities_found", []), list)


@pytest.mark.integration
def test_anonymize_text_single_entity() -> None:
    base = get_base_url()
    # Text contains an IBAN and an email; only anonymize IBAN
    payload = {
        "text": "Contact: jan.jansen@example.com. IBAN: NL91ABNA0417164300.",
        "language": "nl",
        "entities": ["IBAN"],
        "anonymization_strategy": "replace",
    }
    resp = requests.post(f"{base}/api/v1/anonymize", json=payload, timeout=60)
    _assert_ok(resp)
    data = resp.json()
    assert data["original_text"] != data["anonymized_text"]
    assert isinstance(data.get("entities_found", []), list)


@pytest.mark.integration
def test_anonymize_text_all_entities() -> None:
    base = get_base_url()
    payload = {
        "text": "Jan woont in Amsterdam, tel 0612345678, mail jan@example.com, IBAN NL91ABNA0417164300.",
        "language": "nl",
        "entities": [
            "PERSON",
            "EMAIL",
            "PHONE_NUMBER",
            "IBAN",
            "ADDRESS",
            "LOCATION",
            "ORGANIZATION",
        ],
        "anonymization_strategy": "replace",
    }
    resp = requests.post(f"{base}/api/v1/anonymize", json=payload, timeout=60)
    _assert_ok(resp)
    data = resp.json()
    assert data["original_text"] != data["anonymized_text"]
    assert isinstance(data.get("entities_found", []), list)


@pytest.mark.integration
def test_document_flow_upload_anonymize_download(tmp_path: Path) -> None:
    base = get_base_url()

    # Prefer new mock test file; fallback to legacy test.pdf
    candidates = [
        Path("tests") / "mock_persoonsgegevens.pdf",
        Path("test.pdf"),
    ]
    repo_pdf = next((p for p in candidates if p.exists()), None)
    if not repo_pdf:
        pytest.skip(
            "No test PDF found (looked for tests/mock_persoonsgegevens.pdf and test.pdf)"
        )

    # 1) Upload
    with repo_pdf.open("rb") as fh:
        files = {"files": ("test.pdf", fh, "application/pdf")}
        resp = requests.post(
            f"{base}/api/v1/documents/upload", files=files, timeout=120
        )
    _assert_ok(resp)

    # Some proxies can return text/plain on errors; ensure JSON here
    try:
        up = resp.json()
    except Exception as exc:  # pragma: no cover
        raise AssertionError(
            f"Upload response is not JSON: {resp.text[:200]} ... ({exc})"
        )

    assert "files" in up and isinstance(up["files"], list) and len(up["files"]) >= 1
    file_id = up["files"][0]["id"]
    assert file_id

    # 1b) Metadata (met PII entiteiten)
    meta = requests.get(
        f"{base}/api/v1/documents/{file_id}/metadata",
        params={"get_pii_entities": True},
        timeout=60,
    )
    _assert_ok(meta)

    # 2) Anonymize
    anon_payload = {
        "pii_entities_to_anonymize": [
            "PERSON",
            "EMAIL",
            "PHONE_NUMBER",
            "IBAN",
            "ADDRESS",
        ]
    }
    resp = requests.post(
        f"{base}/api/v1/documents/{file_id}/anonymize", json=anon_payload, timeout=180
    )
    _assert_ok(resp)
    anon = resp.json()
    status_text = str(anon.get("status", "")).lower()
    assert status_text.startswith(("ok", "success", "completed"))

    # Optional delay if processing is async in some environments
    time.sleep(1)

    # 3) Download
    # Save anonymized result into repo tests/ directory for inspection
    tests_dir = Path("tests")
    tests_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(str(repo_pdf)).stem  # original name without extension
    out_pdf = tests_dir / f"{base_name}(geanonimiseerd).pdf"

    resp = requests.get(f"{base}/api/v1/documents/{file_id}/download", timeout=120)
    _assert_ok(resp)
    # Some deployments may return FileResponse (binary) or a JSON envelope (rare).
    # Prefer binary write if possible.
    try:
        content = resp.content
        assert content and len(content) > 0
        out_pdf.write_bytes(content)
        assert out_pdf.exists() and out_pdf.stat().st_size > 0
    except Exception as exc:
        raise AssertionError(f"Failed to store downloaded file: {exc}")
