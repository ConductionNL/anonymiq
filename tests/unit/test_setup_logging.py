"""Characterization test for setup_logging: the dictConfig it applies."""

import logging.config
import os

import pytest

from src.api import config


def expected(log_dir: str, console_level: str) -> dict:
    return {
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
                "level": console_level,
                "stream": "ext://sys.stdout",
            },
        },
        "root": {"level": "DEBUG", "handlers": ["file", "stream"]},
        "loggers": {
            "python_multipart.multipart": {
                "level": "WARNING",
                "handlers": ["file", "stream"],
                "propagate": False,
            },
        },
    }


@pytest.mark.parametrize(("debug", "level"), [(True, "DEBUG"), (False, "INFO")])
def test_setup_logging_applies_the_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path, debug: bool, level: str
) -> None:
    applied: list[dict] = []
    log_dir = str(tmp_path / "logs")
    monkeypatch.setenv("LOG_DIR", log_dir)
    monkeypatch.setattr(config.settings, "DEBUG", debug)
    monkeypatch.setattr(logging.config, "dictConfig", applied.append)
    config.setup_logging()
    config.setup_logging()
    assert applied == [expected(log_dir, level), expected(log_dir, level)]
    assert os.path.isdir(log_dir)


def test_the_log_dir_defaults_to_logs(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    applied: list[dict] = []
    monkeypatch.delenv("LOG_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(logging.config, "dictConfig", applied.append)
    config.setup_logging()
    assert applied[0]["handlers"]["file"]["filename"] == os.path.join("logs", "app.log")
    assert (tmp_path / "logs").is_dir()
