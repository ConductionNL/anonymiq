import logging.config
import os

from dotenv import load_dotenv

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

    Bevat standaardwaarden voor debugmodus, ondersteunde entiteiten, taal,
    en de te gebruiken NLP-modellen (spaCy of transformers).
    """

    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    DEFAULT_ENTITIES = [
        "PERSON",
        "LOCATION",
        "PHONE_NUMBER",
        "EMAIL",
        "ORGANIZATION",
        "IBAN",
        "DATE_TIME",
        "ADDRESS",
    ]

    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "nl")
    DEFAULT_NLP_ENGINE = os.getenv("DEFAULT_NLP_ENGINE", "spacy").lower()
    DEFAULT_SPACY_MODEL = os.getenv("DEFAULT_SPACY_MODEL", "nl_core_news_md")
    DEFAULT_TRANSFORMERS_MODEL = os.getenv(
        "DEFAULT_TRANSFORMERS_MODEL", "pdelobelle/robbert-v2-dutch-base"
    )
    # CORS is off unless a deployment names its browser origins. The known
    # machine caller (OpenRegister's analyze call) is server to server and
    # sends no Origin header, so it needs no CORS at all.
    # Only a browser front end on another origin, like the dev UI in
    # docker-compose, needs its origin listed here (comma separated).
    ALLOWED_ORIGINS: list[str] = parse_allowed_origins(os.getenv("ALLOWED_ORIGINS"))
    SUPPORTED_UPLOAD_EXTENSIONS = [
        "pdf",
    ]
    SUPPORTED_PII_ENTITIES_TO_ANONYMIZE = [
        "PERSON",
        "LOCATION",
        "PHONE_NUMBER",
        "EMAIL",
        "ORGANIZATION",
        "IBAN",
        "DATE_TIME",
        "ADDRESS",
    ]
    key = os.getenv("CRYPTO_KEY")
    if key:
        CRYPTO_KEY = key.encode("utf-8")
    else:
        logging.warning(
            "CRYPTO_KEY is not set. Using default value. This is not secure for production!"
        )
        CRYPTO_KEY = b"secret"
    # FROZEN at the pre-rename filename, deliberately. This default is what a
    # deployment WITHOUT an explicit DATABASE_URL falls back to, and the file
    # it names already exists on the production PersistentVolumeClaim (the
    # Helm chart passes the same path). Renaming it would not raise: SQLite
    # would create a new, EMPTY database next to the real one and the service
    # would start up looking freshly installed, with every document gone and
    # nothing in the log to say why. It moves only with a volume migration.
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/openanonymiser.db")
    KEEP_TEMP_FILES = os.getenv("KEEP_TEMP_FILES", "false").lower() == "true"

    # Base directory for data files (used by temp directories)
    DATA_DIR = os.getenv("DATA_DIR", "data")

    # HTTP Basic credentials for the document routes. There is no built-in
    # password: when BASIC_AUTH_PASSWORD is unset or empty every document
    # route answers 401, so a deployment that forgets it fails closed.
    BASIC_AUTH_USERNAME = os.getenv("BASIC_AUTH_USERNAME", "admin")
    BASIC_AUTH_PASSWORD = os.getenv("BASIC_AUTH_PASSWORD", "")


settings: Settings = Settings()


def setup_logging() -> None:
    """Configureer logging voor de applicatie.

    Stelt zowel een file- als streamhandler in, met DEBUG- of INFO-niveau
    afhankelijk van de configuratie. Logt naar 'app.log' en de console.
    """
    console_log_level = "DEBUG" if settings.DEBUG else "INFO"
    log_dir = os.getenv("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    logging.config.dictConfig(
        {
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
                    "filename": os.path.join(log_dir, "app.log"),
                },
                "stream": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": console_log_level,
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
    )

    logging.debug("Logging is configured.")
