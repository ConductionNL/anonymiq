# Anonymiq Integration Tests

This directory contains integration tests for the Anonymiq API. These tests use FastAPI's TestClient to test the different endpoints and workflows.

## Requirements

To run these integration tests, you need:

1. A Python environment with the project dependencies installed
2. Either a `test.pdf` file in the root directory, or PyMuPDF installed (which will create a test PDF file automatically)

## Running the Tests

From the project root directory, run:

```bash
pytest tests/integration -v
```

## Test Structure

- `conftest.py`: Contains test fixtures for database sessions, client setup, and test data
- `test_document_endpoints.py`: Tests for the document-related API endpoints
- `test_main.py`: Tests for the main API application

## Important Notes

- The tests use a real PDF analyzer and PDF manipulation process
- An in-memory SQLite database is used for testing, separate from your main database
- Temporary files are created in the `temp/source` and `temp/anonymized` directories

If certain tests are skipped, it's likely because required dependencies (PyMuPDF, pikepdf, etc.) are not installed or a test PDF file could not be found/created.
