# ── Production backend image — FastAPI + uvicorn ────────────────────────
# Build context MUST be the repository root, because the backend imports the
# sibling `ai/` package via the repo root (app/__init__.py adds parents[2] to
# sys.path). The image therefore mirrors the repo layout: /app/backend + /app/ai.
#
#   docker build -f infra/docker/backend.prod.Dockerfile -t recruit-backend .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/backend/requirements.txt

# Application code: backend + sibling ai package
COPY ai /app/ai
COPY backend /app/backend

# Bundle ONLY the small sample dataset + JD (never the 465 MB official file)
COPY dataset/sample_candidates.jsonl /app/dataset/sample_candidates.jsonl
COPY dataset/job_description.docx /app/dataset/job_description.docx

# Entrypoint (migrate -> serve)
COPY infra/docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint.sh
RUN chmod +x /usr/local/bin/backend-entrypoint.sh

# Run from the backend dir so `import ai…` resolves (repo root = /app)
WORKDIR /app/backend

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/local/bin/backend-entrypoint.sh"]
