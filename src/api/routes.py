import logging

from fastapi.routing import APIRouter

from src.api.document_routes import documents_router
from src.api.text_routes import text_analysis_router

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def ping() -> dict[str, str]:
    """Health check endpoint.

    Geeft een eenvoudige status terug om te controleren of de API draait.
    """
    return {"ping": "pong"}


router.include_router(documents_router)
logging.info("Documents API router included!")

router.include_router(text_analysis_router)
logging.info("Text Analysis API router included!")


__all__ = ["router"]
