#!/usr/bin/env bash
# Production entrypoint for the combined deployment image.
#
# Runs BOTH processes in one container so they share a filesystem (the sandbox
# hands datasets to the backend by path, and custom uploads work):
#   * FastAPI backend  — internal only, 127.0.0.1:8000
#   * Streamlit sandbox — public, 0.0.0.0:$PORT  (the demo UI)
#
# No business logic here — orchestration only. No debug/reload flags.
set -euo pipefail

PORT="${PORT:-8501}"

echo "[start] applying database migrations…"
( cd /app/backend && alembic upgrade head ) || echo "[start] WARNING: migrations failed; continuing"

echo "[start] launching backend on 127.0.0.1:8000"
( cd /app/backend && exec uvicorn app.main:app --host 127.0.0.1 --port 8000 ) &
BACKEND_PID=$!

echo "[start] launching Streamlit sandbox on 0.0.0.0:${PORT}"
( cd /app && exec streamlit run sandbox/app.py \
    --server.port "${PORT}" \
    --server.address 0.0.0.0 \
    --server.headless true ) &
STREAMLIT_PID=$!

# Forward termination to both children, and exit if either dies.
trap 'kill "${BACKEND_PID}" "${STREAMLIT_PID}" 2>/dev/null || true' TERM INT
wait -n "${BACKEND_PID}" "${STREAMLIT_PID}"
echo "[start] a process exited; shutting down."
kill "${BACKEND_PID}" "${STREAMLIT_PID}" 2>/dev/null || true
