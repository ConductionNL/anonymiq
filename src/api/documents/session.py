"""The database engine and session factory of the documents component."""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.documents.database import Base
from src.api.documents.settings import document_settings as settings

# Ensure data directory exists before creating database
os.makedirs(settings.DATA_DIR, exist_ok=True)

# Define the database engine and session
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine, checkfirst=True)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for one request and close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
