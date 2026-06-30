# Combined production image — FastAPI backend + Streamlit sandbox.
#
# Build context MUST be the repository root (the backend imports the sibling
# `ai/` package, which must sit next to `backend/`):
#   docker build -f infra/docker/app.prod.Dockerfile -t ai-recruitment .
#
# Runs both processes via start-prod.sh: Streamlit is the public web port
# ($PORT), the backend is internal on 127.0.0.1:8000. They share a filesystem
# so dataset-by-path handoff and custom uploads work.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (better layer caching).
COPY backend/requirements.txt backend/requirements.txt
COPY sandbox/requirements.txt sandbox/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r backend/requirements.txt \
    && pip install -r sandbox/requirements.txt

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
