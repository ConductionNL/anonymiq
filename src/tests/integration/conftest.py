"""Test fixtures for integration tests."""

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# Function to check if a module is installed
def is_module_installed(module_name):
    """Check if a Python module is installed."""
    return importlib.util.find_spec(module_name) is not None


from src.api.documents.database import Base  # noqa: E402
from src.api.documents.service import get_db  # noqa: E402
from src.api.main import app  # noqa: E402

# Create an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    # Create the tables
    Base.metadata.create_all(bind=engine)

    # Create a session
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop tables after test to ensure a clean state
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with the test database."""

    # Override the get_db dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, base_url="http://testserver/api/v1") as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def temp_dirs():
    """Create and clean up temporary directories for file operations."""
    # Create temporary directories for test files
    from src.api.documents.settings import document_settings as settings

    base_dir = Path(settings.DATA_DIR)
    source_dir = base_dir / "temp/source"
    anonym_dir = base_dir / "temp/anonymized"

    source_dir.mkdir(parents=True, exist_ok=True)
    anonym_dir.mkdir(parents=True, exist_ok=True)

    yield {"source": source_dir, "anonymized": anonym_dir}

    # Clean up test files after test
    for dir_path in [source_dir, anonym_dir]:
        for file_path in dir_path.glob("*.pdf"):
            try:
                file_path.unlink()
            except (FileNotFoundError, PermissionError):
                pass


@pytest.fixture(scope="function")
def test_pdf_path():
    """Path to a test PDF file that should be placed in the root directory."""
    pdf_path = Path("test.pdf")

    # If the file exists, use it
    if pdf_path.exists():
        return pdf_path

    # If we have PyMuPDF, create a simple test PDF
    if is_module_installed("pymupdf"):
        try:
            import pymupdf

            # Create a new PDF with sample text
            doc = pymupdf.open()
            page = doc.new_page()

            # Add some text with potential PII entities
            text = (
                "John Doe lives in New York City and works for ACME Corporation.\n"
                "He was born on January 1, 1980 and can be reached at john.doe@example.com.\n"
                "His phone number is 555-123-4567 and his SSN is 123-45-6789.\n"
                "He has a meeting with Jane Smith on 2023-05-15."
            )

            # Insert the text into the PDF
            page.insert_text((50, 50), text, fontsize=11)

            # Save the document
            doc.save(str(pdf_path))
            doc.close()

            return pdf_path
        except Exception as e:
            pytest.skip(f"Could not create test PDF with PyMuPDF: {e}")

    # If we couldn't create or find a PDF, skip the test
    pytest.skip(
        "No test.pdf file found and could not create one. Please create a sample PDF file manually."
    )
    return None
