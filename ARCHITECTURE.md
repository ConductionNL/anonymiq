# Architecture

anonymiq is a Python web service. It finds personal data in Dutch text and PDF documents, and replaces it with placeholders. It can reverse that replacement for authorised users. Conduction apps reach it through OpenRegister's anonymisation backend; it also has a small web interface of its own.

This page is for new developers and for anyone who assesses the code, such as SIG. It names the functional components, says where each one starts and stops, and marks every top-level directory as production, test, generated or tooling.

## System boundary

anonymiq runs as its own container, next to Nextcloud rather than inside it.

| Talks to | How |
|---|---|
| OpenRegister | OpenRegister calls the REST API to analyse and anonymise text and documents |
| Its own database | SQLite by default (`DATABASE_URL`), for uploaded documents and their anonymisation records |
| NLP models | Loaded in-process: spaCy (`nl_core_news_md`) or a transformers model, behind Presidio |

## Directory roles

| Directory | Role |
|---|---|
| `src/api/` | Production Python: the FastAPI application. |
| `api.py` | Start-up script that runs the API with uvicorn. |
| `src/ui/` | Production front end (React, TypeScript, Vite). `src/ui/src/components/ui/` holds small styled primitives in the shadcn/ui pattern. |
| `src/tests/`, `tests/` | Test code only: pytest unit and integration tests, PDF fixtures. |
| `scripts/` | Developer tooling: health check, test runners and one-off PDF experiments. `scripts/test_*.py` and `scripts/run_tests.py` are test code. |
| `charts/`, `argocd/`, `Dockerfile`, `docker-compose.yaml` | Deployment: Helm chart, Argo CD applications, container build. |
| `docs/` | Documentation. |

## Functional components

We group the code by what the service does, not by FastAPI layer.

| Component | What it covers |
|---|---|
| Text analysis | The NLP engines, recognisers and patterns, the analysis service and the text endpoints |
| Documents | Document upload, PDF anonymisation and de-anonymisation, encryption of the mapping, storage |
| API wiring | Application start-up, configuration, dependencies, request and response models |
| Web interface | The React front end in `src/ui/` |
| Developer tooling | Scripts under `scripts/` |

### Boundaries

**Documents** uses **Text analysis** to find entities, never the other way round. **API wiring** is used by both. The front end talks to the API over HTTP only.

## How a request flows

1. A client calls `/api/v1/...` with text or a PDF.
2. The router hands over to the text analyzer, which runs the configured NLP engine and pattern recognisers.
3. For documents, the findings are applied to a copy of the PDF, and the mapping is stored encrypted so it can be reversed.

## Test code

All test code lives in `src/tests/` and `tests/`, plus the `test_*.py` scripts in `scripts/`. Nothing under `src/api/` or `src/ui/` is test code.

## Licence

anonymiq is licensed under EUPL-1.2.

### PyMuPDF (AGPL-3.0) is confined to one module

PDF anonymisation depends on [PyMuPDF](https://pypi.org/project/PyMuPDF/) (`pymupdf`), which Artifex licenses under AGPL-3.0 or a commercial licence. We use it under AGPL-3.0. Conduction decided this on 2026-10-29: the dependency is accepted, and kept in one place.

- **Where.** Production code imports `pymupdf` in exactly one module: `src/api/documents/pdf_xmp.py`. Every other part of the service reaches PDF handling through that module's functions, and the routes through `src/api/documents/service.py`. Tests import it too (`src/tests/test_documents.py`, `src/tests/integration/conftest.py`), to build and read fixtures.
- **What for.** Opening PDFs, reading text spans with their positions, and true redaction: `add_redact_annot` plus `apply_redactions` remove the text from the content stream instead of drawing a box over it. Text left recoverable under a black box is exactly the failure this service exists to prevent.
- **Why not replace it.** No library with a permissive licence redacts content streams. `pypdfium2` (BSD/Apache) reads text with positions but cannot redact. `pypdf` (BSD) can rewrite content streams, but safe text removal would be ours to build and prove. `pdfplumber` and `pdfminer.six` (MIT) only extract.
- **Rule for new code.** Do not import `pymupdf` anywhere else in `src/api/`. Add a function to `pdf_xmp.py` instead, so a later swap (a permissive library, or a commercial Artifex licence) touches one file.

anonymiq itself is EUPL-1.2, whose compatibility clause covers distribution together with AGPL-3.0 code.
