---
description: Start the API (and optionally the UI) locally to try a change
---

Start the API locally, from the repository root:

```bash
uv sync --python 3.12
uv run api.py
```

It serves on port 8080; the Swagger UI is at `http://localhost:8080/api/v1/docs` and the health route at `http://localhost:8080/api/v1/health`. `uv run api.py --help` lists the options (`--env`, `--host`, `--port`, `--workers`). The full sync installs torch and the spaCy model, which is large.

The data routes need HTTP Basic credentials: set `BASIC_AUTH_USERNAME` and `BASIC_AUTH_PASSWORD` (see `.env.example`), or every request answers 401.

To run the API and the web interface together in containers:

```bash
docker compose up -d
```

The API is then on `http://localhost:8001/api/v1/docs` and the UI on `http://localhost:8002`. Stop it with `docker compose down`. README.md writes the older `docker-compose` form, which works where that binary is installed.
