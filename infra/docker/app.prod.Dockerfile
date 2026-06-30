# Combined production image — FastAPI backend + Streamlit sandbox.
#
# Build context MUST be the repository root (the backend imports the sibling
# `ai/` package, which must sit next to `backend/`):
#   docker build -f infra/docker/app.prod.Dockerfile -t ai-recruitment .
#
# The backend (FastAPI pins an older starlette) and Streamlit (needs a newer
# starlette) are installed into SEPARATE virtualenvs so their dependencies never
# clash in one site-packages. Both run in the same container (shared filesystem),
# so dataset-by-path handoff and custom uploads work. Streamlit is the public web
# port ($PORT); the backend is internal on 127.0.0.1:8000.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    BACKEND_VENV=/opt/backend-venv \
    SANDBOX_VENV=/opt/sandbox-venv

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Two isolated virtual environments.
RUN python -m venv "$BACKEND_VENV" && python -m venv "$SANDBOX_VENV"

# Install dependencies first (better layer caching).
COPY backend/requirements.txt backend/requirements.txt
COPY sandbox/requirements.txt sandbox/requirements.txt
RUN "$BACKEND_VENV/bin/pip" install --upgrade pip \
    && "$BACKEND_VENV/bin/pip" install -r backend/requirements.txt
RUN "$SANDBOX_VENV/bin/pip" install --upgrade pip \
    && "$SANDBOX_VENV/bin/pip" install -r sandbox/requirements.txt

# Application source: backend + sibling `ai` package + sandbox.
COPY backend/ backend/
COPY ai/ ai/
COPY sandbox/ sandbox/

# Small demo sample + official JD (the 465 MB dataset is intentionally excluded).
COPY dataset/sample_candidates.jsonl dataset/sample_candidates.jsonl
COPY dataset/job_description.docx dataset/job_description.docx

COPY infra/docker/start-prod.sh /usr/local/bin/start-prod.sh
RUN chmod +x /usr/local/bin/start-prod.sh

# Production defaults (secrets + DB come from the platform's env vars).
ENV APP_ENV=production \
    LOG_JSON=true \
    PRIMARY_LLM_PROVIDER=gemini \
    FALLBACK_LLM_PROVIDER=ollama \
    GEMINI_MODEL=gemini-2.5-flash \
    RANKING_DATASET_PATH=/app/dataset/sample_candidates.jsonl \
    RANKING_EXPORT_DIR=/app/backend/var/rankings \
    SANDBOX_BACKEND_URL=http://localhost:8000/api/v1 \
    SANDBOX_OFFICIAL_DATASET=/app/dataset/sample_candidates.jsonl \
    SANDBOX_OFFICIAL_JD=/app/dataset/job_description.docx \
    PORT=8501

EXPOSE 8501

HEALTHCHECK --interval=20s --timeout=5s --start-period=45s --retries=5 \
    CMD curl -fsS "http://localhost:${PORT}/_stcore/health" || exit 1

CMD ["/usr/local/bin/start-prod.sh"]
