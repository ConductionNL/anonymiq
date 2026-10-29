FROM python:3.12.16-bookworm

# Pick up Debian security fixes published after the base image was built:
# the image scan fails the build on any CRITICAL finding that has a fix.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# use the latest version of uv from the official repository
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN groupadd -r presidio && useradd --no-log-init -r -g presidio presidio

WORKDIR /app

# Create necessary directories and set permissions
RUN mkdir -p /home/presidio/.cache/uv && \
    chown -R presidio:presidio /home/presidio/.cache && \
    chown -R presidio:presidio /app

COPY --chown=presidio:presidio pyproject.toml uv.lock ./

USER presidio

# Disable UV cache for runtime (read-only filesystem in K8s)
ENV UV_NO_CACHE=1

# resolve from uv.lock only, no dev dependencies
RUN uv sync --frozen --no-dev --no-cache
 
# Pre-install Dutch SpaCy model used in production/staging (pin to SpaCy 3.8 series).
# Use pip inside the venv and verify; force layer rebuild with ARG.
ARG FORCE_REBUILD_MAIN="2026-01-13T12:05Z"
RUN set -eux; echo "$FORCE_REBUILD_MAIN" >/dev/null; \
    .venv/bin/python -m ensurepip --upgrade; \
    .venv/bin/pip install -q \
      "nl_core_news_md @ https://github.com/explosion/spacy-models/releases/download/nl_core_news_md-3.8.0/nl_core_news_md-3.8.0-py3-none-any.whl" \
    || .venv/bin/python -m spacy download nl_core_news_md; \
    .venv/bin/python -c "import spacy; spacy.load('nl_core_news_md'); print('nl_core_news_md installed')"

# Pre-download transformers models during build to avoid runtime download
ENV TRANSFORMERS_CACHE=/home/presidio/.cache/transformers
ENV HF_HOME=/home/presidio/.cache/huggingface

# Create cache directories first in a separate layer
RUN mkdir -p /home/presidio/.cache/transformers /home/presidio/.cache/huggingface && \
    chown -R presidio:presidio /home/presidio/.cache

# Download a Dutch NER model for transformers in a separate layer
# Using a model with a token-classification head (NER)
RUN MODEL_NAME="wietsedv/bert-base-dutch-cased-finetuned-conll2002-ner" && \
    echo "Downloading ${MODEL_NAME}..." && \
    .venv/bin/python -c "from transformers import AutoTokenizer, AutoModelForTokenClassification; \
    tokenizer = AutoTokenizer.from_pretrained('${MODEL_NAME}', cache_dir='${TRANSFORMERS_CACHE}'); \
    model = AutoModelForTokenClassification.from_pretrained('${MODEL_NAME}', cache_dir='${TRANSFORMERS_CACHE}'); \
    print('Model downloaded successfully!')"


COPY --chown=presidio:presidio src/api ./src/api
COPY --chown=presidio:presidio api.py ./
COPY --chown=presidio:presidio scripts/healthcheck.py ./scripts/


EXPOSE 8080

# Add Docker healthcheck
HEALTHCHECK \
    --interval=60s \
    --timeout=5s \
    --start-period=25s \
    --retries=5 \
  CMD [".venv/bin/python", "scripts/healthcheck.py", "--port", "8080"]

CMD [".venv/bin/python", "api.py", "--host", "0.0.0.0", "--workers", "2", "--env", "production", "--port", "8080"]