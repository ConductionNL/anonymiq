"""The database engine and session factory of the documents component."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.documents.database import Base
from src.api.documents.settings import document_settings as settings

# Ensure data directory exists before creating database
os.makedirs(settings.DATA_DIR, exist_ok=True)

# Define the database engine and session
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine, checkfirst=True)
