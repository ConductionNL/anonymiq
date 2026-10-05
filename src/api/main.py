from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import settings, setup_logging
from src.api.routers import router

setup_logging()

app = FastAPI(
    title="Presidio-NL API",
    description="API voor Nederlandse tekst analyse en anonimisatie",
    version="1.2.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    redoc_url="/api/v1/redoc",
)

if "*" in settings.ALLOWED_ORIGINS:
    # A wildcard together with credentials would let any web page drive the
    # document routes with a browser's stored credentials. Refuse it.
    raise RuntimeError(
        "ALLOWED_ORIGINS must name explicit origins; '*' is not accepted."
    )

if settings.ALLOWED_ORIGINS:
    # Only browser front ends need CORS. Server to server callers send no
    # Origin header, so with no origins configured the middleware stays off and
    # no response carries an Access-Control-Allow-Origin header.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(router=router)
