"""Configuration of the documents component: storage, database and sealing key."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()


class DocumentSettings:
    """Where documents are stored, the database to record them in, and the key."""

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


document_settings = DocumentSettings()
