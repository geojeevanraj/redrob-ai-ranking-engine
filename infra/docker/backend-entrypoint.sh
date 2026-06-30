#!/usr/bin/env sh
# Production backend entrypoint: apply migrations (with a short retry while the
# database becomes reachable), then start the API. No --reload, no debug.
set -e

echo "[entrypoint] applying database migrations…"
n=0
until alembic upgrade head; do
  n=$((n + 1))
  if [ "$n" -ge 10 ]; then
    echo "[entrypoint] migrations failed after $n attempts" >&2
    exit 1
  fi
  echo "[entrypoint] database not ready yet (attempt $n) — retrying in 3s…"
  sleep 3
done

echo "[entrypoint] starting uvicorn…"
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${BACKEND_PORT:-8000}" \
  --workers "${UVICORN_WORKERS:-2}" \
  --no-server-header
