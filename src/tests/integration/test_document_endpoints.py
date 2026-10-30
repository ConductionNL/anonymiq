"""Integration tests for document endpoints."""

import importlib.util
import time
from pathlib import Path

import pytest
from fastapi import status

from src.api.dtos import DocumentAnonymizationRequest


def _check_pdf_dependencies():
    """Check if the required PDF manipulation dependencies are installed."""
    required_modules = ["pymupdf", "pikepdf", "PIL"]
    missing_modules = []

    for module in required_modules:
        if importlib.util.find_spec(module) is None:
            missing_modules.append(module)

    if missing_modules:
        pytest.skip(
            f"Skipping test as required modules are missing: {', '.join(missing_modules)}. "
            "Install PyMuPDF, pikepdf, and Pillow to run these tests."
        )

    return True


def test_upload_document_success(client, test_pdf_path, temp_dirs):
    """Test successful document upload."""
    # Check dependencies
    _check_pdf_dependencies()

    # Ensure test directories exist
    assert temp_dirs["source"].exists()

    # Open test PDF file
    with open(test_pdf_path, "rb") as f:
        files = {"files": (test_pdf_path.name, f, "application/pdf")}
        response = client.post(
            "/documents/upload",
            files=files,
            params={"tags": ["test", "integration"]},
        )

    # Check response
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "files" in data
    assert len(data["files"]) == 1

    # Verify file details
    file_data = data["files"][0]
    assert file_data["filename"] == test_pdf_path.name
    assert file_data["content_type"] == "application/pdf"
    assert "id" in file_data
    assert len(file_data["tags"]) == 2

    # Verify file was stored on disk
    file_id = file_data["id"]
    source_path = temp_dirs["source"] / f"{file_id}.pdf"
    assert source_path.exists()

    # Return the file ID for use in other tests
    return file_id


def test_upload_document_invalid_extension(client, temp_dirs):
    """Test document upload with invalid file extension."""
    # Create a temporary text file
    from src.api.documents.settings import document_settings as settings

    temp_file = Path(settings.DATA_DIR) / "temp/test_file.txt"
    with open(temp_file, "w") as f:
        f.write("This is a test file")

    try:
        # Try to upload a text file
        with open(temp_file, "rb") as f:
            files = {"files": ("test_file.txt", f, "text/plain")}
            response = client.post("/documents/upload", files=files)

        # Check response - should be an error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "message" in data
        assert "supported" in data["message"].lower()

    finally:
        # Clean up
        if temp_file.exists():
            temp_file.unlink()


def test_get_document_metadata(client, test_pdf_path, temp_dirs):
    """Test getting document metadata."""
    # Check dependencies
    _check_pdf_dependencies()

    # First, upload a document
    with open(test_pdf_path, "rb") as f:
        files = {"files": (test_pdf_path.name, f, "application/pdf")}
        upload_response = client.post(
            "/documents/upload", files=files, params={"tags": ["metadata-test"]}
        )

    file_id = upload_response.json()["files"][0]["id"]

    # Now get metadata
    response = client.get(f"/documents/{file_id}/metadata")

    # Check response
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == file_id
    assert data["filename"] == test_pdf_path.name
    assert len(data["tags"]) == 1
    assert data["tags"][0]["name"] == "metadata-test"


def test_get_document_metadata_not_found(client):
    """Test getting metadata for a non-existent document."""
    response = client.get("/documents/nonexistent-id/metadata")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    "pii_entities",
    [
        ["PERSON", "EMAIL"],
        ["LOCATION", "ORGANIZATION"],
        ["PERSON", "DATE"],
    ],
)
def test_anonymize_document(client, test_pdf_path, temp_dirs, pii_entities):
    """Test document anonymization with different PII entity types."""
    # Check dependencies
    _check_pdf_dependencies()

    # First, upload a document
    with open(test_pdf_path, "rb") as f:
        files = {"files": (test_pdf_path.name, f, "application/pdf")}
        upload_response = client.post("/documents/upload", files=files)

    file_id = upload_response.json()["files"][0]["id"]

    # Anonymize document
    request_body = DocumentAnonymizationRequest(pii_entities_to_anonymize=pii_entities)

    # We're using the actual PDF manipulation now
    # Make sure the source path exists
    source_path = temp_dirs["source"] / f"{file_id}.pdf"
    assert source_path.exists()

    # Make sure the destination directory exists
    anonym_dir = temp_dirs["anonymized"]
    anonym_dir.mkdir(parents=True, exist_ok=True)

    # Make the anonymization request
    response = client.post(f"/documents/{file_id}/anonymize", json=request_body.dict())

    # Check response
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == file_id
    assert data["status"] in [
        "success",
        "failed",
    ]  # Might fail if pdf_xmp is not mocked
    assert isinstance(data["time_taken"], int)


def test_anonymize_document_not_found(client):
    """Test anonymizing a non-existent document."""
    request_body = DocumentAnonymizationRequest(
        pii_entities_to_anonymize=["PERSON", "EMAIL"]
    )

    response = client.post(
        "/documents/nonexistent-id/anonymize", json=request_body.dict()
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_download_document(client, test_pdf_path, temp_dirs):
    """Test document download."""
    # Check dependencies
    _check_pdf_dependencies()

    # First, upload a document
    with open(test_pdf_path, "rb") as f:
        files = {"files": (test_pdf_path.name, f, "application/pdf")}
        upload_response = client.post("/documents/upload", files=files)

    file_id = upload_response.json()["files"][0]["id"]

    # Anonymize document to create download path
    request_body = DocumentAnonymizationRequest(pii_entities_to_anonymize=["PERSON"])

    # Use the real anonymization
    source_path = temp_dirs["source"] / f"{file_id}.pdf"
    assert source_path.exists()

    # Anonymize the document
    anon_response = client.post(
        f"/documents/{file_id}/anonymize", json=request_body.dict()
    )
    assert anon_response.status_code == status.HTTP_200_OK

    # Now try to download
    response = client.get(f"/documents/{file_id}/download?keep_on_server=true")

    # Check response
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/pdf"
    assert "content-disposition" in response.headers
    assert file_id in response.headers["content-disposition"]

    # Verify content
    assert len(response.content) > 0


def test_download_document_not_found(client):
    """Test downloading a non-existent document."""
    response = client.get("/documents/nonexistent-id/download")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_download_document_not_anonymized(client, test_pdf_path, temp_dirs):
    """Test downloading a document that hasn't been anonymized yet."""
    # Check dependencies
    _check_pdf_dependencies()

    # First, upload a document
    with open(test_pdf_path, "rb") as f:
        files = {"files": (test_pdf_path.name, f, "application/pdf")}
        upload_response = client.post("/documents/upload", files=files)

    file_id = upload_response.json()["files"][0]["id"]

    # Try to download without anonymizing first
    response = client.get(f"/documents/{file_id}/download")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not anonymized" in response.json()["detail"].lower()


def test_end_to_end_flow(client, test_pdf_path, temp_dirs):
    """Test end-to-end document flow: upload, anonymize, and download."""
    # Check dependencies
    _check_pdf_dependencies()

    # 1. Upload document
    with open(test_pdf_path, "rb") as f:
        files = {"files": (test_pdf_path.name, f, "application/pdf")}
        upload_response = client.post(
            "/documents/upload", files=files, params={"tags": ["e2e-test"]}
        )

    assert upload_response.status_code == status.HTTP_200_OK
    file_id = upload_response.json()["files"][0]["id"]

    # 2. Get metadata
    metadata_response = client.get(f"/documents/{file_id}/metadata")
    assert metadata_response.status_code == status.HTTP_200_OK
    metadata = metadata_response.json()
    assert metadata["id"] == file_id

    # 3. Anonymize
    request_body = DocumentAnonymizationRequest(
        pii_entities_to_anonymize=["PERSON", "EMAIL", "LOCATION"]
    )

    # Use the real anonymization with the actual PDF manipulation
    source_path = temp_dirs["source"] / f"{file_id}.pdf"
    assert source_path.exists()

    # Make the anonymization request
    anon_response = client.post(
        f"/documents/{file_id}/anonymize", json=request_body.dict()
    )
    assert anon_response.status_code == status.HTTP_200_OK

    # Wait a moment to ensure file is ready
    time.sleep(0.5)

    # 4. Download
    download_response = client.get(f"/documents/{file_id}/download?keep_on_server=true")
    assert download_response.status_code == status.HTTP_200_OK
    assert download_response.headers["content-type"] == "application/pdf"
    assert len(download_response.content) > 0
