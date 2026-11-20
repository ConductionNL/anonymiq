---
description: Run the quality suite that CI runs (ruff, mypy, unit tests with coverage, UI lint, test and build)
---

Run the same checks as `.github/workflows/ci.yml`, from the repository root. There is no Makefile and no single quality command; these steps are the suite.

1. Install the locked dependencies the way CI does, without torch, its CUDA wheels and the large spaCy model (the unit tests load none of them):

   ```bash
   SKIP=$(grep -oE '^name = "(torch|triton|nvidia-[a-z0-9-]+|nl-core-news-lg)"' uv.lock \
     | sed -E 's/name = "(.*)"/--no-install-package \1/')
   uv sync --frozen --python 3.12 $SKIP
   ```

2. Python checks, with the versions CI pins:

   ```bash
   uvx ruff@0.17.0 check .
   uvx ruff@0.17.0 format --check .
   uv run --frozen --no-sync --with mypy==2.4.0 mypy src/api
   uv run --frozen --no-sync --with pytest-cov==7.1.0 python -m pytest tests/unit -p no:cacheprovider --cov=src/api --cov-report=term --cov-fail-under=37
   ```

3. Web interface:

   ```bash
   cd src/ui && npm ci --no-audit --no-fund && npm run lint && npm test && npm run build
   ```

Report each step as passed or failed, with the pytest summary line and the coverage total. If `uvx ruff@0.17.0 format --check .` fails, `uvx ruff@0.17.0 format .` fixes it. Do not lower `--cov-fail-under`; the floor in `ci.yml` must never go down.
