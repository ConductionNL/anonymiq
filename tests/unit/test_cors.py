"""CORS answers only the origins a deployment names, never every origin."""

from fastapi.testclient import TestClient

ALLOWED = "https://allowed.example"
OTHER = "https://evil.example"


def test_a_non_allowed_origin_gets_no_allow_header(client: TestClient) -> None:
    """A simple request from an origin that is not configured."""
    response = client.get("/api/v1/health", headers={"Origin": OTHER})
    assert "access-control-allow-origin" not in response.headers


def test_a_non_allowed_origin_preflight_gets_no_allow_header(
    client: TestClient,
) -> None:
    """A preflight from an origin that is not configured."""
    response = client.options(
        "/api/v1/documents/upload",
        headers={
            "Origin": OTHER,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_a_configured_origin_is_allowed(client: TestClient) -> None:
    """The origin named in ALLOWED_ORIGINS is echoed back, not a wildcard."""
    response = client.get("/api/v1/health", headers={"Origin": ALLOWED})
    assert response.headers.get("access-control-allow-origin") == ALLOWED


def test_parse_allowed_origins_has_no_wildcard_by_default() -> None:
    """Unset or empty means no origin at all, so CORS stays off."""
    from src.api.config import parse_allowed_origins

    assert parse_allowed_origins(None) == []
    assert parse_allowed_origins("") == []
    assert parse_allowed_origins(" https://a.example , https://b.example/ ,") == [
        "https://a.example",
        "https://b.example",
    ]


def test_a_wildcard_origin_is_refused_at_startup(tmp_path) -> None:
    """ALLOWED_ORIGINS='*' stops the app from starting instead of opening CORS."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "ALLOWED_ORIGINS": "https://allowed.example,*",
        "DATA_DIR": str(tmp_path / "data"),
        "LOG_DIR": str(tmp_path / "logs"),
        "DATABASE_URL": f"sqlite:///{tmp_path / 'w.db'}",
    }
    result = subprocess.run(
        [sys.executable, "-c", "import src.api.main"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "ALLOWED_ORIGINS must name explicit origins" in result.stderr
