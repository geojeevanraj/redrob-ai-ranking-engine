# ── Streamlit sandbox image ─────────────────────────────────────────────
# Build context MUST be the repository root (the app imports the `sandbox`
# package and resolves official file paths relative to the repo root).
#
#   docker build -f infra/docker/sandbox.Dockerfile -t recruit-sandbox .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Defaults; override in compose / platform env.
    SANDBOX_BACKEND_URL=http://backend:8000/api/v1 \
    SANDBOX_OFFICIAL_DATASET=/app/dataset/sample_candidates.jsonl \
    SANDBOX_OFFICIAL_JD=/app/dataset/job_description.docx

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY sandbox/requirements.txt /app/sandbox/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/sandbox/requirements.txt

# Sandbox app (includes .streamlit/config.toml with the 1 GB upload limit)
COPY sandbox /app/sandbox

# Bundle the small sample dataset + JD so the "official" option works in-image
COPY dataset/sample_candidates.jsonl /app/dataset/sample_candidates.jsonl
COPY dataset/job_description.docx /app/dataset/job_description.docx

EXPOSE 8501
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "sandbox/app.py", \
     "--server.port", "8501", \
     "--server.address", "0.0.0.0", \
     "--server.headless", "true"]
