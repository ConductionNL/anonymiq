---
description: Run the Python unit tests, or one test file, and the UI tests
---

Python unit tests run in process and need no server and no NLP model. From the repository root, after `uv sync --python 3.12` (see the `check` command for the CI install):

```bash
uv run --frozen --no-sync python -m pytest tests/unit -q
```

For one file or one test, pass its path, for example:

```bash
uv run --frozen --no-sync python -m pytest tests/unit/test_text_routes.py -q
uv run --frozen --no-sync python -m pytest "tests/unit/test_document_auth.py::test_health_stays_public" -q
```

The `$ARGUMENTS` given to this command, if any, are the test path or `-k` expression to pass to pytest.

UI tests (vitest):

```bash
cd src/ui && npm test
```

Read the pytest summary line, not only the exit code. The tests in `tests/test_usecases.py` call a running server (`ANONYMIQ_BASE_URL`, default `localhost:8080`) and are not unit tests; run them only when asked.
