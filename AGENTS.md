# AGENTS.md

anonymiq is a Python web service (FastAPI on Microsoft Presidio) that finds personal data in Dutch text and PDF documents and replaces it with placeholders, with spaCy or a transformers model as the NLP engine. OpenRegister calls its REST API; it also has a small React web interface of its own in `src/ui/`.

It is not a Nextcloud app: there is no `appinfo/info.xml`. It runs as its own container, deployed with the Helm chart in `charts/openanonymiser` and Argo CD (`argocd/`). See [ARCHITECTURE.md](ARCHITECTURE.md) for the components and their boundaries.

## Setup

Local Python environment (Python 3.12, managed with `uv`):

```bash
uv sync --python 3.12
uv run api.py            # API on http://localhost:8080/api/v1/docs
```

On a machine whose default Python is 3.13, a plain `uv sync` tried to build spaCy from source and failed; `--python 3.12` (the version CI uses) installs the locked wheels. CI installs without torch, its CUDA wheels and the large spaCy model, because the unit tests load none of them; see the "Install dependencies" step in [.github/workflows/ci.yml](.github/workflows/ci.yml).

Docker Compose runs the API and the UI together ([docker-compose.yaml](docker-compose.yaml)):

```bash
docker-compose up -d     # API on http://localhost:8001/api/v1/docs, UI on http://localhost:8002
```

The compose file sets development values for `BASIC_AUTH_USERNAME`, `BASIC_AUTH_PASSWORD`, `CRYPTO_KEY` and `ALLOWED_ORIGINS`. All settings are listed in [.env.example](.env.example).

## Build

```bash
docker build -t anonymiq .          # the API image (Dockerfile)
cd src/ui && npm ci && npm run build   # the UI (tsc and vite)
```

The Python service has no build step beyond `uv sync`.

## Test

Python unit tests, as CI runs them (in-process, no models or server needed):

```bash
uv run python -m pytest tests/unit
```

CI adds coverage with a floor: `--cov=src/api --cov-fail-under=37` (the `COVERAGE_MIN` value in `ci.yml`).

UI tests (vitest):

```bash
cd src/ui && npm test
```

The use-case tests in `tests/test_usecases.py` call a running server (default `localhost:8080`, or `ANONYMIQ_BASE_URL`); see the "Testen (pytest)" section of [README.md](README.md). They are not part of CI.

## Lint and quality

There is no Makefile and no single quality command. The quality suite is the set of steps in [.github/workflows/ci.yml](.github/workflows/ci.yml); run them locally with the versions CI pins:

```bash
uvx ruff@0.17.0 check .
uvx ruff@0.17.0 format --check .
uv run --with mypy==2.4.0 mypy src/api
uv run python -m pytest tests/unit
cd src/ui && npm run lint && npm test && npm run build
```

Ruff is configured in `pyproject.toml` (rules E4, E7, E9, F, D, I; Google docstring convention) and checks `src/**/*.py`. Mypy is strict about untyped definitions (`disallow_untyped_defs`). CI also lints and renders the Helm chart with `helm lint --strict` for each values file.

[scripts/precommit.sh](scripts/precommit.sh) is a manual helper (`uv sync`, `ruff check --fix`, `mypy src/api/`); it is not installed as a git hook.

## OpenSpec flow

The repo uses OpenSpec with the `spec-driven` schema ([openspec/config.yaml](openspec/config.yaml)).

- `openspec/changes/<name>/` holds a change in progress: `.openspec.yaml`, `proposal.md`, `tasks.md` and `specs/<capability>/spec.md` (see `openspec/changes/object-detection-in-page-images/`).
- `openspec/specs/<capability>/spec.md` holds the specs of what the service does today.
- A finished change is archived and its spec deltas are merged into `openspec/specs/`.

Rules from `openspec/config.yaml`: a proposal names the OpenRegister change on the other side of any HTTP contract and states what happens when a model or class is not available; scenarios are GIVEN/WHEN/THEN, each tied to a pytest test by name; every task names the pytest test that proves it.

`openspec/woo-build-rules.md`, `openspec/woo-build-queue.md` and `openspec/woo-decisions.md` hold the cross-app Woo build rules, queue and decisions that the changes cite.

## Architecture decisions

Decisions recorded today live in [ARCHITECTURE.md](ARCHITECTURE.md) (component boundaries; PyMuPDF confined to one module) and in [openspec/woo-decisions.md](openspec/woo-decisions.md) (D6: anonymiq owns the image object detector).

## Conventions

Verified in the code and in `ARCHITECTURE.md`:

- Code is grouped by what the service does, not by FastAPI layer. Each component under `src/api/` has one public module: `src/api/analysis/analyzer.py` for text analysis and `src/api/documents/service.py` for documents. Other components import only that module.
- Dependencies run one way: the API uses Documents and Text analysis; Documents uses Text analysis. Nothing imports the API.
- Only `src/api/documents/pdf_xmp.py` imports `pymupdf` in production code. Add a function there instead of importing it elsewhere.
- Each component reads its own settings from the environment (`src/api/config.py`, `src/api/analysis/analyzer.py`, `src/api/documents/settings.py`).
- Authentication is a dependency on the router (`documents_router`, `text_analysis_router`), so a new route on those routers is protected automatically. Only `/api/v1/health` is public.
- Type hints on every function (mypy `disallow_untyped_defs`) and Google-style docstrings (ruff `pydocstyle` convention).

## Commits

Conventional Commits (`feat:`, `fix:`, `docs:` and so on), as [CONTRIBUTING.md](CONTRIBUTING.md) asks and the history follows. No commitlint or PR title check enforces it. Pull requests go to `development`; see [DEPLOYMENT.md](DEPLOYMENT.md) for the branch and release flow.
