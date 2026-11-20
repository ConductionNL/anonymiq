import os
import requests
import pytest


def get_base_url() -> str:
    # ANONYMIQ_BASE_URL is canonical; OPENANONYMISER_BASE_URL is still read
    # because it is what every README, CI job and shell profile written before
    # the rename sets. The DEFAULT host stays on the old name deliberately:
    # api.anonymiq.accept.commonground.nu does not resolve, and pointing the
    # suite at a host that answers nothing would turn a passing integration
    # run into a connection error that looks like an outage.
    return os.getenv(
        "ANONYMIQ_BASE_URL",
        os.getenv(
            "OPENANONYMISER_BASE_URL",
            "https://api.openanonymiser.accept.commonground.nu",
        ),
    )


COMPREHENSIVE_TEXT = (
    "Op 12 januari 2024 bezocht Jan Jansen van Organisatie X het kantoor op "
    "Kerkstraat 10, 1234 AB Amsterdam. "
    "Zijn telefoon is 06-12345678 en e-mail jan.jansen@example.com. "
    "IBAN NL91 ABNA 0417 1643 00. "
    "BSN 123456782. "
    "Paspoortnummer XN1234567. "
    "Rijbewijsnummer 1234567890. "
    "Zaaknummer Z-2023-123456 en AWB 21/12345."
)


@pytest.mark.integration
def test_analyze_supported_entities_staging() -> None:
    """
    Posts a comprehensive Dutch text to /analyze on staging and asserts that
    pattern-based entities are detected. Logs full set of entity types found.
    """
    base = get_base_url()
    payload = {"text": COMPREHENSIVE_TEXT, "language": "nl"}

    resp = requests.post(f"{base}/api/v1/analyze", json=payload, timeout=60)
    assert resp.status_code in (200, 201), f"HTTP {resp.status_code}: {resp.text[:500]}"
    data = resp.json()

    assert "pii_entities" in data
    entities = data["pii_entities"]
    assert isinstance(entities, list)
    assert data.get("text_length") == len(COMPREHENSIVE_TEXT)

    found_types = {e["entity_type"] for e in entities}
    # Assert presence of robust, documented pattern-based entities
    # Per docs: patterns = IBAN, PHONE_NUMBER, EMAIL
    expected_patterns = {"EMAIL", "IBAN", "PHONE_NUMBER"}
    missing = expected_patterns - found_types
    assert not missing, (
        f"Missing expected documented pattern entities: {sorted(missing)}; found={sorted(found_types)}"
    )

    # Optionally print NER-based types for visibility (won't fail if absent).
    # Per docs: PERSON, LOCATION, ORGANIZATION and ADDRESS (best-effort).
    ner_candidates = {"PERSON", "LOCATION", "ORGANIZATION", "ADDRESS"}
    present_ner = sorted(found_types & ner_candidates)
    print(f"Detected NER types (info): {present_ner}")
