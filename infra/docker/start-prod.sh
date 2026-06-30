#!/usr/bin/env bash
# Production entrypoint for the combined deployment image.
#
# Runs BOTH processes in one container so they share a filesystem (the sandbox
# hands datasets to the backend by path, and custom uploads work):
#   * FastAPI backend  — internal only, 127.0.0.1:8000   (backend venv)
#   * Streamlit sandbox — public, 0.0.0.0:$PORT  (the demo UI, sandbox venv)
#
# Each process uses its OWN virtualenv so their dependencies never clash.
# No business logic here — orchestration only. No debug/reload flags.
set -euo pipefail

PORT="${PORT:-8501}"
BACKEND_VENV="${BACKEND_VENV:-/opt/backend-venv}"
SANDBOX_VENV="${SANDBOX_VENV:-/opt/sandbox-venv}"

echo "[start] applying database migrations…"
( cd /app/backend && "${BACKEND_VENV}/bin/alembic" upgrade head ) \
    || echo "[start] WARNING: migrations failed; continuing"

echo "[start] launching backend on 127.0.0.1:8000"
( cd /app/backend && exec "${BACKEND_VENV}/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 ) &
BACKEND_PID=$!

# Run Streamlit from the sandbox dir so its .streamlit/config.toml (upload limit)
# is picked up. app.py adds the repo root to sys.path, so imports still resolve.
echo "[start] launching Streamlit sandbox on 0.0.0.0:${PORT}"
( cd /app/sandbox && exec "${SANDBOX_VENV}/bin/streamlit" run app.py \
    --server.port "${PORT}" \
    --server.address 0.0.0.0 \
    --server.headless true ) &
STREAMLIT_PID=$!

# Forward termination to both children, and exit if either dies.
trap 'kill "${BACKEND_PID}" "${STREAMLIT_PID}" 2>/dev/null || true' TERM INT
wait -n "${BACKEND_PID}" "${STREAMLIT_PID}"
echo "[start] a process exited; shutting down."
kill "${BACKEND_PID}" "${STREAMLIT_PID}" 2>/dev/null || true
