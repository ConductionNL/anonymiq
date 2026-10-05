import logging
import os
import secrets
from typing import Annotated, Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from src.api.config import settings
from src.api.database import Base

# Ensure data directory exists before creating database
os.makedirs(settings.DATA_DIR, exist_ok=True)

# Define the database engine and session
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine, checkfirst=True)

logger = logging.getLogger(__name__)

# SEcurity stuff
security = HTTPBasic()


def get_user(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
) -> str:
    """Get the current user based on HTTP Basic Authentication.

    Based on the reference implementation from FastAPI documentation:
    https://fastapi.tiangolo.com/advanced/security/http-basic-auth/#fix-it-with-secretscompare_digest
    (date: July 2025)

    Args:
        credentials (Annotated[HTTPBasicCredentials, Depends): HTTP Basic credentials.

    Raises:
        HTTPException: If the username or password is incorrect.

    Returns:
        str: The username of the authenticated user.
    """
    if not settings.BASIC_AUTH_PASSWORD:
        # Fail closed: without a configured password nobody gets in, rather
        # than an empty password matching an empty one.
        logger.error("BASIC_AUTH_PASSWORD is not set; refusing every document request.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    current_username_bytes = credentials.username.encode("utf8")
    correct_username_bytes = settings.BASIC_AUTH_USERNAME.encode("utf8")
    is_correct_username = secrets.compare_digest(
        current_username_bytes, correct_username_bytes
    )
    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = settings.BASIC_AUTH_PASSWORD.encode("utf8")
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# Dependency function to get a database session
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
