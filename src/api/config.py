import copy
import logging.config
import os

from dotenv import load_dotenv

from src.api.analysis.analyzer import analysis_settings

load_dotenv()


def parse_allowed_origins(raw: str | None) -> list[str]:
    """Parse a comma separated ALLOWED_ORIGINS value into a list of origins.

    Unset or empty gives an empty list, which leaves CORS off. A trailing slash
    is dropped, because a browser sends the origin without one.

    Args:
        raw: The raw environment value, or None when it is not set.

    Returns:
        list[str]: The explicit origins, in the order given.
    """
    if not raw:
        return []
    return [part.strip().rstrip("/") for part in raw.split(",") if part.strip()]


class Settings:
    """Applicatieconfiguratie voor de Presidio-NL API.

    Bevat standaardwaarden voor debugmodus, CORS, uploads en toegang.
    De tekstanalyse en de documentopslag hebben hun eigen instellingen, in
    ``src.api.analysis.analyzer`` en ``src.api.documents.settings``.
    """

    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    # CORS is off unless a deployment names its browser origins. The known
    # machine caller (OpenRegister's analyze call) is server to server and
    # sends no Origin header, so it needs no CORS at all.
    # Only a browser front end on another origin, like the dev UI in
    # docker-compose, needs its origin listed here (comma separated).
    ALLOWED_ORIGINS: list[str] = parse_allowed_origins(os.getenv("ALLOWED_ORIGINS"))
    SUPPORTED_UPLOAD_EXTENSIONS = [
        "pdf",
    ]
    SUPPORTED_PII_ENTITIES_TO_ANONYMIZE = list(analysis_settings.DEFAULT_ENTITIES)
    # HTTP Basic credentials for the document routes. There is no built-in
    # password: when BASIC_AUTH_PASSWORD is unset or empty every document
    # route answers 401, so a deployment that forgets it fails closed.
    BASIC_AUTH_USERNAME = os.getenv("BASIC_AUTH_USERNAME", "admin")
    BASIC_AUTH_PASSWORD = os.getenv("BASIC_AUTH_PASSWORD", "")


settings: Settings = Settings()


# dictConfig applied by setup_logging; it fills in the log file and the
# console level.
_LOGGING_TEMPLATE: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "file": {
            "class": "logging.FileHandler",
            "formatter": "default",
            "level": "DEBUG",
        },
        "stream": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",  # Use stdout with UTF-8 encoding
        },
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["file", "stream"],
    },
    "loggers": {
        "python_multipart.multipart": {
            "level": "WARNING",
            "handlers": ["file", "stream"],
            "propagate": False,
        },
        # Add other custom loggers to disable here if needed
    },
}


def setup_logging() -> None:
    """Configureer logging voor de applicatie.

    Stelt zowel een file- als streamhandler in, met DEBUG- of INFO-niveau
    afhankelijk van de configuratie. Logt naar 'app.log' en de console.
    """
    log_dir = os.getenv("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    logging.config.dictConfig(
        logging_config(log_dir, "DEBUG" if settings.DEBUG else "INFO")
    )
    logging.debug("Logging is configured.")


def logging_config(log_dir: str, console_log_level: str) -> dict:
    """Return the logging dictConfig for a log directory and console level."""
    config = copy.deepcopy(_LOGGING_TEMPLATE)
    config["handlers"]["file"]["filename"] = os.path.join(log_dir, "app.log")
    config["handlers"]["stream"]["level"] = console_log_level
    return config
