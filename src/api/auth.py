"""HTTP Basic authentication for the document routes."""

import logging
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from src.api.config import settings

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
        logger.error(
            "BASIC_AUTH_PASSWORD is not set; refusing every authenticated request."
        )
        raise _unauthorized()
    # Both are compared every time, so the timing does not reveal which one failed.
    is_correct_username = _matches(credentials.username, settings.BASIC_AUTH_USERNAME)
    is_correct_password = _matches(credentials.password, settings.BASIC_AUTH_PASSWORD)
    if not (is_correct_username and is_correct_password):
        raise _unauthorized()
    return credentials.username


def _matches(given: str, expected: str) -> bool:
    """Compare two strings in constant time."""
    return secrets.compare_digest(given.encode("utf8"), expected.encode("utf8"))


def _unauthorized() -> HTTPException:
    """Return the 401 with a Basic challenge."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Basic"},
    )
