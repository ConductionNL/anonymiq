from typing import Optional, TypeVar

from sqlalchemy.orm import Session

from src.api.documents.database import Base, Document

Row = TypeVar("Row", bound=Base)


def save(db: Session, row: Row) -> Row:
    """Add or update a row, commit, and return it refreshed from the database."""
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_document(db: Session, document_id: str) -> Optional[Document]:
    """Get a document by ID."""
    return db.query(Document).filter(Document.id == document_id).first()
